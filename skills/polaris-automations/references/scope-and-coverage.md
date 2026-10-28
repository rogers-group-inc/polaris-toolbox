# Scope and coverage: which devices an automation can alert about

Wizard step **2 — Devices**. The trigger decides *what* counts as a problem. This file covers
*which devices* that can be true of, and the gates between "the condition is true" and
"an alert fires".

## Scope shapes

`scope` is a strict object. Its keys AND together, and the entries inside each list OR.

| Key | Matches |
|---|---|
| `allAssets: true` | every device. The wizard's default-checked **All assets** box |
| `assetTypes: [...]` | the asset type, exact |
| `tags: [...]` | any listed tag, case-insensitive. A `region:<name>` tag ranks as Region |
| `manufacturers` / `models: [...]` | case-insensitive **contains** |
| `subnetCidrs: [...]` | the primary IP inside any CIDR (a bare IP is a host route) |
| `assetIds` / `integrationIds: [...]` | exact ids. The builder no longer offers asset ids |
| `condition: { op, children }` | the nested builder tree. It is authoritative when present and ANDs with the flat keys |

**The empty scope trap.** For `asset_metric`, `asset_state` and `composite`, a scope with no
key set and no `allAssets` **selects no devices**. `scope: {}` saves fine and alerts on
nothing. Write `{ "allAssets": true }` or a condition. For `event` triggers, `{}`,
`{allAssets: true}` and a tree with no rules all mean **any device**. That difference is why an event
automation's scope is checked for being unconstrained before anything else. `host_metric` (and a host-kind
composite) ignores the scope.

### The condition tree

```json
"scope": { "condition": { "op": "and", "children": [
  { "field": "assetType", "operator": "equals", "value": "<asset-type>" },
  { "op": "or", "children": [
    { "field": "tag", "operator": "has", "value": "<tag-name>" },
    { "field": "subnet", "operator": "inSubnetNamed", "value": "<network-name-pattern>" } ] } ] } }
```

- Group `op`: `and`, `or`, `none` (no child holds), `notAll` (at least one child fails).
  At most 5 levels deep and 100 rules. Every rule needs a non-empty `value`.

| `field` | Operators |
|---|---|
| `assetType`, `status`, `assetId`, `agentInstalled` (`yes` / `no`) | `equals`, `notEquals` |
| `manufacturer`, `model`, `hostname`, `os`, `interfaceName`, `ssid` | `equals`, `notEquals`, `contains`, `notContains`, `startsWith`, `endsWith` |
| `tag` | `has`, `notHas` |
| `subnet` (**Subnet / IP**) | `inCidr` / `notInCidr` (CIDR or bare IP), `inRange` / `notInRange` (`a.b.c.d-a.b.c.e` or the short `a.b.c.d-e`, IPv4), `inSubnetNamed` / `notInSubnetNamed` (an IPAM network name, `*` / `?` wildcards, case-insensitive) |
| `ipBlock` | `inCidr`, `notInCidr` |

- `inSubnetNamed` follows the IPAM registry, so `Plant-*` also covers a network added later.
  Deprecated networks never match.
- `interfaceName` / `ssid` ask what the device *has* (any interface, any SSID). A device whose
  interfaces were never collected matches no positive rule.
- Values a scope can name (manufacturers, models, IPAM networks) come from
  `GET /automations/scope-options`. Device and contact filters elsewhere offer extra fields
  (`osVersion`, `department`, `location`, `fortigate`, the `matches` wildcard). **An automation's scope
  refuses those.**
- Check the real reach with `POST /automations/preview { "scope": {...} }`, which lists the devices it selects.

## The gate every alert passes (rule 37)

A device can raise an alert only when all three hold:

1. it is **`monitored`**;
2. it is **not in a maintenance window**;
3. it is **not dependency-suppressed** (Dep. Down). The one opt-out is below.

Consequences: un-monitoring a device clears its live alerts (`notification.out_of_scope`), and so does
leaving the scope. A deleted asset's `asset.deleted` event still fires. System events with no
asset id still fire on an unconstrained event rule. `POST /automations/preview` reports
`unmonitoredCount` for devices in scope that cannot alert.

