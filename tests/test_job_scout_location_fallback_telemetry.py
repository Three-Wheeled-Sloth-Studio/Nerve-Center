import inspect

from nerve_center.plugins.job_scout.location_discovery import (
    LocationAwareJobScoutDiscoveryLoop,
)


def test_location_cycle_carries_search_provider_fallback_counter() -> None:
    source = inspect.getsource(LocationAwareJobScoutDiscoveryLoop.cycle)
    assert source.count('"search_provider_fallbacks"') >= 2
