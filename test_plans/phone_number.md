# `sw numbers` Test Plan

Retargeted from the pre-merge `phone_number` command to the registry-generated
`sw numbers` group. The old plan tested a surface that no longer exists
(`phone_number list --id`, `--short`, one flag per handler field); this one
tests what ships.

## Prerequisites

- A profile that resolves: `sw whoami` prints a project and space.
- At least three phone numbers in the project, with **at least one named** and
  **at least one left unnamed**, so the handle-resolution cases are reachable.
- At least one number on each of two different `call_handler` values, so the
  routing expansion has something to show.
- A validated E911 address in the project for section 7 (`sw addresses list`).
- Network access to any external webhook URL a number points at — `get --full`
  fetches those.

```bash
# Snapshot before you start. Everything here is restorable from this file.
sw numbers list --json > /tmp/numbers-before.json
```

## What changed, and what to pay attention to

| Change | Where it shows |
| --- | --- |
| `get` accepts a number or a friendly name, not just a uuid | §2 |
| `update`, `release` and the E911 extras accept the same handles | §5, §6, §7 |
| `get` prints a field/value table by default; `--json` is the wire form | §3 |
| `list --match` filters by number or name, server-side | §4 |
| `get --full` follows the routing to the SWML/cXML it points at | §8 |
| `call_handler` accepts 13 values, not 9 | §5, TC-042 |

---

## 1. Shape and help

```bash
# TC-001: the group lists eight commands and no verb-first aliases
sw numbers --help

# TC-002: every id-taking verb advertises the handles it accepts
sw numbers get --help                  # expect: {ID|NUMBER|NAME}
sw numbers update --help               # expect: {ID|NUMBER|NAME}
sw numbers release --help              # expect: {ID|NUMBER|NAME...}
sw numbers assign-e911-address --help  # expect: {ID|NUMBER|NAME}
sw numbers remove-e911-address --help  # expect: {ID|NUMBER|NAME}

# TC-003: --match names the fields it searches
sw numbers list --help                 # expect: "Searches number, name."

# TC-004: --full is documented on get and absent where no routing is declared
sw numbers get --help                  # expect: --full, and the paragraph about it
sw queues get --help                   # expect: no --full

# TC-005: --json and --profile are per-command, not on the root
sw numbers list --json --profile default    # works
sw numbers list --profile default --json    # works, order is irrelevant
sw --json numbers list                      # usage error, on purpose

# TC-006: unique prefixes resolve at both levels
sw num li -n 3
sw numbers re                          # ambiguous: release / remove-e911-address
```

**Expect** TC-006's second line to name both candidates and exit 2, not to guess.

---

## 2. `get` by id, number and name

```bash
# TC-007: by uuid (the only form the old CLI took)
sw numbers get <phone_number_id>

# TC-008: by E.164
sw numbers get +15551234567

# TC-009: without the country code
sw numbers get 5551234567

# TC-010: as a person writes it down
sw numbers get "(555) 123-4567"
sw numbers get 555-123-4567

# TC-011: by friendly name, exactly
sw numbers get "Fax Number"

# TC-012: by friendly name, different case
sw numbers get "fax number"

# TC-013: an exact name wins over a longer name it is a prefix of
#   set up: name one number "Support" and another "Support overflow"
sw numbers update <id-a> --set name=Support
sw numbers update <id-b> --set "name=Support overflow"
sw numbers get Support                 # must resolve to <id-a>, not report ambiguity

# TC-014: an ambiguous handle names the candidates and changes nothing
sw numbers get 555                     # expect exit 2 + a candidates table

# TC-015: a handle that matches nothing falls through to the API's own 404
sw numbers get "no-such-number"

# TC-016: a uuid costs no lookup
#   run with a proxy or -v if available; there must be exactly one request
sw numbers get <phone_number_id>
```

**Expect** TC-014 to print `error: '555' matches N phone numbers` followed by a
table of every candidate with its full id. **Expect** TC-016 to issue a single
`GET /api/relay/rest/phone_numbers/<id>` — an id-shaped identifier must not
trigger a list scan.

---

## 3. `get` output