## Precedence and carve-out (rule 18)

Two automations **watch the same thing** when their trigger signatures match. The signature is
the metric or state field plus its dimension filter, so a filtered and an unfiltered rule never
collide. Among those, the higher **specificity rank** removes its devices from every
lower-ranked rule:

```
All assets < Device type < OS < Manufacturer < Model < Tag < Region < IP block < Subnet < Hostname
```

- Rank is the most specific dimension a scope **positively** constrains. Negative operators
  and `none` / `notAll` groups never raise it. A Subnet / IP rule ranks as Subnet whichever
  operator it uses. `status`, `assetId`, `interfaceName` are not on the ladder.
- When a device is carved out of the lower rule, that rule's readings for it are dropped,
  its active alert is cleared as `notification.superseded`, and its pending hold is reset.
- **Same-rank ties both fire.** That is why the UI creates Clone and Import results
  disabled. An API copy of a rule should also start with `"enabled": false`.
- `event`, `change`, `host_metric` and `composite` triggers do not take part in carve-out.
- **`monitorStatus` is keyed by operator and value, not by device filter.** Every `== down`
  automation is in one group, so they carve each other out. The same resolution decides
  whose `missedPolls` governs each device.
- The preview's `carveOut` says which devices a more specific rule already owns. The Summary step
  shows both directions: whose devices this rule takes, and which of its own a more specific rule takes.

## Down detection

- **`monitorStatus == down` defines down** (rule 36). The covering automation's `missedPolls`
  is the threshold. A device that no down automation covers reads **`passive`**: still polled,
  sampled and charted, never judged, never alerted as down. Entering or leaving `passive` is a
  configuration change, not a state change.
- The failure bucket is a **leaky bucket with a ceiling** (rule 30). A miss adds 1, an answer
  subtracts 1. Reaching N locks the bucket at `max(missedPolls, recoveryPolls)`. Any answer reads
  `recovering`. Time to down is about N × interval for a dead device, and longer for one that flaps,
  because a missed poll also costs its timeout.
- The way back is the same automation's `reset.sustainPolls`: the device stays `recovering`
  until that many probes have answered. "Down after 3 missed, reset after 5 received" describes
  the status pill itself.
- An agent-reported host that goes quiet for two intervals counts a miss per interval, like
  a failed ping (rule 86). Polaris's own agent upgrades and reboots put the host in
  maintenance (rule 80), so those do not count.
- ICMP loss sweeps never move `monitorStatus`. Down is judged on the configured transport only.
- **Before disabling or deleting a down automation**, call
  `GET /automations/:id/removal-impact` → `{ isDownDetection, governs, wouldFallBackToAnother,
  wouldBecomePassive, sampleHostnames }`. `wouldBecomePassive` devices stop being declared
  down. A fleet with no down automation at all writes a one-off `monitor.down_detection_absent` warning Event.

## A device that goes down hands off its response-time and loss alerts (rule 29)

When a device is confirmed `down`, its open alerts on readings made of the outage clear as
*superseded*: `responseTimeMs`, `probeLossPct`, and the failing-minutes fields
(`telemetryFailingMinutes`, `systemInfoFailingMinutes`). No "resolved" is sent and no reset
actions run. Nothing new fires on those readings until the device comes back, then a still-bad
condition fires again once its hold is met. A composite hands off only when every condition in it
would.

Every other alert stays open through the outage: CPU, memory, `memForecastPct` /
`memDaysUntilFull` / `storageDaysUntilFull`, interfaces, sensors, SD-WAN, IPsec, FortiLink, path
checks, and held facts (`status`, `quarantined`, `firmwareVsPrimary`, `tag`,
`dependencySuppressed`). An open alert freezes while no readings arrive and resolves through its own
automation once the device reports healthy. So a CPU or SD-WAN alert open when its device goes dark
sits beside the down alert, and mails "resolved" after the device returns. Only a `down` device
counts: `passive`, `unknown` and `recovering` have no down alert to hand to.

## Maintenance windows (rule 16)

