# TUI Cockpit Test Plan (`sw sh`)

Written for `sw`, not the cmd2 REPL, though it predates the dashboard and the
current key map: where it disagrees with Part 13 of `acceptance.md`, Part 13 is
right. Each case is a checkbox:
tick it, or note what you saw. Where a case names a keystroke, the same thing
must also work with the mouse (menu bar, action bar, right-click / `.` context
menu) unless the case says otherwise.

## Prerequisites
- A profile saved with `sw login --name NAME` and selected with `sw profile use`
- Network access to the space; `sw whoami` succeeds
- At least one owned phone number with voice, and one with messaging
- A SIP endpoint or a second phone you can call from, to create live legs
- At least one of each: number group, video room, video conference, AI agent,
  call flow with a version, Datasphere document, 10DLC campaign with a number
- A validated E911 address (`sw addresses create`) on the project
- A terminal at least 140 columns wide for the full layout; also try 100

## Test Cases

### 1. Launch and layout
- [ ] TC-T001 `sw sh` starts within a second and shows: header meter, menu bar, live calls table, right column (detail above, event feed below), status bar, footer key hints.
- [ ] TC-T002 The status bar leads with the profile name in use, then the space.
- [ ] TC-T003 The header meter reads `live calls N`, and is not a menu item (clicking it does nothing).
- [ ] TC-T004 The menu bar reads, in order: Calls, Numbers, Voice, Messaging, Resources, Video, AI Agents, Logs, Other, Profile.
- [ ] TC-T005 Calls appears once. There is no greyed "live" entry anywhere and Voice's dropdown does not repeat Calls.
- [ ] TC-T006 Every dropdown entry starts with a capital letter and every entry is the same width.
- [ ] TC-T007 Each dropdown has a clickable close control and closes on escape or on clicking outside it.
- [ ] TC-T008 `sw sh --record events.jsonl` writes one JSON line per call event; the file is valid after `q`.
- [ ] TC-T009 With a profile pointing at a host that does not resolve, the app still opens, the feed logs the failure, and nothing hangs.
- [ ] TC-T010 `q` quits cleanly; the terminal is restored.

### 2. Menu contents
- [ ] TC-T011 Numbers dropdown: Buy Numbers is the first entry; then Phone numbers, Number groups, Imported, Verified callers, E911 addresses, SIP domain apps, Number lookup. No standalone "E911" entry.
- [ ] TC-T012 Buy Numbers opens the search wizard directly (area code / contains / region), lands on the Phone numbers table, and a purchase asks for confirmation naming the number and that it charges the project.
- [ ] TC-T013 Logs dropdown holds every log: Voice logs, Conference logs, Message logs, Fax logs, Video logs. No log appears under any other menu.
- [ ] TC-T014 AI Agents dropdown: AI agents, Datasphere, Datasphere chunks. Nothing else.
- [ ] TC-T015 Resources dropdown starts with SWML scripts and SWML webhooks; cXML scripts, cXML webhooks and cXML applications are the last three.
- [ ] TC-T016 Other dropdown says Subprojects, not Projects, and includes MFA.
- [ ] TC-T017 Profile is a button (not a dropdown) and opens the same screen as ctrl+p.

### 3. Navigation
- [ ] TC-T018 `:` opens the command line; `:numbers` + enter switches to Phone numbers; escape closes it without switching.
- [ ] TC-T019 Unique prefixes resolve: `:num`, `:ag`, `:sub`. An ambiguous or unknown name shows a warning and leaves the view alone.
- [ ] TC-T020 `?` opens the jump list of every resource; clicking one switches; escape closes.
- [ ] TC-T021 Escape from a resource view returns to Calls. Escape inside a drill returns to the parent list first, then Calls.
- [ ] TC-T022 `r` reloads the current list in place; inside a drill it returns to the parent list.
- [ ] TC-T023 `j` / `k` and the arrow keys move the cursor; the detail pane follows.
- [ ] TC-T024 The pane title reads `<Resource>  ·  <count>  ·  <caps>`, e.g. `Queues  ·  3  ·  CRUD`, and `read-only` for a list-only resource.
- [ ] TC-T025 A failed load shows `error` in the title and the error text in the detail pane instead of an empty table.

