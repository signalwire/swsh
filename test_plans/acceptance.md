# `sw` acceptance plan — the jobs, end to end

Written for `sw` 3.0.0 as it is today. This is not a command-by-command
walk: it is the handful of things people actually come to SignalWire to do —
stand up an extension, point a number at it, write a dial plan, watch a call
arrive — with every command exercised *in the place it is really used*. A
command that works in isolation and reads wrong in the middle of a job has
still failed.

Each case is a checkbox. Tick it, or write what you saw. **Where a case says
"output", the test is whether a person who did not write the tool could act on
what is printed** — that is the point of this pass.

Run the workflows in order within a part; parts are independent. Part 2 is the
one to do first and to re-check whenever something looks odd, because it is the
contract everything else assumes.

---

## Before you start

### Set up

```bash
cd <checkout>
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export PATH="$PWD/.venv/bin:$PATH"     # so `sw` is on PATH for completion
sw --version                            # sw 3.0.0
```

Use a **scratch project**, not production. Several steps create real objects;
every one of them is torn down in Part 14, and anything that costs money or
reaches the outside world is marked.

| mark | meaning |
| --- | --- |
| 💵 | costs money or bills the project |
| 📡 | reaches a carrier, a handset or a third party |
| 🧹 | creates something Part 14 must remove |

### Conventions

- `<ID>` means paste the id the previous step printed.
- A terminal at least **120 columns** wide. Repeat the table cases at **100**.
- Keep a scratch file of ids as you go; the teardown needs them.
- `sw <anything> --help` should always work and never need the network.

### Prerequisites

- A project with at least one **voice-capable number you already own**
- A second phone you can call from and to 📡
- `ngrok` on PATH if you are testing `sw listen`
- A validated E911 address on the project, for Part 9

---

## Part 1 — First contact

What someone sees in their first five minutes.

- [ ] **A-001** On a machine with **no** credentials, `sw numbers list` fails
      with one line naming the three values and how to supply them. No
      traceback.
- [ ] **A-002** `sw sh` with no credentials **opens the cockpit on the profile
      form** rather than exiting. Filling it in and saving lands on a working
      dashboard.
- [ ] **A-003** Escaping that form instead shows a notice saying what is needed,
      and the app stays usable (ctrl+p reaches the form again).
- [ ] **A-004** `sw login` prompts for project, token and space, prints where
      API credentials come from, and **verifies them before saving**. A wrong
      token is refused with `Nothing was saved.`
- [ ] **A-005** After `sw login`, `sw profile list` shows the profile and marks
      which is in effect; `sw profile path` prints the config file.
- [ ] **A-006** `sw whoami` names the project, the space, the account status and
      **where each value came from** (`credentials_from`).
- [ ] **A-007** With `SIGNALWIRE_API_TOKEN` exported in the shell, `sw whoami`
      says the token came from the environment, not the profile.
- [ ] **A-008** The **first** `sw` command run in a terminal installs tab
      completion, names the file it wrote and how to undo it. The second run
      says nothing.
- [ ] **A-009** In a new shell, `sw numb<TAB>` completes to `numbers`, then
      `sw numbers <TAB>` offers its verbs.
- [ ] **A-010** `sw completion status` names the files; `sw completion
      uninstall` removes them and **a later `sw` run does not put them back**.
- [ ] **A-011** `sw doctor` reports credentials, the LaML surface, call
      identifiers and the tunnel. Each line says `ok` or `fail` with a reason.
- [ ] **A-012** A bare `sw` prints the full command listing in labelled panels,
      with `sh` as the first row and a closing line pointing at `sw sh`.
- [ ] **A-013** `sw docs --list` prints one row per resource; `sw docs -o
      ref.md` writes the same reference as `sw-reference.md`.

---

## Part 2 — The output contract

**Do this part before the workflows, and re-check any line it covers whenever
something looks wrong later.** These hold for *every* command; the workflows
assume them rather than re-testing them.

