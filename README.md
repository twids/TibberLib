# TibberLib

Unofficial async Python library for Tibber's private app API, intended as a
building block for a Home Assistant custom integration.

## Current boundary

Implemented: explicit vehicle/home IDs and integer SoC updates (0â€“100).
GraphQL, HTTP and malformed-response errors propagate to the caller.
Writes are not automatically retried and redirects are not followed.

Experimental read-only discovery includes app login, vehicle listing and a first
vehicle snapshot over GraphQL WebSocket. These protocols still require live
account verification. Token refresh, departure-time writes, pause/resume and
charger discovery are not implemented. HA setup lives in the separate TibberHA
repository. No live account calls have been tested. A successful API response does not
prove a charging plan changed or charging stopped.

```python
import httpx
from tibberlib import TibberClient

# Obtain an APP token securely; the public developer token is a different API.
async def app_token_provider():
    return await your_secure_token_store.get_app_token()

async def update_soc():
    async with httpx.AsyncClient() as http:
        client = TibberClient(http, app_token_provider)
        await client.set_vehicle_soc(
            vehicle_id="YOUR_ZOE_ID", home_id="YOUR_HOME_ID", battery_level=80
        )
```

HA should own credentials, data freshness, vehicle-to-charger association and
any SoC mapping. The agreed one-shot `min(real_soc + 60, 100)` policy below 40%
is deliberately outside this library. Tibber retains scheduling control. That mapping is an
experiment, not a guarantee of 40% by departure or Grid Rewards eligibility.

## Development (PowerShell)

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e '.[test]'
./.venv/Scripts/python.exe -m pytest -q
```

See [APK findings](docs/apk-findings.md) for evidence and remaining questions,
and [architecture](docs/architecture.md) for repository/automation boundaries.
APK files, tokens, account responses and local tools must not be committed.
