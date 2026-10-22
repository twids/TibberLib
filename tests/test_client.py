import json

import httpx
import pytest

from tibberlib import TibberClient, TibberError


async def token():
    return "test-secret"


async def test_zero_soc_and_explicit_vehicle():
    def handle(request):
        body = json.loads(request.content)
        assert body["variables"] == {
            "vehicleId": "zoe", "homeId": "home",
            "settings": [{"key": "offline.vehicle.batteryLevel", "value": 0}],
        }
        return httpx.Response(200, json={"data": {"me": {
            "setVehicleSettings": {"__typename": "Vehicle"}
        }}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        await TibberClient(http, token).set_vehicle_soc(
            vehicle_id="zoe", home_id="home", battery_level=0
        )


@pytest.mark.parametrize("value", [-1, 101, True, 40.5, "40"])
async def test_invalid_soc_never_calls_token_provider(value):
    async def forbidden():
        raise AssertionError("must validate before authentication")
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError):
            await TibberClient(http, forbidden).set_vehicle_soc(
                vehicle_id="zoe", home_id="home", battery_level=value
            )


@pytest.mark.parametrize("status,payload", [
    (401, {"secret": "test-secret"}),
    (200, {"errors": [{"message": "test-secret"}]}),
    (200, {"data": {"me": {"setVehicleSettings": None}}}),
    (200, []),
])
async def test_failures_propagate_without_secrets_or_retry(status, payload):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, json=payload)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        with pytest.raises(TibberError) as error:
            await TibberClient(http, token).set_vehicle_soc(
                vehicle_id="zoe", home_id="home", battery_level=40
            )
    assert "test-secret" not in str(error.value)
    assert len(calls) == 1