Pick any three resources with rows (`sip`, `swml`, `logs` are good) and for
each:

- [ ] **A-020** `sw <res> list` prints a table whose **id column is never
      truncated**. No `…` anywhere in an id, at 120 columns or at 100.
- [ ] **A-021** Every table has a column that identifies the row to a person —
      a name, a number, a display name — not just an id and a date.
- [ ] **A-022** Timestamps are **local time with a zone** (`2026-10-14 09:12:33
      EDT`), identical in shape across `logs`, `recordings`, `swml` and
      `queues`. No raw `2026-10-14T13:12:33Z` and no RFC 2822 anywhere.
- [ ] **A-023** A resource with no rows prints the column headers and **`no
      rows`** — never a row of dashes.
- [ ] **A-024** `sw <res> list -n 200` returns up to 200 rows, not 50. Compare
      against `sw api <its path> -q page_size=200 | jq '.data | length'`.
- [ ] **A-025** `sw <res> list -m <text>` finds a row that is **not on the first
      page**. Pick a name from deep in a long listing and search for it.
- [ ] **A-026** `sw <res> list --json | jq .` parses. Repeat with
      `FORCE_COLOR=3` exported — it must still parse.
- [ ] **A-027** `sw <res> list --raw | jq '.links'` shows the envelope and its
      paging links; `--json` shows the rows only.
- [ ] **A-028** `sw <res> get <ID>` prints a field/value table of **every** key
      the API sent, nulls as `-` and empty strings as `""`.
- [ ] **A-029** `sw <res> get <NAME>` resolves by name without a uuid, and the
      confirmation line names both what you typed and the id.
- [ ] **A-030** A name that matches two rows is an **error listing the
      candidates**, never a silent pick.
- [ ] **A-031** `sw <res> list --sort <field>` orders the whole collection, and
      `--desc` reverses it. Rows with an empty value stay **last in both
      directions**.
- [ ] **A-032** `sw <res> list --columns id,<name-field>` shows exactly those;
      `--columns nope` is an error naming the fields that exist.
- [ ] **A-033** `sw <res> list --csv` is parseable CSV; a value containing a
      comma is quoted.
- [ ] **A-034** `sw <res> list | head -3` exits quietly — no `BrokenPipeError`.

Failure behaviour:

- [ ] **A-035** A deliberate validation failure (e.g. `sw gateways create --set
      name=x --set uri=sip:x --set encryption=required --set codecs=PCMU --set
      ciphers=AES_256_CM_HMAC_SHA1_80` twice, so the second collides) prints a
      **readable line naming the field** — `uri: must be unique within project
      (not_unique_within_project)` — not a Python dict.
- [ ] **A-036** The platform's documentation link appears **under** the message
      as a hint, not inside the sentence.
- [ ] **A-037** `sw swml get 00000000-0000-4000-8000-000000000000` is a 404 in
      one line naming the URL.
- [ ] **A-038** With a bad token, any command says `authentication failed` and
      mentions the project id and token.
- [ ] **A-039** With a space that does not resolve, the error names the space
      and points at `sw whoami`.
- [ ] **A-040** `sw whoami --timeout 0.001` reports a timeout, not a traceback.
- [ ] **A-041** Ctrl-C during a listing exits without a traceback.
- [ ] **A-042** `sw --json numbers list` is a **usage error** (the flag belongs
      to the command), while `sw numbers list --json --profile X` and
      `sw numbers list --profile X --json` both work.
- [ ] **A-043** `sw listen --raw` is **refused before it does anything** — no
      tunnel is opened.

---

## Part 3 — Workflow: a SIP extension you can call

The most common first job. Creates 🧹.

```bash
sw sipprofile get
```
- [ ] **A-050** Prints the project's SIP record: `domain`, `domain_identifier`
      and the `default_*` settings. The domain is the **real** one, carrying the
      per-space identifier — not `<space>.sip.signalwire.com`.