```bash
# TC-017: default is a field/value table, not raw JSON
sw numbers get +15551234567

# TC-018: --json is the wire form, unchanged
sw numbers get +15551234567 --json | jq .call_handler

# TC-019: unset and empty are distinguishable
sw numbers get +15551234567            # a null field reads "-", an empty string reads ""

# TC-020: timestamps are local and name their zone
sw numbers get +15551234567            # created_at reads e.g. 2024-05-21 12:11:07 EDT
sw numbers get +15551234567 --json     # ...and stays 2024-05-21T16:11:07Z here

# TC-021: a long value folds rather than being truncated
sw numbers get <a number with a long message_request_url>
```

**Expect** TC-021's URL to be readable in full — an elided URL ending in `…`
cannot be pasted anywhere and is the bug this replaced.

---

## 4. `list` and `--match`

```bash
# TC-022: plain listing
sw numbers list
sw numbers list -n 1                   # same columns as the full list, one row

# TC-023: match on a number fragment
sw numbers list --match 555
sw numbers list -m 555                 # short flag

# TC-024: match on a name fragment, case-insensitively
sw numbers list -m fax
sw numbers list -m FAX

# TC-025: match spanning both fields
sw numbers list -m 1                   # matches numbers and any name containing "1"

# TC-026: match with no hits is an empty table, not an error
sw numbers list -m zzzzzz

# TC-027: match composes with --json and --limit
sw numbers list -m 555 --json | jq 'length'
sw numbers list -m 555 -n 1 --json | jq 'length'   # expect 1

# TC-028: --match on a resource with no declared filters still works
sw sip list -m support
sw swml list -m test
```

**Expect** TC-023/TC-024 to be filtered by the platform (`filter_number`,
`filter_name`), and TC-028 to be filtered locally over the page `list` returned.
Both should look identical to the user.

---

## 5. `update`

```bash
# TC-029: update by uuid
sw numbers update <id> --set name="Updated by id"

# TC-030: update by number
sw numbers update +15551234567 --set name="Updated by number"

# TC-031: update by name
sw numbers update "Updated by number" --set name="Updated by name"

# TC-032: the output names both what you typed and the id it wrote
sw numbers update +15551234567 --set name="Round trip"
#   expect: updated +15551234567 (bbbbbbbb-...)

# TC-033: repeated --set
sw numbers update +15551234567 --set call_handler=laml_webhooks \
                               --set call_request_url=https://example.com/voice

# TC-034: raw JSON body
sw numbers update +15551234567 --body '{"name":"From a body"}'

# TC-035: --body beats --set
sw numbers update +15551234567 --set name=ignored --body '{"name":"wins"}'

# TC-036: an invalid choice is caught locally, before any request
sw numbers update +15551234567 --set call_handler=bogus    # exit 2, nothing sent

# TC-037: an ambiguous handle stops the update
sw numbers update 555 --set name=x                          # exit 2, nothing sent
```

### Handlers

`call_handler` now accepts all thirteen values. Each of these should be accepted
locally and sent; whether the platform accepts the companion value is its own
check.

```bash
# TC-038: the handlers the old choice list already had
sw numbers update +15551234567 --set call_handler=relay_script \
                               --set call_relay_script_url=https://example.com/swml
sw numbers update +15551234567 --set call_handler=laml_webhooks \
                               --set call_request_url=https://example.com/cxml
sw numbers update +15551234567 --set call_handler=laml_application \
                               --set call_laml_application_id=<app_id>
sw numbers update +15551234567 --set call_handler=relay_topic --set call_relay_topic=office
sw numbers update +15551234567 --set call_handler=relay_application \
                               --set call_relay_application=my_app
sw numbers update +15551234567 --set call_handler=video_room --set call_video_room_id=<room_id>
sw numbers update +15551234567 --set call_handler=dialogflow \
                               --set call_dialogflow_agent_id=<agent_id>
sw numbers update +15551234567 --set call_handler=ai_agent \
                               --set calling_handler_resource_id=<resource_id>
sw numbers update +15551234567 --set call_handler=call_flow \
                               --set calling_handler_resource_id=<resource_id>

# TC-039: the four that used to be rejected locally (REGRESSION)
sw numbers update +15551234567 --set call_handler=relay_sip_endpoint \
                               --set call_sip_endpoint_id=<endpoint_id>
sw numbers update +15551234567 --set call_handler=relay_context \
                               --set call_relay_context=my_app
sw numbers update +15551234567 --set call_handler=relay_connector \
                               --set call_relay_connector_id=<connector_id>
sw numbers update +15551234567 --set call_handler=relay_verto_endpoint \
                               --set call_verto_resource=<resource>

# TC-040: message handlers
sw numbers update +15551234567 --set message_handler=laml_webhooks \
                               --set message_request_url=https://example.com/sms
sw numbers update +15551234567 --set message_handler=relay_context \
                               --set message_relay_context=my_app

# TC-041: both channels in one call
sw numbers update +15551234567 --set call_handler=laml_webhooks \
                               --set call_request_url=https://example.com/voice \
                               --set message_handler=laml_webhooks \
                               --set message_request_url=https://example.com/sms
```

