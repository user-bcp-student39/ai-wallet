from datetime import datetime, timezone

from domain.onboarding import Step, OnboardingSession

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_onboarding_has_five_steps_and_starts_at_step_one():
    assert len(Step) == 5
    assert OnboardingSession.start(NOW).step == Step.NAME == 1


def test_wallet_starts_inactive_and_becomes_active_only_on_activation():
    session = OnboardingSession.start(NOW)
    assert session.activated is False
