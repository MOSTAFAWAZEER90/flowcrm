"""Pure, deterministic lead-score blending.

The final lead score blends the AI base score with deterministic signal features
(channel quality, recency, profile completeness, explicit buying signal). Kept
free of I/O so it is trivially unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import LeadChannel

HOT_LEAD_THRESHOLD = 70

# Relative blend weights (must sum to 1.0).
W_AI = 0.50
W_CHANNEL = 0.20
W_RECENCY = 0.15
W_PROFILE = 0.15

# Explicit buying signal nudges the score upward.
BUYING_SIGNAL_BONUS = 10

# Per-channel intent quality (0-100). Higher = warmer channel.
CHANNEL_QUALITY: dict[LeadChannel, int] = {
    LeadChannel.calendly: 95,
    LeadChannel.whatsapp: 90,
    LeadChannel.fb_lead_form: 80,
    LeadChannel.messenger: 75,
    LeadChannel.instagram: 70,
    LeadChannel.web_form: 65,
    LeadChannel.landing_page: 62,
    LeadChannel.google_form: 60,
    LeadChannel.email: 55,
    LeadChannel.manual: 50,
}


@dataclass(frozen=True)
class ScoreFeatures:
    ai_base_score: int  # 0-100, from the AI classifier
    channel: LeadChannel
    recency_hours: float | None  # hours since last activity (None => unknown)
    has_email: bool
    has_phone: bool
    has_name: bool
    buying_signal: bool = False


def _clamp(value: float, low: int = 0, high: int = 100) -> int:
    return int(max(low, min(high, round(value))))


def _recency_score(recency_hours: float | None) -> int:
    if recency_hours is None:
        return 50  # neutral when unknown
    if recency_hours <= 1:
        return 100
    if recency_hours <= 24:
        return 85
    if recency_hours <= 72:
        return 65
    if recency_hours <= 168:  # 1 week
        return 45
    if recency_hours <= 720:  # 1 month
        return 25
    return 10


def _profile_score(has_email: bool, has_phone: bool, has_name: bool) -> int:
    return (40 if has_email else 0) + (40 if has_phone else 0) + (20 if has_name else 0)


def blend_lead_score(features: ScoreFeatures) -> int:
    """Blend AI + deterministic features into a final 0-100 lead score."""
    ai = _clamp(features.ai_base_score)
    channel = CHANNEL_QUALITY.get(features.channel, 50)
    recency = _recency_score(features.recency_hours)
    profile = _profile_score(features.has_email, features.has_phone, features.has_name)

    blended = W_AI * ai + W_CHANNEL * channel + W_RECENCY * recency + W_PROFILE * profile
    if features.buying_signal:
        blended += BUYING_SIGNAL_BONUS
    return _clamp(blended)


def is_hot_lead(score: int, buying_signal: bool) -> bool:
    return score >= HOT_LEAD_THRESHOLD or buying_signal