**TC-039 is the regression case.** Before this change, all four were rejected by
`sw` itself with an invalid-choice error, on values live numbers were already
using. Each must now be accepted locally.

```bash
# TC-042: the choice list is complete
sw docs 2>/dev/null | grep -A 2 call_handler   # or read the --help for the TUI form
```

---

## 6. `release`

> Releasing is billable and irreversible. Run these against numbers you are
> willing to lose, or stop at the confirmation prompt.

```bash
# TC-043: release by uuid, confirm
sw numbers release <id>

# TC-044: release by number, confirm
sw numbers release +15551234567

# TC-045: release by name, confirm
sw numbers release "Fax Number"

# TC-046: the confirmation shows what each handle resolved to
sw numbers release "Fax Number"
#   expect a line:  Fax Number  →  bbbbbbbb-...
#   then:           release 1 phone number? [y/N]

# TC-047: answering no changes nothing
sw numbers release "Fax Number"        # answer n, then confirm it still exists
sw numbers get "Fax Number"

# TC-048: several at once, mixed handles
sw numbers release +15551234567 "Fax Number" <id>
#   expect one resolution line per handle, then "release 3 phone numbers?"

# TC-049: an ambiguous handle stops the whole command before anything goes
sw numbers release +15551234567 555 -y
#   expect exit 2, the candidates table, and NO number released — including the
#   unambiguous one

# TC-050: --yes skips the question
sw numbers release <id> -y

# TC-051: a bad id fails the command but the good ones still go
sw numbers release <good-id> nonexistent -y    # exit 1, "released <good-id>" + an error

# TC-052: --json is a summary object
sw numbers release <id> -y --json      # {"released": [...], "failed": {...}}
```

**TC-049 is the safety case.** Resolution happens for every identifier before
the first delete is sent, so an ambiguous one cannot leave a half-finished
release behind.

---

## 7. E911 extras

```bash
# TC-053: assign by uuid
sw numbers assign-e911-address <id> --e911-address-id <address_id>

# TC-054: assign by number
sw numbers assign-e911-address +15551234567 --e911-address-id <address_id>

# TC-055: assign by name
sw numbers assign-e911-address "Fax Number" --e911-address-id <address_id>

# TC-056: a missing required flag names the flag
sw numbers assign-e911-address +15551234567 --json     # exit 2, names --e911-address-id

# TC-057: in a terminal, the address is offered as a picker
sw numbers assign-e911-address +15551234567

# TC-058: remove asks first, and names what it resolved
sw numbers remove-e911-address "Fax Number"

# TC-059: remove with --yes
sw numbers remove-e911-address +15551234567 --yes

# TC-060: verify the assignment landed
sw numbers get +15551234567 --json | jq '.e911_address_id, .e911_status'
```

---

## 8. `get --full`: the whole routing picture

Run each of these against a number on the handler named.

