"""Pure follow-up cadence scheduling.

Cadence day offsets (relative to enrollment): step1=+1, step2=+3, step3=+7,
step4=+14. After step 4 the sequence deactivates. Kept pure for unit testing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

CADENCE_DAY_OFFSETS: dict[int, int] = {1: 1, 2: 3, 3: 7, 4: 14}
MAX_STEP = 4


@dataclass(frozen=True)
class CadenceDecision:
    next_step: int | None  # None once the sequence is finished
    next_run_at: datetime | None
    is_active: bool


def next_run_for_step(enrolled_at: datetime, step: int) -> datetime:
    """Absolute run time for a given 1-based step, measured from enrollment."""
    if step not in CADENCE_DAY_OFFSETS:
        raise ValueError(f"Invalid cadence step: {step}")
    return enrolled_at + timedelta(days=CADENCE_DAY_OFFSETS[step])


def initial_schedule(enrolled_at: datetime) -> datetime:
    """When the first step (step 1) is due."""
    return next_run_for_step(enrolled_at, 1)


def schedule_after_send(enrolled_at: datetime, sent_step: int) -> CadenceDecision:
    """Given the step just sent, decide the next step / run time / active flag."""
    if sent_step < 1:
        raise ValueError("sent_step must be >= 1")
    if sent_step >= MAX_STEP:
        return CadenceDecision(next_step=None, next_run_at=None, is_active=False)
    next_step = sent_step + 1
    return CadenceDecision(
        next_step=next_step,
        next_run_at=next_run_for_step(enrolled_at, next_step),
        is_active=True,
    )
