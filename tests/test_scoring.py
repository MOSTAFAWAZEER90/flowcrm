"""Unit tests for the pure lead-score blend function."""
from __future__ import annotations

from app.models.enums import LeadChannel
from app.services.scoring import (
    HOT_LEAD_THRESHOLD,
    ScoreFeatures,
    blend_lead_score,
    is_hot_lead,
)


def _features(**overrides) -> ScoreFeatures:
    base = dict(
        ai_base_score=50,
        channel=LeadChannel.web_form,
        recency_hours=1.0,
        has_email=True,
        has_phone=True,
        has_name=True,
        buying_signal=False,
    )
    base.update(overrides)
    return ScoreFeatures(**base)


def test_score_is_clamped_0_100():
    assert blend_lead_score(_features(ai_base_score=1000)) <= 100
    assert blend_lead_score(_features(ai_base_score=-50)) >= 0


def test_hot_lead_via_whatsapp_and_buying_signal():
    score = blend_lead_score(
        _features(
            ai_base_score=90,
            channel=LeadChannel.whatsapp,
            recency_hours=0.5,
            buying_signal=True,
        )
    )
    assert score >= HOT_LEAD_THRESHOLD
    assert is_hot_lead(score, True)


def test_cold_lead_low_score():
    score = blend_lead_score(
        _features(
            ai_base_score=10,
            channel=LeadChannel.manual,
            recency_hours=1000.0,
            has_email=False,
            has_phone=False,
        )
    )
    assert score < HOT_LEAD_THRESHOLD
    assert not is_hot_lead(score, False)


def test_channel_quality_increases_score():
    low = blend_lead_score(_features(channel=LeadChannel.manual))
    high = blend_lead_score(_features(channel=LeadChannel.calendly))
    assert high > low


def test_profile_completeness_increases_score():
    sparse = blend_lead_score(_features(has_email=False, has_phone=False))
    full = blend_lead_score(_features(has_email=True, has_phone=True))
    assert full > sparse


def test_recency_decay():
    fresh = blend_lead_score(_features(recency_hours=0.5))
    stale = blend_lead_score(_features(recency_hours=1000.0))
    assert fresh > stale


def test_buying_signal_bonus_and_hot_threshold():
    no_signal = blend_lead_score(_features(ai_base_score=60, buying_signal=False))
    with_signal = blend_lead_score(_features(ai_base_score=60, buying_signal=True))
    assert with_signal > no_signal
    # buying_signal forces hot even with a modest score
    assert is_hot_lead(40, True)
    assert not is_hot_lead(40, False)
    assert is_hot_lead(HOT_LEAD_THRESHOLD, False)