### 4. Resource views
- [ ] TC-T026 Phone numbers lists the full number, name, handler, callback URL and the **full** id; no id is truncated anywhere.
- [ ] TC-T027 Rows are newest first where the API returns a created_at.
- [ ] TC-T028 On a non-live view the detail pane takes the whole right column; the event feed and its title are hidden. Switching back to Calls restores them.
- [ ] TC-T029 Highlighting an AI agent shows **every** field, nested ones flattened to dotted keys (`ai_agent.prompt.text`), the whole prompt text present, long values folded, lists rendered in full. Compare against `sw agents get <id> --json`.
- [ ] TC-T030 Enter or clicking a row opens it in the detail pane scrolled to the top; the pane scrolls rather than clipping.
- [ ] TC-T031 Message logs: highlighting a message fetches and shows its body once; re-highlighting does not refetch (feed shows no second fetch).
- [ ] TC-T032 Action bar buttons New/Edit/Delete/More are enabled only for what the resource supports (Queues: all; Voice logs: none of New/Edit/Delete).
- [ ] TC-T033 `n` on Queues opens the create form titled `create queues`; ctrl+s with a blank required field refuses and names the field; a valid form creates, the list reloads, the feed logs it.
- [ ] TC-T034 `e` opens the edit form prefilled with the current values, including nested ones (AI agent prompt text).
- [ ] TC-T035 `d` asks `delete <singular> <id>?`; No / escape leaves the row; Yes deletes and reloads.
- [ ] TC-T036 `d` on a resource without delete shows a warning and opens nothing.
- [ ] TC-T037 `n` on Phone numbers opens the buy wizard, not a blank form.
- [ ] TC-T038 A write-only resource (API tokens) opens with `nothing to list, press n to create` and `n` works.
- [ ] TC-T039 An action-only resource (MFA) opens with `nothing to list, press x for actions`, and More is enabled.
- [ ] TC-T040 The `.` key and right-click open a context menu listing exactly the valid actions for the row; picking one does the same as its key.

### 4a. Full routing (`F`)
The `sw numbers get <n> --full` expansion, in the detail pane. It is a toggle on
the pane, not a modal — it *is* that row's detail, answering "what happens when
this rings?" instead of listing forty fields of which most are dead.
- [ ] TC-T040a Phone numbers › highlight a row › `F`: the pane shows VOICE and MESSAGING, each with its handler, the settings that handler reads, and the resource it hands off to.
- [ ] TC-T040b The document is there in full — a cXML bin's markup, a SWML script's JSON, a call flow's `flow_data` — syntax-highlighted and scrollable, not truncated.
- [ ] TC-T040c A number whose handler was changed shows a **NOT IN USE** section naming the fields left from the earlier configuration. Compare with `sw numbers get <n> --full` in a terminal: identical.
- [ ] TC-T040d `F` again returns to the ordinary field table.
- [ ] TC-T040e Move the cursor to another row while a tree is showing: the tree disappears and the new row's field table is shown. A tree must never be displayed against the row it was not built for.
- [ ] TC-T040f While it resolves, the pane reads `following the routing…` **and the interface stays live** — the clock keeps ticking, `j`/`k` still move, the call feed still updates. Test this against a number pointing at a dead external URL, which takes several seconds to time out.
- [ ] TC-T040g A number pointing at an unreachable webhook shows `could not be fetched: …` under that node; nothing crashes and the other channel still resolves.
- [ ] TC-T040h `F` on a resource with no routing declared (Queues, SWML) shows a warning and opens nothing.
- [ ] TC-T040i `F` with no row highlighted warns `no row selected`.
- [ ] TC-T040j The `.` context menu lists **Full routing** on Phone numbers and does not list it on Queues; picking it does the same as `F`.
- [ ] TC-T040k The footer shows `routing` as a binding.

### 5. Extras: drills
Each drill shows its rows in place with the title as a breadcrumb `<Resource>  >  <drill>  ·  N  ·  esc to go back`.
- [ ] TC-T041 Call flows › `x` opens a menu (versions, deploy version); versions lists them.
- [ ] TC-T042 Number groups › memberships.
- [ ] TC-T043 SIP gateways › addresses. Datasphere › chunks. Phone numbers › search available.
- [ ] TC-T044 Room sessions › members, recordings, events. Room recordings › events.
- [ ] TC-T045 Video rooms › streams. Video conferences › streams, tokens.
- [ ] TC-T046 Fabric resources › addresses. 10DLC campaigns › assigned numbers.
- [ ] TC-T047 A single-extra resource runs the drill directly on `x` with no menu.
- [ ] TC-T048 Inside a drill, `x` offers only the actions that belong to that drill (see section 6), never the parent's.

