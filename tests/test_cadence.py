"""Unit tests for the pure follow-up cadence scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.cadence import (
    CADENCE_DAY_OFFSETS,
    MAX_STEP,
    initial_schedule,
    next_run_for_step,
    schedule_after_send,
)

ENROLLED = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_offsets_match_spec():
    assert CADENCE_DAY_OFFSETS == {1: 1, 2: 3, 3: 7, 4: 14}


def test_initial_schedule_is_one_day():
    assert initial_schedule(ENROLLED) == ENROLLED + timedelta(days=1)


@pytest.mark.parametrize("step,days", [(1, 1), (2, 3), (3, 7), (4, 14)])
def test_next_run_for_step(step, days):
    assert next_run_for_step(ENROLLED, step) == ENROLLED + timedelta(days=days)


def test_advance_from_step1_to_step2():
    d = schedule_after_send(ENROLLED, sent_step=1)
    assert d.is_active is True
    assert d.next_step == 2
    assert d.next_run_at == ENROLLED + timedelta(days=3)


def test_advance_through_full_sequence():
    d2 = schedule_after_send(ENROLLED, 2)
    assert d2.next_step == 3 and d2.next_run_at == ENROLLED + timedelta(days=7)
    d3 = schedule_after_send(ENROLLED, 3)
    assert d3.next_step == 4 and d3.next_run_at == ENROLLED + timedelta(days=14)


def test_deactivates_after_last_step():
    d = schedule_after_send(ENROLLED, sent_step=MAX_STEP)
    assert d.is_active is False
    assert d.next_step is None
    assert d.next_run_at is None


def test_invalid_step_raises():
    with pytest.raises(ValueError):
        next_run_for_step(ENROLLED, 5)
    with pytest.raises(ValueError):
        schedule_after_send(ENROLLED, 0)