- [ ] **A-051** It takes **no id** (`sw sipprofile get` with nothing after it).

```bash
sw sip create --set username=qa-ext-1001 --set password='<a strong one>'   # 🧹
sw sip list -m qa-ext
sw sip get qa-ext-1001
```
- [ ] **A-052** The create prints `created <id>` with the id in full.
- [ ] **A-053** The listing shows the endpoint with a display name derived from
      the username, and the full id.
- [ ] **A-054** `sw sip get qa-ext-1001` resolves **by username**, no uuid.
- [ ] **A-055** The detail table shows the nested endpoint fields
      (`sip_endpoint.username`, `codecs`, `ciphers`, `encryption`), and the
      password is **not** echoed.

```bash
sw sip update qa-ext-1001 --set encryption=required --set codecs=PCMU
sw sip get qa-ext-1001 --raw | jq '.sip_endpoint.encryption, .sip_endpoint.codecs'
```
- [ ] **A-056** The update reports what it changed and names the row.
- [ ] **A-057** The read-back shows the new values — the update was not
      silently dropped.
- [ ] **A-058** An invalid value (`--set encryption=bogus`) is refused
      **locally**, naming the three valid ones, without a request being sent.

Register a real phone against it 📡:

- [ ] **A-059** Using the domain from **A-050** and the username/password above,
      a softphone registers. If it does not, `sw sipprofile get` is where the
      domain must come from — a derived `<space>.sip.signalwire.com` will not
      resolve.
- [ ] **A-060** In the cockpit (`sw sh` → `:calls`), press `g` to register the
      built-in phone with the same credentials, then `H` to dial. The call
      appears in the live table.

---

## Part 4 — Workflow: get a number and point it at the extension

💵 if you buy one; skip the purchase and use an existing number otherwise.

```bash
sw numbers search --area-code 440 -n 5
sw numbers search --contains 1234 --type local
sw numbers search --type toll-free -n 3
```
- [ ] **A-070** Results show the E.164, the formatted number, the region and
      what the number can do.
- [ ] **A-071** `--contains 12` (two digits) is refused with a reason; 3–7
      digits is accepted.
- [ ] **A-072** `--type toll-free` ignores `--area-code` and says so, or simply
      returns toll-free numbers.

```bash
sw numbers buy --set number=<E.164 from the search>      # 💵 🧹
sw numbers list -m <last 4 digits>
```
- [ ] **A-073** The purchase **asks for confirmation naming the number and that
      it charges the project**, unless `--json`.
- [ ] **A-074** The new number appears in the listing with its full id.
- [ ] **A-075** `sw numbers get <the number>` works with `+1…`, with
      `(440) …` and with the bare ten digits — all three find the same row.

Point it at the extension:

```bash
sw sip get qa-ext-1001 --json | jq -r .id          # the endpoint id
sw numbers update <the number> \
    --set call_handler=relay_sip_endpoint \
    --set call_sip_endpoint_id=<endpoint id>
sw numbers get <the number> --full
```
- [ ] **A-076** The update is reported with the number **and** its id.
- [ ] **A-077** `--full` shows a `VOICE` section naming `relay_sip_endpoint`,
      the endpoint it resolves to, and that endpoint's settings inline.
- [ ] **A-078** Fields belonging to handlers that are **not** live are listed
      separately as `NOT IN USE` rather than mixed in or hidden.
- [ ] **A-079** Calling the number from your other phone rings the registered
      extension 📡.
- [ ] **A-080** `sw logs list -n 5` shows the leg; `sw logs get <ID>` shows it in
      full; `sw logs events <ID>` shows its timeline.

---

## Part 5 — Workflow: a dial plan in SWML