```bash
# TC-061: a hosted cXML bin — two hops to the document
sw numbers get <a number on laml_webhooks pointing at a /laml-bins/ URL> --full
#   expect: VOICE laml_webhooks
#             └─ cxml_webhook  <resource id>
#                  └─ cxml_script  <resource id>  "<name>"
#                       contents: the cXML in full, highlighted

# TC-062: a SWML script — the document arrives with the resource
sw numbers get <a number on relay_script> --full
#   expect a swml_script node with its contents as JSON, and NO further hop
#   (its request_url is its own bin URL; following it would loop)

# TC-063: a call flow
sw numbers get <a number on call_flow> --full     # expect flow_data in full

# TC-064: a SIP endpoint
sw numbers get <a number on relay_sip_endpoint> --full
#   expect codecs and ciphers on one line each, NOT as JSON blocks

# TC-065: a video room
sw numbers get <a number on video_room> --full
#   expect the node, then "the API returns no further configuration for this type"

# TC-066: an AI agent
sw numbers get <a number on ai_agent> --full      # expect the prompt as a document

# TC-067: an external webhook is fetched
sw numbers get <a number pointing at a live external URL> --full
#   expect status, content_type, and the response body as a document

# TC-068: an external webhook that is down
sw numbers get <a number pointing at a dead tunnel> --full
#   expect the status line and NO body — an HTML error page is not a document

# TC-069: a handler with no target resource says so
sw numbers get <a number whose messaging_handler_resource_id is null> --full
#   expect "this handler names no target resource"

# TC-070: stale configuration is called out
sw numbers update +15551234567 --set call_handler=laml_webhooks \
                               --set call_request_url=https://example.com/a
sw numbers update +15551234567 --set call_handler=relay_script \
                               --set call_relay_script_url=https://example.com/b
sw numbers get +15551234567 --full
#   expect a NOT IN USE section listing call_request_url, which is set but which
#   relay_script does not read

# TC-071: --full --json is one nested object
sw numbers get +15551234567 --full --json | jq '.channels[].handler'
sw numbers get +15551234567 --full --json | jq -r '.channels[0].points_to.points_to.documents[0].text'

# TC-072: plain get does not follow anything
sw numbers get +15551234567           # one request; no fabric resource fetched
```

**TC-070 is the point of the feature.** A number keeps every pointer it has ever
had, and only `call_handler` says which one is live.

**TC-067 security check:** the request to the external host must carry **no**
`Authorization` header. Point a number at a URL you control, run `--full`, and
confirm the inbound request has no SignalWire credentials on it.

---

## 9. `search` and `buy`

`numbers search` is the availability search — numbers you do *not* own. It is a
different thing from `list --match`, which searches the ones you do.

```bash
# TC-073: search by area code
sw numbers search --area-code 555

# TC-074: digit-position filters
sw numbers search --starts-with 555
sw numbers search --contains 1234
sw numbers search --ends-with 7890

# TC-075: geography
sw numbers search --region OH
sw numbers search --region OH --city Cleveland
sw numbers search --city Cleveland            # expect: --city requires --region

# TC-076: toll-free has no geography
sw numbers search --type toll-free
sw numbers search --type toll-free --area-code 833

# TC-077: limit and JSON
sw numbers search --area-code 555 -n 5 --json

# TC-078: no results is an empty table, not an error
sw numbers search --area-code 000

# TC-079: buy a number found above
sw numbers buy --set number=+15551234567

# TC-080: buy with no number, in a terminal, prompts for it
sw numbers buy

# TC-081: buy with no number and --json errors rather than prompting
sw numbers buy --json
```

**TC-081:** every prompt is strict under `--json` or with no TTY. It must fail
with a message naming the missing field, not hang.

---

## 10. TUI form

```bash
sw sh       # then open a phone number and press e to edit
```

- **TC-082:** every text box starts one line tall.
- **TC-083:** paste a long webhook URL into `call_request_url`. The box grows and
  wraps; the whole URL is readable without arrowing sideways.
- **TC-084:** the box stops growing at six lines and scrolls beyond that — one
  field must not fill the form.
- **TC-085:** press `enter` in a text box. Focus moves to the next field and **no
  newline is inserted** — a line break in a URL would be sent.
- **TC-086:** change `call_handler` in the select. The companion fields for the
  new handler appear and the old ones disappear.
- **TC-087:** type into a text field that something else is conditional on. The
  visibility still reacts (the controls are TextAreas now, not Inputs).