| | Effect |
|---|---|
| Polling | stopped for the device (a Polaris Agent and **Poll Now** still report) |
| New alerts | not raised for the device **or for dependency-suppressed children** |
| An open **device-down** alert | **cleared** within a minute (`system:maintenance`), no reset actions run. Still down afterwards means a new alert once `missedPolls` is reached |
| Every other open alert | **stays open, paused**. Escalation and reminders pause. When the window ends it is judged on fresh readings: it resolves normally (reset actions run) or carries on. A healthy reading taken during the window resolves it early |
| Children | the device counts as down for dependency suppression, unless the schedule's *suppress children* is off |

Polaris opens short windows itself for agent upgrade / reinstall / uninstall, firmware upgrades,
workload restarts and updates, and reboots it sends or an automation books (rule 80). Event
automations judge an event against the device's maintenance history **at the moment the event
happened** (rule 80a), so a window that lasted two seconds still suppresses.

## Dependency suppression

- A device whose every effective parent is **confirmed down** is **Dep. Down**. It is excluded
  from firing, its probe failures are drawn grey, and it keeps being probed at its normal
  interval, so its own count is current when the parent returns (rule 38).
- Entering needs every parent `down`. Leaving needs the parent `up`, `unknown` or `passive`:
  `warning` and `recovering` keep the subtree held.
- Live alerts on a suppressed device are retired when the upstream is genuinely down. Behind a
  parent that is **in maintenance**, its device-down alert is cleared and every other alert is
  kept, paused.
- **Dependency-Down Bypass** (`alertWhenDependencyDown: true`, valid only on a lone
  `monitorStatus == down` trigger, rule 78): this automation alerts the moment the device turns
  Dep. Down, says **DEPENDENCY DOWN**, and names the upstream device that is actually down. It is
  one notification: reminders and escalation wait until the upstream is back. Acknowledging the
  root cause's own Down alert acknowledges it (rule 78a). A maintenance window still silences it.

## Quiet time is not coverage

Quiet time never stops an alert from being raised. See
[actions-escalation-repeat.md](actions-escalation-repeat.md#quiet-time).

## Why didn't it fire?

Walk these in order and stop at the first that applies:

1. **Enabled?** The list toggle. A cloned or imported automation starts disabled.
2. **Scope empty?** `{}` on a device trigger selects nothing. Run the preview with the scope alone.
3. **Monitored?** Unmonitored devices never alert (`unmonitoredCount` in the preview).
4. **Maintenance or Dep. Down?** Check the device's status pill: Maintenance, Dep. Down or Dependency Test.
5. **Carved out?** A more specific automation on the same signature owns the device (preview `carveOut`).
6. **No reading?** An unpinned interface or tunnel (rule 57), a sensor with no alarm bit, a
   filesystem that is not growing, a host with no per-core CPU, a stream that is never polled, a
   `fortilinkStatus` / `firmwareVsPrimary` that cannot be placed. Use `POST /automations/dimension-values`.
7. **Pattern matches nothing?** A typo in `ifNamePattern`, `sensorNamePattern`, `mountPathPattern` or `tunnelName`.
8. **Hold not met?** `forPolls` counts readings at the device's cadence. `windowPolls` groups must
   fill first. A down device produces no other alerts.
9. **Superseded?** The device went down (rule 29), a `cpuPct` alert exists (for `cpuCorePct`), or an
   SD-WAN underlay is over the line (rule 90).
10. **Event filters?** A filtered event rule never fires on an event with no asset. `minLevel`
    or `detailsMatch` may exclude the event. The `cooldownSec` may not have elapsed.
11. **It fired but nobody heard.** Quiet time held the send (QUIET pill). The notify action has no
    To, a recipient has no push device, an alert group overrides its recipients, or there were no
    actions at all (in-app only).

## Why did it fire?

- A **same-rank twin** (a clone, or an API copy) is also enabled. Both fire.
- No clear threshold, so a reading sitting on the line re-alerts. Add `reset.clearThreshold`.
- The hold is shorter than expected in wall-clock time because the device is polled faster than
  assumed. Check `POST /automations/poll-cadence`.
- A `poeStatus == fault` rule covers unpinned ports by design.
- An alert during a maintenance window was raised before the window opened. It was paused, not
  cleared, and resumes afterwards.
