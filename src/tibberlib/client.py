"""Only operations found in the app are enabled here."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

TokenProvider = Callable[[], Awaitable[str]]

SET_SOC = """mutation SetVehicleSettings(
  $vehicleId: String!, $homeId: String!, $settings: [SettingsItemInput!]
) {
  me {
    setVehicleSettings(id: $vehicleId, homeId: $homeId, settings: $settings) {
      __typename
    }
  }
}"""


class TibberError(Exception):
    """Sanitized API error: never includes headers, tokens or response bodies."""


class TibberClient:
    """Use an HA-managed HTTP client and token provider; caller owns both.

    Mutations are not retried automatically: a lost response can mean that
    the server already applied the write. Success is API acknowledgement,
    not confirmation that the car stopped or a charging plan was updated.
    """

    def __init__(self, http: httpx.AsyncClient, token_provider: TokenProvider):
        self._http = http
        self._token_provider = token_provider

    async def set_vehicle_soc(
        self, *, vehicle_id: str, home_id: str, battery_level: int
    ) -> None:
        if not vehicle_id.strip() or not home_id.strip():
            raise ValueError("vehicle_id and home_id must be nonempty")
        if type(battery_level) is not int or not 0 <= battery_level <= 100:
            raise ValueError("battery_level must be an integer between 0 and 100")
        token = await self._token_provider()
        if not token:
            raise TibberError("No app access token available")
        try:
            response = await self._http.post(
                "https://app.tibber.com/v4/gql",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "TibberLib/0.1.0",
                },
                json={
                    "query": SET_SOC,
                    "variables": {
                        "vehicleId": vehicle_id,
                        "homeId": home_id,
                        "settings": [{
                            "key": "offline.vehicle.batteryLevel",
                            "value": battery_level,
                        }],
                    },
                },
                timeout=20,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise TibberError("Tibber request failed; write outcome unknown") from None
        if response.status_code != 200:
            raise TibberError(f"Tibber HTTP status {response.status_code}")
        try:
            payload: Any = response.json()
        except ValueError:
            raise TibberError("Tibber returned invalid JSON") from None
        if not isinstance(payload, dict) or payload.get("errors"):
            raise TibberError("Tibber returned a GraphQL error or invalid response")
        data = payload.get("data")
        me = data.get("me") if isinstance(data, dict) else None
        result = me.get("setVehicleSettings") if isinstance(me, dict) else None
        if not isinstance(result, dict) or not result.get("__typename"):
            raise TibberError("Tibber did not acknowledge the settings update")
