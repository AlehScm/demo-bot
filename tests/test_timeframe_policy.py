import pytest

from application.policies.timeframe_policy import TimeframePolicy
from domain.exceptions.errors import UnsupportedTimeframeError
from domain.value_objects.timeframe import Timeframe


def test_timeframe_policy_allows_defaults() -> None:
    policy = TimeframePolicy()
    assert policy.ensure_supported(Timeframe.ONE_MINUTE) == Timeframe.ONE_MINUTE


def test_timeframe_policy_rejects_unsupported() -> None:
    policy = TimeframePolicy(allowed_timeframes=[Timeframe.ONE_MINUTE])
    with pytest.raises(UnsupportedTimeframeError):
        policy.ensure_supported(Timeframe.ONE_HOUR)