- **TC-088:** widen and narrow the terminal with a long value in a box. The
  height re-fits to the new wrap width.
- **TC-089:** save. The value that arrives is the one shown, whole.

### Full routing in the TUI

- **TC-089a:** highlight a number and press `F`. The pane shows the same tree
  `sw numbers get <n> --full` prints, documents included.
- **TC-089b:** press `F` again — back to the field table.
- **TC-089c:** with a tree showing, move to another row. The tree goes; a tree
  built for one number is never shown against another.
- **TC-089d:** press `F` on a number pointing at a dead external URL. The pane
  reads `following the routing…` and **the interface stays live** while it
  times out.
- **TC-089e:** press `.` — the menu lists **Full routing**; on Queues it does not.

---

## 11. Edge cases

```bash
# TC-090: a very long name
sw numbers update +15551234567 --set "name=$(python3 -c "print('a'*1000)")"

# TC-091: unicode and punctuation in a name
sw numbers update +15551234567 --set "name=测试电话"
sw numbers update +15551234567 --set "name=Test@example.com"

# TC-092: a name that looks like a number
sw numbers update <id> --set name=+15559999999
sw numbers get +15559999999     # which row does this resolve to? document the answer

# TC-093: an empty name
sw numbers update +15551234567 --set name=

# TC-094: a malformed --set
sw numbers update +15551234567 --set notanassignment     # exit 2, names the problem

# TC-095: a handle with leading/trailing whitespace
sw numbers get " +15551234567 "

# TC-096: --full on a number with no configuration at all
sw numbers get <a freshly bought number> --full
```

**TC-092 is deliberately ambiguous** — a name that is also a valid E.164.
Record what happens so the behaviour is a decision rather than an accident.

---

## 12. Lifecycle

```bash
# TC-097: buy → configure → inspect → release
sw numbers search --area-code 555 -n 5
sw numbers buy --set number=+15551234567
sw numbers update +15551234567 --set name="Lifecycle Test" \
                               --set call_handler=laml_webhooks \
                               --set call_request_url=https://example.com/voice
sw numbers get "Lifecycle Test"
sw numbers get "Lifecycle Test" --full
sw numbers list -m Lifecycle
sw numbers release "Lifecycle Test"

# TC-098: handler switching leaves visible sediment
sw numbers update <id> --set call_handler=laml_webhooks \
                       --set call_request_url=https://example.com/a
sw numbers update <id> --set call_handler=relay_script \
                       --set call_relay_script_url=https://example.com/b
sw numbers get <id> --full             # call_request_url under NOT IN USE

# TC-099: the same number reached five ways gives the same row
sw numbers get <id> --json             | jq -r .id
sw numbers get +15551234567 --json     | jq -r .id
sw numbers get 5551234567 --json       | jq -r .id
sw numbers get "555-123-4567" --json   | jq -r .id
sw numbers get "Lifecycle Test" --json | jq -r .id
```

---

## Restore

```bash
# What changed since the snapshot
diff <(jq -S . /tmp/numbers-before.json) <(sw numbers list --json | jq -S .)
```

Reconfigure anything section 5 or 8 rewrote. Nothing here creates a number
except TC-079 and TC-097.

## Recording results

For each case: **status** (pass/fail), **what was printed**, **what the API
returned**, and — for the resolution cases — **which row it resolved to and how
many requests it took**. A handle that resolves to the right row by accident
(because there happens to be only one number) is not a pass; note the shape of
the project it was run against.

## Reference

- Owned numbers: `/api/relay/rest/phone_numbers` (GET, POST, PUT, DELETE)
- Availability search: `/api/relay/rest/phone_numbers/search`
- List filters: `filter_number`, `filter_name` — substring, case-insensitive
- E911: `/api/relay/rest/phone_numbers/{id}/e911_address`
- Routing targets: `/api/fabric/resources/{id}` — returns the target's whole
  configuration inline, whatever its type
- Hosted bins: `/laml-bins/{inner_id}`, `/relay-bins/{inner_id}` — the id in the
  URL is the script's **inner** id, not its Fabric resource id
