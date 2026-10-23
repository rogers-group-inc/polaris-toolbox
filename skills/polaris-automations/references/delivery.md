# Delivery: what to hand the user, and how they put it in

Every answer carries the rule JSON, the wizard walkthrough and the dry run. This file covers
the API sequence, the wizard's on-screen names, the permissions and the testing surfaces.

## Permissions

| Gate | Grants |
|---|---|
| `automationManagement:read` | list rules, `GET /automations/schema`, `scope-options`, `recipient-users`, `dimension-values`, `poll-cadence`, `removal-impact`, `GET /delivery-channels` |
| `automationManagement:write` | create, edit, clone, delete, **`POST /automations/preview`**, test deliveries |
| `automationScripts:write` | **also** required to save a rule carrying a `script` action (403 otherwise) |
| `assets:write` | **also** required to save a rule carrying a `reboot` action (403 otherwise). Removing one never needs it |
| `contacts:read` | the Address Book tab and its search (the recipient typeahead's local half works without it) |
| `alerts:read` / `:write` / `:fullwrite` | see / acknowledge / clear alerts |

A bearer token is bound to a role. Its writes are audited as `api:<token name>`. Every create,
edit and delete writes an Event.

## The API sequence

All paths are under `/api/v1`. `/notification-rules` still works as a deprecated alias of
`/automations`.

1. **`GET /automations/schema`**: the vocabulary. Every metric, state field, comparator,
   aggregation, change type, action type and severity the server accepts, plus `metricMeta`, `fieldMeta`,
   `metricDimensions`, `fieldDimensions`, `templateVariables`, and the names behind ids a condition can carry:
   `stateProbes`, `pathChecks`, `customWidgets`. **Build against this, not against a list in a doc.**
2. **`GET /delivery-channels`**: the channel ids a notify action names.
   **`GET /automations/recipient-users`**: user ids for `recipientUserIds`.
   **`GET /automations/scope-options`**: manufacturers, models and IPAM networks a scope can name.
3. **`POST /automations/dimension-values`** `{ metric, dimension, scope }`: the values the
   scoped devices actually report for one dimension (interface names, sensor names, mounts,
   tunnels, state-probe rows), so a filter names a value that exists.
   **`POST /automations/poll-cadence`** `{ metric?, scope }`: how often those devices take the
   reading. Use it to say what `forPolls: N` means in wall-clock time.
4. **`POST /automations/preview`**: the dry run. It writes nothing. Send `{ "scope": {...} }` alone to list the
   devices selected. Send `{ "trigger": {...}, "scope": {...} }` to evaluate current readings. The answer:
   `{ supported, totalEvaluated, totalAssets?, unmonitoredCount?, meetsCount, matches, carveOut?, … }`.
   - `meetsCount` = readings meeting the trigger **now**. On a fresh threshold rule, a large number means the threshold is
     too low and it will page on save.
   - `carveOut` = devices a more specific rule already owns (they will not alert from this one).
   - `unmonitoredCount` = devices in scope that can never alert (rule 37).
   - Event and change triggers have no current reading and answer `supported: false`.
   - Pass `id` when previewing an edit, so the rule's carve-out excludes itself.
5. **`POST /automations`** with the full body and `"enabled": false`: **201** with `{ rule }`.
   A 400 names the failing field. Read the rule back and confirm every key survived, because unknown
   trigger and top-level keys are dropped without an error.
6. A human reviews the rule, then enables it with the list toggle in the UI, or with a `PUT` of the
   full rule carrying `"enabled": true`.

**Editing:** `GET /automations`, take the rule, change it, and **`PUT /automations/:id` the whole
body**. It is a full replace: omitted fields take their defaults, so a missing `enabled` turns
the rule on and a missing `reset` makes it manual-clear. Masked `api_call` headers sent back
unchanged keep their value only while that action's `url` is unchanged. 404 means the rule does not exist.

**Removing:** `GET /automations/:id/removal-impact` first if the trigger is
`monitorStatus == down` (`wouldBecomePassive` devices stop being declared down). Then
`DELETE /automations/:id` returns **204**, and its open alerts are cleared.

```bash
# Dry run, then create disabled. $POLARIS_TOKEN comes from the environment, never pasted into chat.
curl -s -X POST -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d @rule.json "https://<polaris-host>/api/v1/automations/preview"
curl -s -X POST -H "Authorization: Bearer $POLARIS_TOKEN" -H "Content-Type: application/json" \
  -d @rule.json "https://<polaris-host>/api/v1/automations"
```

## The wizard walkthrough

Automations → **+ New automation**. Seven steps. Any visited step can be revisited, and in edit mode all
are unlocked. **There is no enabled control in the wizard.** Enabling is the list's toggle.

| Step | On-screen controls to name | JSON it writes |
|---|---|---|
| **1 — Name** | name, description, **Import from file…** (create only; imports are created disabled) | `name`, `description` |
| **2 — Devices** | **All assets** checkbox (default checked). Untick it for the condition builder: AND / OR / NONE / NOT-ALL groups, field + operator + value rows, up to 5 deep. A live preview of matched devices | `scope` |
| **3 — Trigger** | severity at the top, **Trigger type** dropdown, the condition rows, **+ Condition** (filter rows: Device identifier, Component name, SD-WAN member IP address), the duration field (**Sustained for (polls)** / **Measured over** / **Poll Group Size** / **History (minutes)**), **Use multiple severity levels** → **+ Severity**, **Test against current data** | `severity`, `trigger`, `severityBands` |
| **4 — Reset** | **Reset when the trigger is no longer true** (default), the clear threshold (dead band), "must stay true for" in polls. Untick it for **Custom conditions**, timed or manual. Event rules show **When a matching event arrives** | `reset` |
| **5 — Actions** | **In-app Alert** card (message template, **Insert variable…**), **Require Acknowledgement**, **Dependency-Down Bypass** (down rules only), **Trigger Action** list (Notify / API call / Script / Create an Event / Reboot the device), **Repeat this action** on a notify, **+ Escalation Action**, **Stop escalating when**, **Use different actions for each severity level**, **Raise one alert per device, not one per …**, **Reset Action** list | `messageTemplate`, `requireAckNote`, `trigger.alertWhenDependencyDown`, `actions`, `escalation`, `bandNotify`, `groupByAsset`, `resetActions` |
| **6 — Quiet time** | **Off** / **Ignore Global Quiet Time** / **Override Global Quiet Time** (schedule editor, the **What goes quiet** tree, **Recipient exceptions…**) | `quietTime` |
| **7 — Summary** | review, **Export**, **View code**, **Test delivery**, and the *Devices this automation affects* preview with its specificity indicator and carve-out warning | — |

How the wizard's words map to the JSON:

- **Sustained for (polls)** is `forPolls`. On a sole `monitor status is down` condition it is
  `missedPolls` instead, and is required there.
- **Measured over** (minutes) is `windowSec`. **Poll Group Size** is `windowPolls`, and its
  **Sustained for (poll groups)** is `forPolls`.
- On the Devices step, a **Subnet / IP** row is `field: "subnet"` (`is within CIDR`, `is within range`,
  `is in subnet named` → `inCidr`, `inRange`, `inSubnetNamed`).
- **Asset's L1 Region Users** is `recipientDeviceRegionLevels: [1]`. **Asset's Region Users** is
  `recipientDeviceRegion: true`. **Asset's Responsible Contacts** is `recipientAssetContacts: true`.

## View code, Export, Import

- **View code** (Summary step, or the name menu) is the full-fidelity body, ids and headers
  included. It is the same JSON this skill emits, and its save is the same **full-replace PUT**:
  removing a key removes the setting.
- **Export** writes a portable `.automation.json` with a `dependencies` block first. Install-specific
  items are recorded **by name**: channels, scripts, state probes, roles, regions, tags,
  pinned devices. **`api_call`, `script` and `reboot` actions are stripped**, so an export carries no
  secret and an import can never name a script. After an import, the **Actions** step always needs attention.
- **Import from file…** (Name step, create only): the file's name becomes the rule's name, and the
  rule is created **disabled**.
- **Clone** names the copy `<name> (copy)` and creates it disabled, because same-rank twins both fire (rule 18).

## The toolbox scripts

Two scripts in the toolbox's `scripts/` wrap the API sequence (Python 3, standard library only;
`POLARIS_URL` + `POLARIS_TOKEN` or `--token-file`; `--insecure` for a self-signed lab cert):

