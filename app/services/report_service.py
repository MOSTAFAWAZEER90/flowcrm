from __future__ import annotations

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.enums import ContactStatus, PipelineStage, TaskStatus
from app.models.task import Task
from app.models.user import User
from app.schemas.report import (
    FunnelReport,
    FunnelStage,
    PipelineReport,
    PipelineStageValue,
    SourceBreakdown,
    SourcesReport,
    TeamMemberStats,
    TeamReport,
)

_CLOSED = (PipelineStage.won, PipelineStage.lost)
_D0 = Decimal("0")


class ReportService:
    def __init__(self, session: AsyncSession, principal: Principal):
        self.session = session
        self.principal = principal

    async def funnel(self) -> FunnelReport:
        rows = (
            await self.session.execute(
                select(Deal.stage, func.count()).group_by(Deal.stage)
            )
        ).all()
        counts = {stage: count for stage, count in rows}
        stages = [
            FunnelStage(stage=s.value, count=int(counts.get(s, 0))) for s in PipelineStage
        ]
        total_contacts = int(
            await self.session.scalar(
                select(func.count()).select_from(Contact).where(Contact.deleted_at.is_(None))
            )
            or 0
        )
        return FunnelReport(stages=stages, total_contacts=total_contacts)

    async def pipeline(self) -> PipelineReport:
        weighted = func.coalesce(
            func.sum(Deal.value * Deal.probability / 100.0), 0
        )
        rows = (
            await self.session.execute(
                select(
                    Deal.stage,
                    func.count(),
                    func.coalesce(func.sum(Deal.value), 0),
                    weighted,
                ).group_by(Deal.stage)
            )
        ).all()
        stages = [
            PipelineStageValue(
                stage=stage.value,
                count=int(count),
                total_value=Decimal(str(total)),
                weighted_value=Decimal(str(round(float(wtd), 2))),
            )
            for stage, count, total, wtd in rows
        ]
        open_value = Decimal(
            str(
                await self.session.scalar(
                    select(func.coalesce(func.sum(Deal.value), 0)).where(
                        Deal.stage.notin_(_CLOSED)
                    )
                )
                or 0
            )
        )
        won_value = Decimal(
            str(
                await self.session.scalar(
                    select(func.coalesce(func.sum(Deal.value), 0)).where(
                        Deal.stage == PipelineStage.won
                    )
                )
                or 0
            )
        )
        return PipelineReport(stages=stages, open_value=open_value, won_value=won_value)

    async def sources(self) -> SourcesReport:
        won_expr = func.sum(
            case((Contact.status == ContactStatus.customer, 1), else_=0)
        )
        rows = (
            await self.session.execute(
                select(Contact.source, func.count(), won_expr)
                .where(Contact.deleted_at.is_(None))
                .group_by(Contact.source)
            )
        ).all()
        return SourcesReport(
            sources=[
                SourceBreakdown(source=src.value, count=int(cnt), won=int(won or 0))
                for src, cnt, won in rows
            ]
        )

    async def team(self) -> TeamReport:
        users = (await self.session.execute(select(User))).scalars().all()

        deal_rows = (
            await self.session.execute(
                select(
                    Deal.owner_id,
                    func.sum(case((Deal.stage.notin_(_CLOSED), 1), else_=0)),
                    func.sum(case((Deal.stage == PipelineStage.won, 1), else_=0)),
                    func.coalesce(
                        func.sum(
                            case((Deal.stage == PipelineStage.won, Deal.value), else_=0)
                        ),
                        0,
                    ),
                ).group_by(Deal.owner_id)
            )
        ).all()
        deals_by_user = {
            owner: (int(open_c), int(won_c), Decimal(str(won_v)))
            for owner, open_c, won_c, won_v in deal_rows
        }

        task_rows = (
            await self.session.execute(
                select(Task.assigned_to, func.count())
                .where(Task.status == TaskStatus.open)
                .group_by(Task.assigned_to)
            )
        ).all()
        open_tasks_by_user = {uid: int(cnt) for uid, cnt in task_rows}

        members = []
        for user in users:
            open_c, won_c, won_v = deals_by_user.get(user.id, (0, 0, _D0))
            members.append(
                TeamMemberStats(
                    user_id=user.id,
                    full_name=user.full_name,
                    open_deals=open_c,
                    won_deals=won_c,
                    won_value=won_v,
                    open_tasks=open_tasks_by_user.get(user.id, 0),
                )
            )
        return TeamReport(members=members)
