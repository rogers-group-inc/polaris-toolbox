# Triggers and conditions

Wizard step **3 — Trigger**. Severity is chosen at the top of the step, then the **Trigger
type** dropdown, which groups the kinds as *Device conditions* (asset metric, asset state,
and trees of them), *Path Monitor*, *Polaris host conditions*, *Audit event match* and
*Change detection*. Always read `GET /automations/schema` for the install's live vocabulary.
The lists below are what the server accepted when this was written.

## The six stored shapes

| `type` | Shape (required keys **bold**) | Scoped to devices? |
|---|---|---|
| `asset_metric` | **`metric`**, **`operator`**, **`threshold`**, `aggregation`, `windowSec`, `windowPolls`, `forPolls`, `dimensionFilter`, `ignoreAtOrAbove`, `includeServer` | yes |
| `asset_state` | **`field`**, **`operator`**, **`value`** (string / number / boolean), `forPolls`, `dimensionFilter`, `missedPolls`, `alertWhenDependencyDown` | yes |
| `host_metric` | **`metric`**, **`operator`**, **`threshold`**, `aggregation`, `windowSec`, `windowPolls`, `forPolls` | **no**: the scope is discarded |
| `event` | **`actionPattern`** (glob), `resourceType`, `minLevel`, `detailsMatch` | yes, the filter applies to the event's **subject** (rule 46) |
| `change` | **`changeType`**, `dimensionFilter`, `includeServer` | yes |
| `composite` | **`kind`** (`asset` \| `host`), **`op`** (`and` \| `or`), **`children`**, `forPolls` | yes (`asset` kind) |

**Comparators:** `>` `>=` `<` `<=` `==` `!=`. **Aggregations:** `latest` (default) `avg`
`median` `min` `max`. **Severities:** `notice` `informational` `warning` `serious` `critical`.

Path Monitor automations are stored as `asset_metric` (a `path*` metric) or `change`
(`path_check_path_changed`). The wizard files them under their own category.

## Asset metrics (`asset_metric.metric`)

| Metric | Unit | Dimensions (`dimensionFilter` keys) |
|---|---|---|
| `cpuPct` | % | — |
| `cpuCorePct` | % | — (one alert per device naming the hot cores; hold counted **per core**, rule 89) |
| `memPct` | % | — |
| `memUsedBytes` | bytes | — |
| `memDaysUntilFull` | days | — (one reading per device; a forecast, see below) |
| `sessionCount` | — | — |
| `responseTimeMs` | ms | — |
| `uptimeSec` | sec | — |
| `probeLossPct` | % | — (windowed ratio, see below) |
| `hwSensorValue` | the sensor's unit | `sensorClass`, `sensorNamePattern` |
| `hwSensorAlarm` | 0/1 (1 = Alarm) | `sensorClass`, `sensorNamePattern` |
| `storageUsedPct` / `storageUsedBytes` | % / bytes | `mountPathPattern` |
| `storageDaysUntilFull` | days | `mountPathPattern` |
| `ifInErrorRate` / `ifOutErrorRate` | errors/s | `ifNamePattern` |
| `ifInBps` / `ifOutBps` | bps | `ifNamePattern` |
| `sdwanLatencyMs` / `sdwanJitterMs` / `sdwanPacketLoss` | ms / ms / % | `healthCheck`, `link` |
| `ipsecThroughputBps` | bps | `tunnelName` |
| `customWidgetValue` | the widget's | `widgetId` |
| `customStateValue` | 0/1 | `stateProbeId`, `stateRowPattern` |
| `pathOk` / `pathLatencyMs` / `pathFailurePct` / `pathHttpStatus` / `pathHopCount` / `pathTlsDaysLeft` | 0/1 / ms / % / — / hops / days | `checkId` |

- **0/1 metrics** (`hwSensorAlarm`, `customStateValue`, `pathOk`) take `==` / `!=` against
  `1` or `0`. They refuse severity bands and a clear threshold. In the wizard the threshold box becomes the
  probe's own two labels ("Alarm" / "OK").
- **Prefer `hwSensorAlarm`** over inventing a threshold on `hwSensorValue` (rule 24). The
  device knows its own per-model limits. A source with no alarm bit is excluded, never read as 0.
