# Responsibility boundaries

## TibberLib (this repository)

Transport, authentication, typed/validated inputs, reading account vehicles and
server settings, and operations supported by collected API evidence. No calendars,
SoC mapping or decisions about when the car should charge.

## TibberHA (separate repository)

Home Assistant config flow, credentials, account/vehicle selection, connection
health and actions. Reuses TibberLib. No duplicate Renault/Easee polling. Read-only
discovery comes before enabling any unverified setting mutation.

## HA automation (user-visible charging policy)

Use the existing Renault SoC, connection and Home signals. Charger association
must be explicit: two connected Easees do not identify which contains the Zoe.

* Plug-in below 40%: write `floor(real_soc) + 60` once; set the next weekday
  departure at 06:00 local Europe/Stockholm time once.
* Plug-in at/above 40%: report real SoC once; remove the managed departure.
* First reaching 40% during that session: remove the managed departure and report
  real SoC once. No continuous SoC writes while charging.
* Unplug: end the managed session; never infer a new plug-in from HA restart.
* Restore persisted session state after restart, reconcile incomplete operations
  without blindly repeating unknown-outcome writes. Distinguish actual disconnect
  from unavailable. Do not advance a missed deadline to tomorrow silently.
* Weekdays currently mean Monday-Friday, not Swedish public holidays. Calendar
  support can be added later if requested.

Tibber retains all price/charging scheduling. No HA charge-now fallback, no
automatic Easee commands and no 80% stop in this policy. The older 80% automation
must be reviewed before deployment to avoid conflicting control.

## Deployment gates

Still required: live read-only account verification; exact departure key, value
encoding and clear semantics; timezone/weekday mapping; authenticated write and
read-back tests; actual HA integration runtime tests; observed plug-in/40%
transitions; morning outcome. Mock tests cannot establish these facts.