```bash
cat > /tmp/plan.json <<'EOF'
{"sections":{"main":[{"answer":{}},
 {"play":{"url":"say:Thanks for calling. Connecting you now."}},
 {"connect":{"to":"qa-ext-1001"}}]}}
EOF
sw swml create --set name=qa-dialplan --body "$(jq -c '{name:"qa-dialplan",contents:.}' /tmp/plan.json)"   # 🧹
```
- [ ] **A-090** Alternatively `sw swml create` with no flags opens a prompt for
      each required field, and the document field opens an editor that
      **validates the JSON locally** before sending.
- [ ] **A-091** Invalid JSON in `contents` is refused with the parse error and
      the position, before any request.
- [ ] **A-092** `sw swml get qa-dialplan` shows the document in full, not
      truncated or escaped into one line.

```bash
sw numbers update <the number> --set call_handler=relay_script \
    --set call_relay_script_url=<the swml url from the row>
sw numbers get <the number> --full
```
- [ ] **A-093** `--full` now resolves the script and prints **the SWML itself**
      under the handler.
- [ ] **A-094** Calling the number plays the prompt then rings the extension 📡.
- [ ] **A-095** `sw swml update qa-dialplan --set name=qa-dialplan-2` renames it
      and **does not blank the document** — confirm with
      `sw swml get qa-dialplan-2 --raw | jq '.swml_script.contents'`.

Webhook variant:

```bash
sw swmlhooks create --set name=qa-hook --set primary_request_url=https://example.com/swml   # 🧹
sw swmlhooks list -m qa-hook
```
- [ ] **A-096** Created and listed; the URL is shown in full or folded, never
      silently cut.

---

## Part 6 — Workflow: the cXML / LaML path

```bash
sw cxml create --set name=qa-cxml --set script_type=calling \
  --set contents='<?xml version="1.0" encoding="UTF-8"?><Response><Say>Hello from cXML</Say></Response>'   # 🧹
sw cxml list -m qa-cxml
sw cxml get qa-cxml
```
- [ ] **A-100** Created, listed, and the XML reads back intact.
- [ ] **A-101** Malformed XML is refused with the platform's message naming
      `contents`.
- [ ] **A-102** `sw cxmlapps list` and `sw cxmlhooks list` both work and show a
      name column, not a bare id and a date.
- [ ] **A-103** Pointing the number at it (`--set call_handler=laml_webhooks
      --set call_request_url=<the bin url>`) and calling plays the message 📡.
- [ ] **A-104** `sw numbers get <the number> --full` resolves the **hosted bin
      URL back to the cXML it holds**, not just the URL.

---

## Part 7 — Workflow: an AI agent on a number

```bash
sw agents create --set name=qa-agent --set prompt_text='You are a terse test agent.'   # 🧹
sw agents list -m qa-agent
sw agents get qa-agent
```
- [ ] **A-110** The prompt round-trips in full — a long multi-line prompt is not
      truncated in the detail table.
- [ ] **A-111** `sw numbers update <the number> --set call_handler=ai_agent --set
      calling_handler_resource_id=<agent id>` is accepted, and `--full` shows
      the agent **and its prompt** under VOICE.
- [ ] **A-112** Calling reaches the agent 📡.
- [ ] **A-113** In the cockpit, `u` stands up the local agent lab and `a` dials
      it from the built-in phone; everything it creates is removed on quit.

---

## Part 8 — Workflow: messaging

```bash
sw send create --set from_=<your number> --set to=<your mobile> --set body='qa test'   # 💵 📡
sw messages send <your mobile> --from <your number> --body 'qa test 2'                 # 💵 📡
sw messages list -n 5
sw messages get <ID>
```
- [ ] **A-120** Both spellings send and report the message id and state.
- [ ] **A-121** The log lists it with from, to, direction, status and a local
      timestamp.
- [ ] **A-122** `sw messages get <ID>` includes the **body**, not just metadata.
- [ ] **A-123** Replying from the handset appears in `sw messages list` as
      inbound 📡.
