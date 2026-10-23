"""Read-only app discovery; protocol recovered from APK/community evidence.

These operations require account verification before production deployment.
No raw server replies or credentials are logged.
"""

import asyncio
import json
from typing import Any

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .client import TibberError

VEHICLE_SNAPSHOT = """subscription vehicleStateSubscription($vehicleId: String!) {
  vehicleState(vehicleId: $vehicleId) {
    id name
    battery { level canReadLevel }
    charging {
      targetedStateOfCharge targetedDepartureTime chargerId
      departureTimes { weekday time { hours minutes } }
    }
    userSettings { key value valueType valueIsArray isReadOnly }
    settingsScreen {
      uid type title settingKey
      childItems { uid type title settingKey
        childItems { uid type title settingKey }
      }
    }
    actionButtons { text enabled action type url redirect }
    chargers { chargerId name sessionId }
  }
}"""


async def list_vehicles(http: httpx.AsyncClient, token: str) -> list[dict[str, Any]]:
    """List account vehicles using the APK's GetMyVehicles document subset."""
    try:
        response = await http.post(
            "https://app.tibber.com/v4/gql",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "query GetMyVehicles { me { myVehicles { vehicles { id title isPaired } } } }"},
            timeout=20, follow_redirects=False,
        )
    except httpx.HTTPError:
        raise TibberError("Vehicle listing request failed") from None
    if response.status_code != 200:
        raise TibberError(f"Vehicle listing HTTP status {response.status_code}")
    try:
        data = response.json()
        if data.get("errors"):
            raise TibberError("Vehicle listing GraphQL error")
        vehicles = data["data"]["me"]["myVehicles"]["vehicles"]
        if not isinstance(vehicles, list) or any(
            not isinstance(v, dict) or not isinstance(v.get("id"), str) for v in vehicles
        ):
            raise TibberError("Invalid vehicle list")
        return vehicles
    except (ValueError, TypeError, KeyError, AttributeError):
        raise TibberError("Invalid vehicle listing response") from None


async def list_homes(http: httpx.AsyncClient, token: str) -> list[dict[str, Any]]:
    """APK GetHomes document subset (HomeItem id/title)."""
    try:
        response = await http.post(
            "https://app.tibber.com/v4/gql",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "query GetHomes { me { homes { id title } } }"},
            timeout=20, follow_redirects=False,
        )
        if response.status_code != 200:
            raise TibberError(f"Home listing HTTP status {response.status_code}")
        data = response.json()
        if data.get("errors"):
            raise TibberError("Home listing GraphQL error")
        homes = data["data"]["me"]["homes"]
        if not isinstance(homes, list) or any(
            not isinstance(h, dict) or not isinstance(h.get("id"), str) for h in homes
        ):
            raise TibberError("Invalid home list")
        return homes
    except httpx.HTTPError:
        raise TibberError("Home listing request failed") from None
    except (ValueError, TypeError, KeyError, AttributeError):
        raise TibberError("Invalid home listing response") from None


async def login(http: httpx.AsyncClient, email: str, password: str) -> str:
    """Get an app token. Caller must store/refresh credentials securely.

    Endpoint and JSON shape are from DG65/NRGTibberGridRewards; this is
    deliberately marked unverified with the user's live account.
    """
    try:
        response = await http.post(
            "https://app.tibber.com/v1/login.credentials",
            json={"email": email, "password": password},
            headers={"User-Agent": "TibberLib/0.1.0"},
            follow_redirects=False,
            timeout=20,
        )
    except httpx.HTTPError:
        raise TibberError("App authentication request failed") from None
    if response.status_code != 200:
        raise TibberError(f"App authentication HTTP status {response.status_code}")
    try:
        data = response.json()
    except ValueError:
        raise TibberError("Invalid authentication response") from None
    token = data.get("token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token:
        raise TibberError("Authentication did not return an app token")
    return token


async def read_vehicle(token: str, vehicle_id: str) -> dict[str, Any]:
    """Read the first vehicle snapshot then close the subscription.

    This intentionally exposes server-provided setting definitions rather than
    making up departure-time keys or pause commands.
    """
    if not token or not vehicle_id.strip():
        raise ValueError("App token and vehicle_id are required")
    try:
        async with asyncio.timeout(30):
            async with connect(
                "wss://app.tibber.com/v4/gql/ws",
                additional_headers={"Authorization": f"Bearer {token}"},
                subprotocols=["graphql-transport-ws"],
                max_size=2**20,
                proxy=None,
            ) as ws:
                await ws.send(json.dumps({"type": "connection_init"}))
                acknowledged = False
                async for raw in ws:
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise TibberError("Invalid subscription response")
                    kind = message.get("type")
                    if kind == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                    elif kind == "connection_ack" and not acknowledged:
                        acknowledged = True
                        await ws.send(json.dumps({
                            "id": "vehicle", "type": "subscribe",
                            "payload": {"query": VEHICLE_SNAPSHOT,
                                        "variables": {"vehicleId": vehicle_id}},
                        }))
                    elif kind == "next" and message.get("id") == "vehicle":
                        payload = message.get("payload")
                        if not isinstance(payload, dict) or payload.get("errors"):
                            raise TibberError("Vehicle subscription GraphQL error")
                        data = payload.get("data")
                        vehicle = data.get("vehicleState") if isinstance(data, dict) else None
                        if not isinstance(vehicle, dict) or vehicle.get("id") != vehicle_id:
                            raise TibberError("Vehicle snapshot missing or ID mismatch")
                        await ws.send(json.dumps({"id": "vehicle", "type": "complete"}))
                        return vehicle
                    elif kind in {"error", "connection_error", "complete"}:
                        raise TibberError("Vehicle subscription ended without a snapshot")
                raise TibberError("Vehicle subscription closed without a snapshot")
    except TimeoutError:
        raise TibberError("Vehicle snapshot timed out after 30 seconds") from None
    except OSError:
        raise TibberError("Vehicle snapshot network connection failed") from None
    except WebSocketException as err:
        # Codes are safe diagnostics. Never include server reasons/headers/bodies.
        received = getattr(err, "rcvd", None)
        code = getattr(received, "code", None)
        response = getattr(err, "response", None)
        status = getattr(response, "status_code", None)
        detail = f" (close code {code})" if isinstance(code, int) else ""
        if isinstance(status, int):
            detail = f" (HTTP {status})"
        raise TibberError(f"Vehicle snapshot WebSocket failed{detail}") from None
    except (ValueError, TypeError):
        raise TibberError("Vehicle snapshot response could not be decoded") from None
