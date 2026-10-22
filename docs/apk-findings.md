# Tibber Android investigation â€” 2026-10-22

User-supplied APK: package `com.tibber.android`, version `26.40.0`, code
`2640004`. SHA-256:
`12e88e1de9742c138bf83dd1b64eb9bb8def37e9c77ff3ee88d7c792a109e126`.

Extracted v2 signer certificate SHA-256:
`36608a988441269bcf7299a0da96d7cd7f948f5e3c1a1f53b140ecf7066708f8`.
This is an identifier, not verification against a trusted Tibber release.

## Static evidence

The DEX string table contains Apollo GraphQL documents:

* `SetVehicleSettings(vehicleId: String!, homeId: String!, settings:
  [SettingsItemInput!])` calls `me.setVehicleSettings`.
* `SetVehicleChargerSettings` calls
  `me.home(id: $homeId).setVehicleChargerSettings` with explicit charger ID.
* Charging fragment includes `departureTimes { weekday time { hours minutes } }`
  and `targetedDepartureTime`.
* Vehicle and charger fragments include `userSettings`, `settingsScreen` and
  `actionButtons { text enabled action type url redirect }`.
* Literal keys: `offline.vehicle.batteryLevel`, `smartCharging.isEnabled`.
* Navigation identifier: `vehicle-departure-times`. This is NOT established as
  an API setting key.

Androguard instruction inspection confirms
`com.tibber.network.vehicle.GatewayVehicleProvider.setSetting` creates one
`SettingsItemInput` and invokes `SetVehicleSettingsMutation`.
The analogous charger provider invokes `SetVehicleChargerSettingsMutation`.

The SoC key is also independently present in the existing community component:
https://github.com/Elibart-home/tibber_soc_updater

Further APK evidence: `vehicleStateSubscription($vehicleId: String!)` reads
`vehicleState(vehicleId: $vehicleId)`. The `GetMyVehicles` query reads
`me.myVehicles.vehicles`, whose `MyVehicle` fragment has `id`, `title` and
`isPaired` (not a `name` field). The discovery module uses these subsets.

Community protocol evidence for app login at `/v1/login.credentials`, JSON
email/password, WebSocket `/v4/gql/ws`, Authorization bearer header and empty
`connection_init` with `graphql-transport-ws`:
https://github.com/DG65/NRGTibberGridRewards/blob/main/TibberGridReward/module.php
These are protocol candidates, not live-verified account behavior. Offline
tests cover framing, ping/pong, selected vehicle identity and error handling.

`vehicle-departure-times` is used in `VehicleSettingViewModel.keyToTooltipContent`
as a substring match for server setting/group identifiers. It is not established
as the exact mutation key. REA 6.7.0/JADX successfully opened the APK; the attempted
method `SmartChargingViewModel.onDepartureTimesSettingsWanted` does not exist as
a standalone method in this optimized build. Its Kotlin label is insufficient
evidence to invent a callable method or API.

## Remaining verification

No exact departure write key/value encoding, weekday convention, timezone
semantics or pause/resume operation has yet been established. Server-provided
settings and action definitions may be necessary. Do not invent these values.
Nothing was sent to a live Tibber account during this investigation.

## Local analysis tools

Python 3.12 venv: httpx, pytest, pytest-asyncio and Androguard.
Node 24 and REA are installed under ignored `work/tools`.
Temurin JDK 21 is installed on Windows. JADX headless MCP 0.7.1 is in ignored
`work/jadx-headless-mcp.jar`; downloaded digest matches REA documentation:
`6e5eacf500b64292bfb73c49797c1958f6ee44646e43e868039ae7feb573ff75`.
REA is used through its CLI; no global agent MCP configuration was modified.