- [ ] **A-124** `sw numbers update <the number> --set message_handler=laml_webhooks
      --set message_request_url=<a URL>` is accepted, and `--full` shows a
      MESSAGING section separate from VOICE.

---

## Part 9 — Workflow: E911 and number groups

```bash
sw addresses list
sw numbers assign-e911-address <the number> --e911-address-id <ID>
sw numbers get <the number> --json | jq '.e911_address_id, .e911_status'
sw numbers remove-e911-address <the number>
```
- [ ] **A-130** `sw addresses list` shows the address fields, not just ids.
- [ ] **A-131** Assigning reports success naming the number; the read-back shows
      the id and status.
- [ ] **A-132** Removing **asks for confirmation** and the read-back shows it
      gone.

```bash
sw groups create --set name=qa-hunt            # 🧹
sw groups add-member qa-hunt --phone-number-id <number id>
sw groups memberships qa-hunt
sw groups remove-member <membership id>
```
- [ ] **A-133** The group is created and found by name.
- [ ] **A-134** `memberships` is a drill: it lists the members, and `n`/`e`/`d`
      do **not** act on the parent group from inside it (check in the cockpit).
- [ ] **A-135** Removing a member asks first and names what it is removing.

---

## Part 10 — Workflow: video

```bash
sw videorooms create --set name=qa-room --set max_members=5     # 🧹
sw videorooms list -m qa-room
sw videorooms get qa-room --json | jq .max_members
```
- [ ] **A-140** `max_members` **comes back as 5**, not the default. (This is the
      field that used to be silently dropped — if it reads 20, say so.)
- [ ] **A-141** `sw videorooms mint-room-token` returns a token.
- [ ] **A-142** `sw vconf create --set name=qa-conf --set display_name='QA conf'
      --set size=small` 🧹 succeeds, and `size` is required-looking in the form.
      `--set size=xlarge` is refused.
- [ ] **A-143** `sw vsessions list` and `sw vlogs list` work after a session has
      existed.

---

## Part 11 — Workflow: subscribers and tokens

```bash
sw subscribers create --set email=qa-sub@example.com --set password='<strong>'   # 🧹
sw subscribers list -m qa-sub
sw subscribers sip-credentials <subscriber id>
sw subtokens create --set <as prompted>
```
- [ ] **A-150** The subscriber is created and found by email.
- [ ] **A-151** `sip-credentials` is a drill from the subscriber; acting on its
      rows uses the **credential** id, not the subscriber's.
- [ ] **A-152** `sw chattoken create` and `sw pubsubtoken create` each return a
      token and say what it is for.

---

## Part 12 — Workflow: watching it happen

```bash
sw calls list -n 10
sw calls dial <your mobile> --from <your number> --tts 'This is a test'   # 💵 📡
sw calls show <call id>
sw calls play <call id> --tts 'still here'
sw calls digits <call id> 123
sw calls hangup <call id>
```
- [ ] **A-160** `sw calls list` shows live and recent legs from **the voice
      log**, including legs a SIP endpoint made — not only LaML legs.
- [ ] **A-161** Each control command reports what it did against which call.
- [ ] **A-162** A control command against an ended call fails with a readable
      reason.

```bash
sw listen --no-rewrite
sw listen -N <the number>          # rewrites, then restores on exit
```
- [ ] **A-170** `--no-rewrite` prints the public URL and **changes nothing** —
      confirm with `sw numbers get <the number> --json | jq .call_status_callback_url`.
- [ ] **A-171** A real rewrite prints what it changed; callbacks stream in as
      they arrive during a call 📡.
- [ ] **A-172** Ctrl-C **restores the original URLs**. Verify with the same jq.
- [ ] **A-173** Kill it with `kill -9` instead, then `sw listen --restore`
      undoes the leftover rewrite.

---

## Part 13 — The cockpit over the same objects

`sw sh`. These supersede the matching cases in `tui.md`, which predates the
dashboard and the current key map.

