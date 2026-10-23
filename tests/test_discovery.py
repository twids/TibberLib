import json

import httpx
import pytest

from tibberlib import TibberError
from tibberlib import discovery


async def test_login_handles_special_characters_without_form_concatenation():
    def handle(request):
        assert request.url.path == "/v1/login.credentials"
        assert json.loads(request.content) == {"email": "a+b@example.org", "password": "x&y=z"}
        return httpx.Response(200, json={"token": "test-token"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert await discovery.login(http, "a+b@example.org", "x&y=z") == "test-token"


@pytest.mark.parametrize("payload", [{"token": None}, {"token": 123}, []])
async def test_bad_login_reply(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=payload)
    )) as http:
        with pytest.raises(TibberError):
            await discovery.login(http, "email", "secret")


async def test_vehicle_list_uses_title_not_unverified_name_field():
    def handle(request):
        assert "id title isPaired" in json.loads(request.content)["query"]
        return httpx.Response(200, json={"data": {"me": {"myVehicles": {
            "vehicles": [{"id": "zoe", "title": "Zoe", "isPaired": True}]
        }}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        assert (await discovery.list_vehicles(http, "secret"))[0]["title"] == "Zoe"


class Socket:
    def __init__(self, vehicle):
        self.sent = []
        self.messages = iter([
            {"type": "ping"}, {"type": "connection_ack"},
            {"id": "vehicle", "type": "next", "payload": {"data": {"vehicleState": vehicle}}},
        ])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def send(self, message):
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self.messages))
        except StopIteration:
            raise StopAsyncIteration


async def test_snapshot_subscription_is_read_only_and_closed(monkeypatch):
    socket = Socket({"id": "zoe", "userSettings": []})
    def connect(url, **kwargs):
        assert url == "wss://app.tibber.com/v4/gql/ws"
        assert kwargs["subprotocols"] == ["graphql-transport-ws"]
        return socket
    monkeypatch.setattr(discovery, "connect", connect)
    assert (await discovery.read_vehicle("secret", "zoe"))["id"] == "zoe"
    assert [item["type"] for item in socket.sent] == [
        "connection_init", "pong", "subscribe", "complete"
    ]
    assert socket.sent[2]["payload"]["query"].startswith("subscription")


async def test_wrong_vehicle_is_rejected(monkeypatch):
    monkeypatch.setattr(discovery, "connect", lambda *a, **kw: Socket({"id": "other-car"}))
    with pytest.raises(TibberError, match="ID mismatch"):
        await discovery.read_vehicle("secret", "zoe")


@pytest.mark.parametrize("error,expected", [
    (TimeoutError("secret"), "timed out"),
    (OSError("secret"), "network connection failed"),
    (ValueError("secret"), "could not be decoded"),
])
async def test_snapshot_errors_are_specific_but_do_not_leak_details(monkeypatch, error, expected):
    def connect(*args, **kwargs):
        raise error
    monkeypatch.setattr(discovery, "connect", connect)
    with pytest.raises(TibberError, match=expected) as caught:
        await discovery.read_vehicle("secret", "zoe")
    assert "secret" not in str(caught.value)