```bash
python3 scripts/apply-automation.py firewall-cpu.rule.json --dry-run   # preview only
python3 scripts/apply-automation.py firewall-cpu.rule.json             # create (skips an existing name)
python3 scripts/apply-automation.py firewall-cpu.rule.json --update    # PUT over a rule of the same name
python3 scripts/export-automations.py --out ./rules --name "firewall"  # plain rule bodies, as .rule.json
```

`apply-automation.py` previews each rule (devices covered, readings meeting it now), then
creates it — a rule file may hold one body or a list. `export-automations.py` writes the stored
body minus id / timestamps / alert-group link, replaces every email address with a numbered
`<recipient-N@example.com>` placeholder, keeps `api_call` headers masked, and lists under
`_toolbox.remap` the per-install ids (channels, users, scripts, assets) to set on the target.
It is not the UI's Export (`.automation.json` with a dependencies block, actions stripped):
use the UI's for moving a rule between installs by NAME, the script's for review and version
control of the exact body.

## Testing

- **Test against current data** (Trigger step) and the Summary step's preview: devices, readings,
  carve-out. This is the UI face of `POST /automations/preview`.
- **Test delivery** (Summary step, `automationManagement:write`): one button per distinct delivery
  (*Send Test Email*, *Send Test Web Push*, *Write a Test Event*…). Each press creates a real `[TEST]`
  alert about a **made-up device** (rule 65), sent **to the person pressing it and nobody else**.
  It shows in Active Alerts with a TEST pill and clears itself after an hour. `api_call`, `script` and
  `reboot` are never offered. Slack, Teams and Pushbullet are tested from the **Delivery** tab instead.
- **`POST /automations/test-delivery` needs a signed-in session and returns 401 to a bearer token**:
  there is no user to deliver it to. Over the API, the dry run is `preview`. There is no API test send.

## Handing it over: a checklist

1. JSON with `"enabled": false`, every placeholder named, and a line saying where each id comes from.
2. If the trigger is `monitorStatus == down`, say that it defines Down for those devices, and run
   `removal-impact` on any rule it replaces.
3. The preview body, plus what `meetsCount` / `carveOut` / `unmonitoredCount` should look like.
4. The wizard steps, keyed to the table above.
5. What firing looks like: severity, who is told and when, escalation and reminders, when it clears,
   and who hears the all-clear (`resetActions`).
6. **Human review before enabling in production.** Real tokens, addresses and hostnames stay out of
   the chat and out of files. The operator types secrets into the wizard.