- [ ] **A-180** Opens on the **dashboard**: wordmark, space, profile, and eight
      counts. Not an empty calls table.
- [ ] **A-181** A count reading `12+` means "at least twelve"; a plain number is
      exact.
- [ ] **A-182** `?` opens the **key list**, grouped, and includes `j`/`k`.
      Escape closes it.
- [ ] **A-183** `ctrl+r` opens the resource jump list. `:` opens the command bar
      and `:sip` switches.
- [ ] **A-184** `/` filters the rows on screen. The pane title reads
      `3 of 134 · /qa` — both numbers.
- [ ] **A-185** Switching resource **clears the filter**; it is not a mode.
- [ ] **A-186** `escape` steps out one level: drill → list → dashboard.
- [ ] **A-187** A listing of more than 50 rows shows **all** of them (scroll to
      the bottom and compare with `sw <res> list -n 500 --json | jq length`).
- [ ] **A-188** `v` cycles the detail pane: fields → json → raw. `raw` fetches
      that row's own record.
- [ ] **A-189** `F` on a number shows the routing tree, same content as
      `get --full`.
- [ ] **A-190** `n` / `e` / `d` open forms prefilled correctly; `ctrl+s` saves
      and a blank required field is refused naming the field.
- [ ] **A-191** Inside a drill (`groups > memberships`), `n`/`e`/`d` are
      withheld and the footer does not offer them.
- [ ] **A-192** `x` lists the extra actions for the resource; `.` acts on the
      highlighted row.
- [ ] **A-193** `m` hands the mouse back — you can select and copy text — and a
      green `SELECT` badge shows while it is on.
- [ ] **A-194** `ctrl+p` switches profile and the whole cockpit repoints.
- [ ] **A-195** `q` quits cleanly and the terminal is restored.

---

## Part 14 — Teardown and leak check

Delete everything marked 🧹, in reverse order of creation.

```bash
sw numbers update <the number> --set call_handler=laml_webhooks   # unpoint it first
sw sip delete qa-ext-1001 --yes
sw swml delete qa-dialplan-2 --yes
sw swmlhooks delete qa-hook --yes
sw cxml delete qa-cxml --yes
sw agents delete qa-agent --yes
sw groups delete qa-hunt --yes
sw videorooms delete qa-room --yes
sw vconf delete qa-conf --yes
sw subscribers delete <subscriber id> --yes
sw numbers release <the number> --yes          # 💵 only if you bought it
```
- [ ] **A-200** Each delete **names what it is removing** before asking, and
      `handle → id` is shown for anything addressed by name.
- [ ] **A-201** Deleting several at once resolves **every** identifier before
      asking, and an ambiguous one stops the whole command — nothing is deleted.
- [ ] **A-202** A Fabric delete returning 204 with an empty body is reported as
      success, not as a failure.
- [ ] **A-203** **Leak check.** For each of `sip swml swmlhooks cxml agents
      groups videorooms vconf confrooms subscribers`, run
      `sw <res> list -n 200 -m qa-` and confirm nothing is left.
- [ ] **A-204** Check `sw confrooms list -n 200 -m qa-` specifically, since the
      video steps create conference rooms too, and delete any `qa-` row left.

---

## Part 15 — Everything else

Commands the workflows do not reach. One smoke test each: it runs, the output
is readable, and an empty collection says `no rows`.

