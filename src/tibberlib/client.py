"""Only operations found in the app are enabled here."""

from collections.abc import Awaitable, Callable
from collections.abc import Mapping
from datetime import time
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
        await self._set_settings(vehicle_id, home_id, [{
            "key": "offline.vehicle.batteryLevel", "value": battery_level,
        }])

    async def set_departure_times(
        self, *, vehicle_id: str, home_id: str,
        departures: Mapping[str, time | None],
    ) -> None:
        """Set only specified weekdays. None removes a time, not smart charging.

        Times are local wall-clock values, not UTC instants. The caller owns
        timezone/date selection. APK time-picker code formats HH:mm:00 and its
        turn-off path passes null through EditedSetting/saveSetting.
        """
        weekdays = {"monday", "tuesday", "wednesday", "thursday", "friday",
                    "saturday", "sunday"}
        if not vehicle_id.strip() or not home_id.strip() or not departures:
            raise ValueError("Vehicle, home and at least one weekday are required")
        settings = []
        for day, departure in departures.items():
            if day not in weekdays:
                raise ValueError("Invalid weekday")
            if departure is not None and (
                not isinstance(departure, time) or departure.tzinfo is not None
                or departure.second or departure.microsecond
            ):
                raise ValueError("Departure must be a local time with minute precision")
            settings.append({
                "key": f"offline.vehicle.departureTimes.{day}",
                "value": departure.strftime("%H:%M:00") if departure is not None else None,
            })
        await self._set_settings(vehicle_id, home_id, settings)

    async def _set_settings(self, vehicle_id: str, home_id: str, settings: list[dict]) -> None:
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
                        "settings": settings,
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
