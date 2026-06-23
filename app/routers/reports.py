from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentPrincipal, DBSession
from app.schemas.report import FunnelReport, PipelineReport, SourcesReport, TeamReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/funnel", response_model=FunnelReport)
async def funnel(session: DBSession, principal: CurrentPrincipal) -> FunnelReport:
    return await ReportService(session, principal).funnel()


@router.get("/pipeline", response_model=PipelineReport)
async def pipeline(session: DBSession, principal: CurrentPrincipal) -> PipelineReport:
    return await ReportService(session, principal).pipeline()


@router.get("/sources", response_model=SourcesReport)
async def sources(session: DBSession, principal: CurrentPrincipal) -> SourcesReport:
    return await ReportService(session, principal).sources()


@router.get("/team", response_model=TeamReport)
async def team(session: DBSession, principal: CurrentPrincipal) -> TeamReport:
    return await ReportService(session, principal).team()