### 6. Extras: actions
An action with input opens a form titled with the action's label and containing only that action's fields. One that changes something asks first. On success the result is shown as a drill when the API returns an object, otherwise the list (or the drill you were in) reloads and the feed logs it.
- [ ] TC-T049 Phone numbers › assign E911 address: form offers a picker of the project's validated addresses (not a text box); submitting assigns; `sw numbers get <id> --json` shows the address.
- [ ] TC-T050 Phone numbers › remove E911 address: asks `remove E911 address <id>?`; Yes removes.
- [ ] TC-T051 Any row action with no row highlighted (empty list) warns `no row selected` and opens nothing.
- [ ] TC-T052 Number groups › add member: picker of owned numbers; the memberships drill then shows the new row.
- [ ] TC-T053 Inside memberships: `x` offers show member and remove member. Remove asks, then the memberships drill refreshes (not the group list).
- [ ] TC-T054 Video rooms › mint room token: `room_name` is prefilled from the highlighted room; the token appears as a one-row result you can read in the detail pane.
- [ ] TC-T055 Video rooms › find by name: the room appears as a one-row result.
- [ ] TC-T056 Video rooms › start stream: needs an RTMP(S) URL; the streams drill then lists it.
- [ ] TC-T057 Video conferences › start stream. Inside tokens: show token, reset token (asks first).
- [ ] TC-T058 10DLC campaigns › assigned numbers › unassign number: asks, unassigns, the drill refreshes.
- [ ] TC-T059 Fabric resources › assign to SIP domain app (picker of domain apps), assign to phone route (id + calling/messaging), assign to SIP endpoint (picker of endpoints).
- [ ] TC-T060 Subscriber tokens: `n` mints a plain token; `x` offers guest, invite, refresh and embed, each with its own fields; each result is shown.
- [ ] TC-T061 MFA › send code by SMS: `to` required, `from` is a picker of owned numbers; result shows the request `id`. Then verify code with that id and the received code shows `success: true`; a wrong code shows the API's failure, not a crash.
- [ ] TC-T062 MFA › send code by call rings the destination and speaks the code.
- [ ] TC-T063 A failed action (bad id, API 4xx) shows `<label> failed: <reason>` and logs it in red in the feed; the view is unchanged.

### 7. Live calls
- [ ] TC-T064 Place a call from a SIP endpoint through SWML, and one to a cXML number. Both rows appear within 7 seconds, with state, full id, type (SIP/PSTN/LaML…), direction, from, to, started time and a duration that ticks.
- [ ] TC-T065 Duration starts counting from when the call was answered, not from when the TUI first saw it.
- [ ] TC-T066 Hang up from the phone: the row leaves the live view within 5 seconds and the feed logs the end with a reason.
- [ ] TC-T067 `f` toggles ended calls into the table (newest first) and back out; the footer hint reflects it.
- [ ] TC-T068 `h` on a SWML/RELAY leg hangs it up. `h` on a cXML (LaML) leg also hangs it up, routed through the compat API (no "must not point to a cXML call" error).
- [ ] TC-T069 `t` prompts for a transfer target and transfers a RELAY leg. On a LaML leg it fails locally with the message that only hangup and record work on cXML calls.
- [ ] TC-T070 `p` prompts for text and speaks it into a RELAY leg. `s` prompts for digits and sends them.
- [ ] TC-T071 `R` starts recording on either kind of leg; the feed says `record sent`.
- [ ] TC-T072 The detail pane for a LaML leg explains that native call control is unavailable for it.
- [ ] TC-T073 `h` / `t` / `p` / `s` / `R` with no call highlighted warn and do nothing. On a resource view they do nothing at all.
- [ ] TC-T074 `c` clears the event feed.
- [ ] TC-T075 New call: `n` on the live view (also the New button and `New call` in the context menu) opens a form titled `new call` with from (picker of owned numbers), to, SWML or cXML URL, and say.
- [ ] TC-T076 Submitting with neither a URL nor say is refused locally with a warning; nothing is dialled.
- [ ] TC-T077 Submitting to your phone with `say` = "hello from sw": the phone rings, answers to the text, hangs up; the row appears in the live view within 7 seconds and disappears after it ends.
- [ ] TC-T078 Submitting with a SWML URL runs that script.
- [ ] TC-T079 With `sw sh --topic <topic>`, RELAY events for that topic show in the feed alongside polled ones without duplicate rows.

### 8. Profiles
- [ ] TC-T080 ctrl+p opens the profile screen listing every saved profile, the one in use marked; escape closes it.
- [ ] TC-T081 The note shows the config file path and, when SIGNALWIRE_* environment variables are set, a warning that the CLI's default is shadowed by them.
- [ ] TC-T082 `u` (or Use) on another profile switches: the status bar shows the new name, the live view reloads from the new project, the old poller stops (no events from the previous project appear afterwards), and `sw whoami` in another shell reports the new default.
- [ ] TC-T083 `n` (or New) opens the form; blanks are refused; saving adds the profile without switching to it.
- [ ] TC-T084 `e` (or Edit) opens the form prefilled (token masked); saving persists; `sw profile list` agrees.
- [ ] TC-T085 `d` (or Delete) asks first, then removes; deleting the profile in use is refused or falls back sensibly (note what you see).
- [ ] TC-T086 ctrl+p never opens Textual's command palette.

### 9. Consistency with the CLI
- [ ] TC-T087 Every resource reachable in the TUI is listed by `sw docs --list`, and `sw docs` group headings match the menu bar.
- [ ] TC-T088 Anything created, edited or deleted in the TUI is visible to the matching `sw <resource> get <id> --json` immediately afterwards.
- [ ] TC-T089 `sw calls list --live` and the TUI live view agree on which legs are up.
