from datetime import time, timezone
import json

import httpx
import pytest

from tibberlib import TibberClient


async def token():
    return "test-token"


async def test_set_and_clear_preserves_unspecified_days_and_null():
    requests = []
    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"data": {"me": {
            "setVehicleSettings": {"__typename": "Vehicle"}
        }}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await TibberClient(http, token).set_departure_times(
            vehicle_id="zoe", home_id="home",
            departures={"friday": time(6), "monday": None},
        )
    assert len(requests) == 1
    assert requests[0]["variables"]["settings"] == [
        {"key": "offline.vehicle.departureTimes.friday", "value": "06:00:00"},
        {"key": "offline.vehicle.departureTimes.monday", "value": None},
    ]


@pytest.mark.parametrize("departures", [
    {}, {"fri": time(6)}, {"friday": "06:00"}, {"friday": True},
    {"friday": time(6, 0, 1)}, {"friday": time(6, tzinfo=timezone.utc)},
])
async def test_bad_departures_rejected_before_authentication(departures):
    async def forbidden():
        raise AssertionError("invalid input must not reach authentication")
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError):
            await TibberClient(http, forbidden).set_departure_times(
                vehicle_id="zoe", home_id="home", departures=departures,
            )
