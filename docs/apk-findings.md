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

### Departure encoding evidence (additional investigation)

Authenticated HA discovery succeeded. For the user's offline Zoe, server settings
include `offline.vehicle.departureTimes.<weekday>` for all seven English weekday
names and `offline.vehicle.smartCharging.isEnabled` (boolean, true). The user set
Friday 06:00 in the iPhone app; a fresh HA inspection returned Friday `06:00`.
Other days return a localized display value (`No departure time`), while the
structured charging fragment returns `time: null`. Do NOT send display text.

REA/JADX analysis of this APK established:

* `com.google.android.gms.dynamite.zzf.mapSettingToEditableSettingListItem` creates
  a TimePickerItem using callback class ID 18 of
  `com.tibber.graphs.ui.pager.GraphPageIndicatorKt$$ExternalSyntheticLambda1`.
* That callback formats selected hour/minute as `%02d:%02d:00` with Locale.ROOT
  and passes it to the setting-update callback.
* The mapper's turn-off callback reaches
  `BaseSettingsViewModel$$ExternalSyntheticLambda1` class ID 0, which creates
  `EditedSetting(key, null)`.
* `BaseSettingsViewModel.saveSetting()` passes that same `newValue` to
  `getOnSettingsUpdate().invoke(key, newValue)` without display-text conversion.

The library now encodes local minute-precision times as `HH:mm:00` and clear as
JSON null using the existing SetVehicleSettings mutation. These writes still
require live write/read-back verification. No account IDs or raw account replies
are published here.

Departure write key/encoding is now supported by the above static/live-read
evidence. Home timezone and actual next-departure behavior, clear/write read-back
and pause/resume still require live verification. Account login, vehicle listing
and snapshots were read successfully through HA; no writes were made at this stage.

## Local analysis tools

Python 3.12 venv: httpx, pytest, pytest-asyncio and Androguard.
Node 24 and REA are installed under ignored `work/tools`.
Temurin JDK 21 is installed on Windows. JADX headless MCP 0.7.1 is in ignored
`work/jadx-headless-mcp.jar`; downloaded digest matches REA documentation:
`6e5eacf500b64292bfb73c49797c1958f6ee44646e43e868039ae7feb573ff75`.
REA is used through its CLI; no global agent MCP configuration was modified.
