# Verifying `sw`

The README covers install, authentication and usage. This covers how the tool is
checked, what each kind of check actually proves, and what has been confirmed
against a live space.

## Automated, no credentials needed

```bash
.venv/bin/python -m pytest -q            # the whole suite
.venv/bin/ruff check .
.venv/bin/python scripts/audit_secrets.py --check
.venv/bin/python scripts/audit_fields.py --markdown   # CI fails if docs/field-audit.md changes
```

**What the suite proves, and what it does not.** It stubs HTTP at the transport
boundary, so a green run proves `sw` issues the right method against the right
URL with the right body, and that every registry route resolves against the
bundled catalog. It does not prove the platform accepts those requests.
Response envelopes, pagination parameters and error shapes are only as correct
as the last live probe.

Targeted runs while working:

```bash
.venv/bin/python -m pytest tests/test_resources.py -q      # registry invariants
.venv/bin/python -m pytest tests/test_spec_catalog.py -q   # route well-formedness
.venv/bin/python -m pytest tests/test_crud.py -q           # method + URL per verb
.venv/bin/python -m pytest tests/test_tables.py -q         # what a listing owes a reader
.venv/bin/python -m pytest tests/test_tui.py -q            # headless cockpit
.venv/bin/python -m pytest tests/test_coverage.py -q       # the completeness gate
```

The invariants worth knowing, because they are what catch a bad resource
definition before it ships:

| Test | Catches |
| --- | --- |
| `test_resources.py::TestRestTransportIsComplete` | a `rest_ops` id that does not resolve; a `caps` letter with no route; an `Extra` whose `spec_op` is wrong |
| `test_resources.py::TestVerifiedAgainstLiveProject` | a guess quietly replacing something a live probe already settled |
| `test_spec_catalog.py::TestExactRoutes` | a regenerated catalog losing an exact method or path — the 10DLC `registry/beta` prefix, the singleton `sip_profile`, the two POST-not-GET JSON-RPC endpoints |
| `test_coverage.py` | a spec operation that is neither covered nor excluded-with-a-reason; the ratchet regressing |
| `test_field_audit.py` | a resource whose fields matched the documented request body drifting away from it |
| `test_tables.py` | an identifier elided out of a listing; an empty collection drawn as a row of nulls |

The suite is hermetic about the terminal it runs in. `tests/conftest.py` clears
`FORCE_COLOR` and pins the width at import time, because Rich takes the colour
decision from the environment as well as from the destination — a shell that
exports `FORCE_COLOR` failed about fifty tests that pass everywhere else.

## Live verification, credentials required

There is no live-API test. These are the probes, and they are how a registry
guess becomes a verified fact. Use a scratch project.

```bash
sw doctor                                # credentials, LaML reachability, tunnel deps
python scripts/verify_registry.py        # probes every resource
python scripts/verify_softphone.py       # a real call over loopback, no network
python scripts/probe_dial_uri.py         # which dial-target shapes the stack accepts
python scripts/probe_invite_uri.py       # what actually goes on the wire
python scripts/probe_sip_edges.py <domain>   # which SIP edges answer, over UDP and TCP
```

### The read sweep

Every listing, which cannot damage anything:

```bash
for r in numbers groups verified addresses domains sip gateways swml swmlhooks \
         cxml cxmlhooks cxmlapps flows confrooms subscribers relayapps connectors \
         fabricaddresses sipaddr resources agents datasphere queues recordings \
         logs messages conflogs fax vlogs shortcodes brands wanumbers watemplates \
         wabiz videorooms vsessions vrecordings vconf projects; do
  echo "--- $r"; sw $r list -n 5
done
```

Read the tables, not just the exit codes. A listing can return 200 and still be
wrong for a person: a column that resolves to nothing on every row, an
identifier elided, four spellings of a timestamp across four resources.

### One write cycle per API family