- **`cpuCorePct`** only fires on hosts that report per-core figures: the Polaris Agent, vCenter, and
  Unraid / TrueNAS hosts. While the device has an open `cpuPct` alert from any automation, the
  per-core alert stays quiet or clears as *superseded*.
- **`storageDaysUntilFull`** is a forecast. A filesystem that is not growing produces no reading.
- **`memDaysUntilFull`** is the memory twin: the 30-day trend of the daily average memory in use
  (% of installed), projected to 100%. It needs at least 7 daily points; a host whose memory is flat,
  shrinking or new produces no reading. Use `<=`, e.g. `<= 14`. Aggregation and a poll hold add nothing —
  it moves about once a day. The number matches the forecast headline on the asset's Memory chart.
- **`customStateValue`** needs `dimensionFilter.stateProbeId` (an id from `/schema` →
  `stateProbes`). `stateRowPattern` matches the row's *label*, and blank means every row, one alert each.
  **`customWidgetValue`** needs `widgetId` (from `/schema` → `customWidgets`). **`path*`**
  take `checkId` (from `/schema` → `pathChecks`). Blank means every check, one alert each.

### Packet loss (`probeLossPct`)

- A **windowed ratio**: the window *is* the reading. State it as `windowSec` (default 15 min,
  minimum 5 min, the wizard's **History (minutes)**). An aggregation does not apply. An optional
  `forPolls` hold sits on top.
- Only devices that are answering (`up` / `warning`) report loss. The failures of an outage
  (a run of misses that reached `down`) are excluded from the metric (rule 29).
- `ignoreAtOrAbove` (0–100, default 100): a reading at or above it is not a reading at all,
  and it clears this rule's alert on that device. Set 90 to avoid a loss alert trailing every outage.
  It applies to packet loss only.

## Asset state fields (`asset_state.field`)

**Device-wide:** `monitorStatus`, `status`, `consecutiveFailures`, `dependencySuppressed`,
`quarantined`, `fortilinkStatus`, `firmwareVsPrimary`, `telemetryFailingMinutes`,
`systemInfoFailingMinutes`, `tag`.
**Per component:** `ifOperStatus`, `ifAdminStatus`, `ifIpAddress`, `poeStatus`,
`ipsecStatus`, `sdwanRuleStatus`, `sdwanSelectedMember`, `sdwanMemberState`.

| Field | Values | Notes |
|---|---|---|
| `monitorStatus` | `up` `warning` `recovering` `down` `passive` `unknown` | `warning` is shown as **Missed**. `== down` is the down-detection automation, below |
| `status` | `active` `maintenance` `decommissioned` `storage` `disabled` `quarantined` | lifecycle |
| `consecutiveFailures` | number | "Missed polls outstanding". It is a leaky bucket, not a run (rule 30) |
| `dependencySuppressed`, `quarantined` | `true` / `false` | |
| `fortilinkStatus` | `up` `down` `unknown` | the parent FortiGate's view of the FortiLink / CAPWAP link (rule 59). "Stopped seeing it at all" is `!= up` |
| `firmwareVsPrimary` | `current` `older` `newer` | against the Repository's primary image (rule 87). The usual rule is `!= current` |
| `telemetryFailingMinutes` / `systemInfoFailingMinutes` | minutes | how long that stream's polls have failed (rule 118). The usual rule is `>= 60`. A stream that is never polled gives no reading |
| `tag` | a tag name | `==` / `!=` only. The value is the bare tag name; a region keeps its `region:` prefix |
| `ifOperStatus` / `ifAdminStatus` | the port's status (e.g. `down`) | only **pinned** ports. `ifOperStatus` reads only admin-up ports |
| `ifIpAddress` | an address string | `==` / `!=`. `!= 0.0.0.0` means "the port has an address" |
| `poeStatus` | `disabled` `searching` `delivering` `fault` `test` `other-fault` | `== fault` covers **every** PoE port, pinned or not. Other forms are pinned-only. Ports with PoE disabled are skipped |
| `ipsecStatus` | the tunnel status | pinned tunnels only. Name one in `dimensionFilter.tunnelName` |
| `sdwanMemberState` | `up` `down` | per health check × member. Overlays stay quiet while their underlay is over the line (rule 90) |

Interface conditions match `ifNamePattern` against the port's **name or description**. Several
terms joined by `|` match any of them (rule 124), e.g. `"wan1 | ATT EPLS"`.

### `monitorStatus == down`: the down-detection automation

```json
"trigger": { "type": "asset_state", "field": "monitorStatus", "operator": "==", "value": "down", "missedPolls": 3 }
```

- `missedPolls` (1–100) **is the definition of down** for every device this automation covers
  (rule 36). The wizard shows it in the **Sustained for (polls)** field when this is the only
  condition. Do not add `forPolls` on top, because the count already is the hold. If it is absent,
  the default is 3.
- `missedPolls` and `alertWhenDependencyDown` are **refused** anywhere else: on another field,
  comparator or value, and inside a multi-condition composite.
- `alertWhenDependencyDown: true` is the wizard's **Dependency-Down Bypass** (rule 78). See
  [scope-and-coverage.md](scope-and-coverage.md#dependency-suppression).
- Precedence picks which down automation governs a device. Same-rank ties go to the **smaller
  count**, then the older rule, then the lower id.
- Its severity is the colour of Down on charts and in alert emails.

## Event triggers

```json
"trigger": { "type": "event", "actionPattern": "agent.disconnected", "minLevel": "warning" }
```

- `actionPattern`: a glob over the audit Event's action (`capacity.*`). `minLevel`: `info` /
  `warning` / `error`. `resourceType`: an optional narrowing.
- `detailsMatch`: `{ "<detail key>": "<value>" }`. Every pair must hold, compared as text.
  This makes a rule directional (`"direction": "escalated"` on `capacity.severity_changed`).
  The keys are the ones an event shows in its details on the **Events** page.
- A **filtered** event automation never fires on an event that names no asset (an integration,
  a user, the host) or on one whose asset is already deleted. Leave such rules unconstrained.
- Event and change triggers take a `timed`, `manual` or `event` reset, never `auto` /
  `condition`. Known counterparts: `agent.disconnected` → `agent.connected`;
  `agent.upgrade_failed` / `agent.upgrade_skipped` → `agent.upgrade_succeeded`;
  `agent.install_failed` → `agent.installed`; `agent.uninstall_failed` → `agent.uninstalled`;
  `agent.build.failed` → `agent.build.completed`; `integration.discover.error` →
  `integration.discover.completed`; `platform.lifecycle_changed` →
  `platform.lifecycle_recovered`; `capacity.severity_changed` → `capacity.severity_recovered`.

## Change triggers (`change.changeType`)

`lldp_neighbor_added`, `lldp_neighbor_removed`, `process_started`, `process_stopped`,
`sdwan_failover`, `mclag_peer_lost`, `wireless_station_connected`, `firmware_changed`,
`switch_port_changed`, `wireless_ap_changed`, `gateway_firewall_changed`, `fortilink_changed`,
`path_check_path_changed`. A change fires on each instant. To alert *while* a link is down, use the
`asset_state` field instead: it has a reading, so it gets a hold and an auto reset.

## Host metrics (`host_metric.metric`)

`cpuPct`, `memUsedPct`, `memUsedBytes`, `loadAvg1`, `loadAvg5`, `loadAvg15`, `procRssBytes`.
These describe the Polaris server itself. A reading is taken every 30 s, so `forPolls: 4` is about 2 minutes.

## Holds, windows and poll groups

| You want | Write | Wizard field |
|---|---|---|
| "true on N consecutive readings" | `aggregation: "latest"` + `forPolls: N` (0–100) | **Sustained for (polls)** |
| "average over the last M minutes" | `aggregation: "avg"` (or median/min/max) + `windowSec` | **Measured over** (minutes) |
| "average of each group of K polls, K-groups in a row" | aggregation + `windowPolls: K` (1–100) + `forPolls: G` | **Poll Group Size** + **Sustained for (poll groups)** |
| packet loss over M minutes | `windowSec` (no aggregation) + optional `forPolls` | **History (minutes)** |
| down after N misses | `missedPolls: N` on `monitorStatus == down` | **Sustained for (polls)** |

- The engine counts **readings**, not ticks (it ticks every 60 s). On a device polled every
  5 minutes, `forPolls: 3` is about 15 minutes. `POST /automations/poll-cadence { metric, scope }`
  returns the real cadence so you can say what N polls means in wall-clock time.
- **Poll groups do not overlap** (rule 66). Time to alert = group size × sustained, e.g.
  `windowPolls: 10, forPolls: 3` at 60 s is 30 minutes. A group has to fill before it reads anything.
- A `windowSec` window floats with availability: misses write no value, so a lossy device
  is averaged over whatever answered. Poll groups fix the sample size instead.
- **Response time** in a poll group counts a missed poll as the device's probe timeout, and going
  Down resets the group. A recovered device is quiet until a group refills.
- With `windowSec`, the engine fetches at least 15 minutes of samples, so a window under 15
  minutes is really measured over 15.
- Choosing `avg` / `median` / `min` / `max` without a window is refused by the wizard. Always
  state one in API bodies too.
- `forDurationSec` / `windowSec` are also written as wall-clock mirrors by the wizard. A rule
  that carries only seconds keeps the old time-based behaviour.

## Dimension filters (`dimensionFilter`, strict)

Component keys: `ifNamePattern` (≤ 1000, `|` list), `sensorClass` (`temperature` `fan`
`voltage` `current` `optical` `poe` `power` `disk` `other`), `sensorNamePattern`,
`mountPathPattern`, `sdwanRulePattern`, `healthCheck` / `link` (≤ 1000, `|` lists),
`sdwanMemberIp` (`"== <ip>"` or `"!= <ip>"`, SD-WAN member conditions only, rule 98),
`tunnelName`, `widgetId`, `processNamePattern`, `stateProbeId`, `stateRowPattern`, `checkId`.

Device-identifier keys (valid on every asset metric / state leaf): `hostnamePattern`,
`ipPattern` (CIDR, octet-boundary prefix or exact, never a bare substring), `macPattern`
(separator-insensitive), `manufacturerPattern`, `modelPattern`. The wizard writes these from
**+ Condition → Device identifier** filter rows.

- `*Pattern` values are case-insensitive **substrings**. Blank means every component, one alert each.
- A pattern that matches nothing saves cleanly and then never fires. List what the devices actually report with
  `POST /automations/dimension-values { metric, dimension, scope }` before you write one.
- Dimension filters are part of the **trigger signature**, so two automations on the same metric
  with different filters never carve each other out.

## Composite (multi-condition) triggers

```json
"trigger": { "type": "composite", "kind": "asset", "op": "and", "forPolls": 3,
  "children": [
    { "type": "asset_metric", "metric": "cpuPct", "operator": ">", "threshold": 90 },
    { "type": "asset_metric", "metric": "memPct", "operator": ">", "threshold": 90 } ] }
```

- At most 3 levels deep and 10 leaves. Groups are `{ op, children }` with `and` / `or` only (no NOT at
  trigger level; use the inverse comparator). A composite needs **2 or more leaves**. A single
  leaf is collapsed to a plain trigger at save.
- Leaves are `asset_metric` / `asset_state` (kind `asset`) or `host_metric` (kind `host`),
  never mixed. Path conditions cannot be mixed with device conditions. Event and change cannot be leaves.
- **One hold for the whole tree** (`forPolls` on the composite). Leaf `forPolls` is stripped.
- Evaluated **per device**. A multi-component leaf counts as met when *any* component meets it,
  and the rule raises one alert per device. `groupByAsset` is refused because there is nothing to fold.
- Composite automations do not take part in precedence carve-out.
- A leaf `dimensionFilter.hostnamePattern` lets one tree mix device-specific branches
  ("wan1 down on one switch **or** /backup full on one server").

## Path Monitor (brief)

Path metrics watch only devices with an active Polaris Agent: the scope is ANDed with
"Polaris Agent installed". `includeServer: true` also watches the Polaris server's own runs
of a check. It cannot be combined with a `condition` reset. The alert is about the **host that
ran the check**, and path results never change that host's Up / Down status.