| | command | check |
| --- | --- | --- |
| [ ] A-210 | `sw api --list` | enumerates operations; `--list compatibility-api` scopes it |
| [ ] A-211 | `sw api /api/relay/rest/phone_numbers` | body verbatim, pipes into `jq` |
| [ ] A-212 | `sw api list_subscribers` | resolves an operation id |
| [ ] A-213 | `sw api create_queue --dry-run` | names the ambiguity across two APIs |
| [ ] A-214 | `sw api send_fax --dry-run -f To=… -f From=… -f MediaUrl=…` | prints the request, sends nothing |
| [ ] A-215 | `sw api <a write>` | asks for confirmation unless `--force` |
| [ ] A-216 | `sw queues create/list/update/delete` | the relay-rest CRUD path |
| [ ] A-217 | `sw gateways create` | refuses without encryption, codecs **and** ciphers |
| [ ] A-218 | `sw domains create` | refuses without `identifier` |
| [ ] A-219 | `sw connectors create` | refuses without `token` |
| [ ] A-220 | `sw relayapps create` | refuses without `name` |
| [ ] A-221 | `sw datasphere create --set url=…` | refuses without a URL; `search` works |
| [ ] A-222 | `sw flows create --set title=qa-flow` 🧹 | created by **title**, not name |
| [ ] A-223 | `sw flows versions <ID>` | lists versions |
| [ ] A-224 | `sw confrooms list` | name column present |
| [ ] A-225 | `sw sipaddr create` | needs a resource to point at; the picker offers real ones |
| [ ] A-226 | `sw fabricaddresses list` | read-only, lists |
| [ ] A-227 | `sw resources list` | every fabric resource, with type |
| [ ] A-228 | `sw resources assign-to-phone-route` | names both ids it needs |
| [ ] A-229 | `sw recordings list` / `get` | timestamps match everything else |
| [ ] A-230 | `sw conflogs list`, `sw fax list`, `sw vlogs list` | all three list |
| [ ] A-231 | `sw lookup get +1…` | carrier/CNAM detail table |
| [ ] A-232 | `sw mfa send-code-by-sms` 📡 then `verify-code` | both report clearly |
| [ ] A-233 | `sw verified create` 📡 | submit and redial verification |
| [ ] A-234 | `sw imported create` | create-only; says it cannot be listed back |
| [ ] A-235 | `sw shortcodes list` | lists or says `no rows` |
| [ ] A-236 | `sw brands list`, `sw brands campaigns <ID>` | the 10DLC drill |
| [ ] A-237 | `sw brands orders <campaign id>` | orders reached through the parent |
| [ ] A-238 | `sw orders list` | **does not exist** — only `sw orders get <ID>` |
| [ ] A-239 | `sw campaigns list` | **does not exist** — only `get`/`update` plus extras |
| [ ] A-240 | `sw wanumbers list`, `sw wabiz list`, `sw watemplates list` | all three |
| [ ] A-241 | `sw projects list` | subprojects, not "projects" |
| [ ] A-242 | `sw tokens create` 🧹 | returns a token; `delete` revokes it |
| [ ] A-243 | `sw vrecordings list`, `sw vstreams get <ID>` | both |
| [ ] A-244 | `sw chunks get <ID>` | a datasphere drill |
| [ ] A-245 | `sw subcreds get <ID>` | a subscriber drill |
| [ ] A-246 | `sw logout` then `sw whoami` | says not logged in; profiles are kept |

---

## What to write down

For anything that fails, capture:

1. the **exact command**, including flags
2. the **full output**, with `FORCE_COLOR=0 NO_COLOR=1` so it pastes cleanly
3. what you expected instead
4. `sw --version` and the terminal width

For a cockpit problem, `y` on the Calls view copies the phone's diagnostics to
the clipboard **and** a file, with the password redacted. For anything SIP,
turn on the `sip_trace` interop knob and attach
`~/Library/Logs/swsh/sip-trace.log`.

Three classes of finding are worth separating, because they need different
fixes:

- **wrong data** — a value that is missing, stale, or silently different from
  what the platform holds. Highest priority; check it against
  `sw <res> get <ID> --raw`.
- **unreadable output** — correct data a person cannot act on: a truncated id, a
  column that is always empty, an error printed as a data structure.
- **wrong shape** — a command that cannot do its job: a required field the form
  does not ask for, a flag that does nothing, an id it has nowhere to accept.