Each family was migrated independently and they differ in update verb and delete
response, so one cycle each is the smallest useful check:

```bash
# relay-rest
sw queues create --set name=sw-check --set max_size=5
sw queues list -m sw-check
sw queues update <id> --set max_size=7
sw queues delete <id> --yes

# fabric — 204 with an empty body on delete, which is success
sw swml create --set name=sw-check --set contents='{"sections":{"main":[]}}'
sw swml update <id> --set name=sw-check-2
sw swml get <id> --raw          # confirm the partial update kept the document
sw swml delete <id> --yes

# fabric, the route that validates as a full replace
sw gateways create --set name=sw-check --set uri=sip:gw.example.com \
                   --set encryption=required --set codecs=PCMU \
                   --set ciphers=AES_256_CM_HMAC_SHA1_80
sw gateways delete <id> --yes
```

Then `sw api`, whose whole purpose is reaching what the registry does not model:

```bash
sw api /api/relay/rest/phone_numbers | jq '.data | length'   # a path
sw api list_subscribers | jq '.data | length'                # an operation id
sw api --list compatibility-api                              # the unmodelled surface
sw api send_fax --dry-run -f To=+1… -f From=+1… -f MediaUrl=https://…/f.pdf
```

Finally the cockpit, by hand: Part 13 of `test_plans/acceptance.md` is the
checklist.

## What has been confirmed live

Pinned in `tests/test_resources.py::TestVerifiedAgainstLiveProject` and
`tests/test_lab.py`, each one having replaced a wrong guess:

- The codec list the SIP form actually offers; `VP9` is not in it.
- SIP endpoint and SIP gateway encryption are **different vocabularies**:
  `default|required|optional` for an endpoint, `required|optional|forbidden` for
  a gateway. A gateway rejects `default`.
- A SIP gateway requires `encryption`, `ciphers` and `codecs` on create. Declared
  optional, both the form and the CLI collected two values and sent a request
  that could not succeed.
- `filter_number` and `filter_name` on the phone-number list do a
  case-insensitive substring match server-side. No other list endpoint has a
  filter that has been proven to work, so looking up any other resource by name
  walks the whole collection and matches locally.
- A space's SIP domain carries a per-space identifier and must be **read** from
  the SIP profile, never derived from the space hostname.
- A `;transport=` parameter in the `To` header separates an INVITE that routes
  from one that does not — so an account names no transport by default.

## The manual test plans

**Start with [`test_plans/acceptance.md`](../test_plans/acceptance.md).** It is
the full by-hand pass: 158 cases over fifteen parts, arranged as the jobs people
actually do — stand up an extension, point a number at it, write a dial plan,
watch the call arrive — with each command exercised where it is really used. A
command that works in isolation and reads wrong in the middle of a job has still
failed, and only a workflow shows that.

Two things about how it is built:

- **Part 2 is the contract.** Paging, handle lookup, local timestamps, untruncated
  ids, readable errors, `--json` that parses — checked once, up front, so the
  workflows can assume them instead of re-testing them in fifteen places.
- **It is checked against the binary.** Every command phrase, `--set` key and
  flag in it was validated against the built CLI, so a case cannot send someone
  down a path that does not exist. Re-check the affected cases whenever the
  command surface changes.

The rest of `test_plans/` is older. `tui.md` and `phone_number.md` are written
for `sw`, though `tui.md` predates the dashboard and the current key map — where
it disagrees with Part 13 of the acceptance plan, Part 13 is right. The other
seventeen were carried over from swsh 2.0 and are written for the cmd2 REPL:
bare commands like `sip_gateway list --json` typed at a prompt, which do not run
as-is. They remain valuable as the record of what was verified live and as a
source of cases, but translating them is outstanding work and is not mechanical
— the resources were renamed too (`sip_gateway` → `gateways`, `fifo_queue` →
`queues`, `laml_app` → `cxmlapps`, `video` → four separate resources).
