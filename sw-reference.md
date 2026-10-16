# sw resource reference  (v3.0.0)

Generated from the registry — the single source of truth behind both the CLI and the TUI. Do not edit by hand; run `sw docs`.

54 resources across 8 groups, out of 332 operations the platform exposes.

Anything not listed here is still reachable with `sw api`, which resolves any operation id from the same catalog: `sw api --list` enumerates all of them. That is how the compatibility API is used, since it is deliberately not modelled as resources.

## Numbers

### `addresses` — E911 addresses

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw addresses list`, `sw addresses create`, `sw addresses get`, `sw addresses update`, `sw addresses delete`
- backend: rest · relay-rest
- Emergency (E911) addresses. Assign one to a number with `sw numbers assign-e911-address`.
- fields:
  - `label` (text) *(required)* — What to call this address.
  - `country` (text) *(required)* — ISO 3166 alpha-2, e.g. US.
  - `first_name` (text) *(required)*
  - `last_name` (text) *(required)*
  - `street_number` (text) *(required)*
  - `street_name` (text) *(required)*
  - `city` (text) *(required)*
  - `state` (text) *(required)*
  - `postal_code` (text) *(required)*
  - `address_type` (choice=['Apartment', 'Basement', 'Building', 'Department', 'Floor', 'Office', 'Penthouse', 'Suite', 'Trailer', 'Unit']) — Sub-unit kind, when the address has one.
  - `address_number` (text) — Sub-unit number, e.g. the suite number.
  - `emergency_enabled` (bool) — Carrier-validates the address. Regulated and billable.
  - `auto_correct_address` (bool) — Let the carrier correct the address. Defaults to true.

### `domains` — SIP domain apps

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw domains list`, `sw domains create`, `sw domains get`, `sw domains update`, `sw domains delete`
- backend: rest · relay-rest
- fields:
  - `name` (text) *(required)*
  - `identifier` (text) *(required)* — Subdomain label, e.g. `support` for support.<space>.
  - `domain` (text)

### `groups` — number groups

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw groups list`, `sw groups create`, `sw groups get`, `sw groups update`, `sw groups delete`, `sw groups memberships`, `sw groups add-member`, `sw groups show-member`, `sw groups remove-member`
- backend: rest · relay-rest
- fields:
  - `name` (text) *(required)*

### `imported` — imported numbers

- operations: `C`  (L=list C=create R=read U=update D=delete)
- commands: `sw imported create`
- backend: rest · relay-rest
- Create-only: numbers can be imported but the API offers no list of them.
- fields:
  - `number` (text) *(required)*
  - `carrier` (text)

### `lookup` — number lookup

- operations: `live`  (L=list C=create R=read U=update D=delete)
- commands: `sw lookup get`, `sw lookup look-up-a-number`
- backend: rest · relay-rest
- Carrier/CNAM lookup for an E.164 number.

### `numbers` — phone numbers

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw numbers list`, `sw numbers buy`, `sw numbers get`, `sw numbers update`, `sw numbers release`, `sw numbers search`, `sw numbers assign-e911-address`, `sw numbers remove-e911-address`
- backend: rest · relay-rest
- Owned numbers and how each routes. Creating one purchases it.
- fields:
  - `number` (text) *(required)* — E.164. Creating purchases the number.
  - `name` (text)
  - `call_handler` (choice=['relay_script', 'relay_topic', 'relay_context', 'relay_application', 'relay_connector', 'relay_sip_endpoint', 'relay_verto_endpoint', 'laml_webhooks', 'laml_application', 'ai_agent', 'call_flow', 'video_room', 'dialogflow']) — Pick a handler; the field it needs appears below.
  - `call_request_url` (text)
  - `call_status_callback_url` (text)
  - `call_laml_application_id` (text)
  - `call_relay_script_url` (text)
  - `call_relay_topic` (text)
  - `call_relay_topic_status_callback_url` (text)
  - `call_relay_application` (text)
  - `call_relay_context` (text)
  - `call_relay_context_status_callback_url` (text)
  - `call_relay_connector_id` (text)
  - `call_sip_endpoint_id` (text)
  - `call_verto_resource` (text)
  - `call_video_room_id` (text)
  - `call_fallback_url` (text)
  - `calling_handler_resource_id` (text) — The AI agent, call flow or video room to route to.
  - `call_dialogflow_agent_id` (text)
  - `message_handler` (choice=['relay_script', 'relay_topic', 'relay_context', 'relay_application', 'relay_connector', 'relay_sip_endpoint', 'relay_verto_endpoint', 'laml_webhooks', 'laml_application', 'ai_agent', 'call_flow', 'video_room', 'dialogflow'])
  - `message_request_url` (text)
  - `message_fallback_url` (text)
  - `message_laml_application_id` (text)
  - `message_relay_context` (text)
  - `message_relay_topic` (text)

### `verified` — verified callers

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw verified list`, `sw verified create`, `sw verified get`, `sw verified update`, `sw verified delete`, `sw verified submit-verification`, `sw verified redial-verification`
- backend: rest · relay-rest
- fields:
  - `number` (text) *(required)*

## Voice

### `calls` — calls

- operations: `live`  (L=list C=create R=read U=update D=delete)
- backend: sdk · -
- Live calls merged from RELAY, status callbacks and polling.

### `queues` — queues

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw queues list`, `sw queues create`, `sw queues get`, `sw queues update`, `sw queues delete`, `sw queues members`, `sw queues member`, `sw queues next-member`
- backend: rest · relay-rest
- fields:
  - `name` (text) *(required)*
  - `max_size` (int) — Maximum callers held in the queue.

### `recordings` — recordings

- operations: `LRD`  (L=list C=create R=read U=update D=delete)
- commands: `sw recordings list`, `sw recordings get`, `sw recordings delete`
- backend: rest · relay-rest

## Messaging

### `brands` — 10DLC brands

- operations: `LCR`  (L=list C=create R=read U=update D=delete)
- commands: `sw brands list`, `sw brands create`, `sw brands get`, `sw brands campaigns`, `sw brands orders`
- backend: rest · relay-rest
- Brand registrations; each brand lists its campaigns, and each campaign its number orders.
- fields:
  - `name` (text) *(required)*
  - `company_name` (text)
  - `legal_entity_type` (choice=['PRIVATE_PROFIT', 'PUBLIC_PROFIT', 'NON_PROFIT', 'GOVERNMENT'])
  - `contact_email` (text)
  - `contact_phone` (text)
  - `ein` (text)
  - `ein_issuing_country` (text)
  - `company_vertical` (text)
  - `company_address` (text)
  - `status_callback_url` (text)

### `campaigns` — 10DLC campaigns

- operations: `RU`  (L=list C=create R=read U=update D=delete)
- commands: `sw campaigns get`, `sw campaigns update`, `sw campaigns assigned-numbers`, `sw campaigns unassign-number`
- backend: rest · relay-rest
- fields:
  - `name` (text) *(required)*

### `orders` — number orders

- operations: `LCR`  (L=list C=create R=read U=update D=delete)
- commands: `sw orders get`
- backend: rest · relay-rest
- fields:
  - `phone_numbers` (list) — E.164 numbers to assign to the campaign.
  - `status_callback_url` (text) — Where order status changes are posted.

### `send` — send message

- operations: `C`  (L=list C=create R=read U=update D=delete)
- commands: `sw send create`, `sw send update`
- backend: rest · message-api
- Send SMS/MMS/WhatsApp via the native message API.
- fields:
  - `from_` (choice) *(required)*
  - `to` (text) *(required)*
  - `body` (textarea)
  - `media` (list) — Media URLs, comma separated (MMS).

### `shortcodes` — short codes

- operations: `LRU`  (L=list C=create R=read U=update D=delete)
- commands: `sw shortcodes list`, `sw shortcodes get`, `sw shortcodes update`
- backend: rest · relay-rest
- fields:
  - `name` (text)

### `wabiz` — WhatsApp businesses

- operations: `L`  (L=list C=create R=read U=update D=delete)
- commands: `sw wabiz list`
- backend: rest · message-api

### `wanumbers` — WhatsApp numbers

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw wanumbers list`, `sw wanumbers get`
- backend: rest · message-api
- WhatsApp senders on this project. Read-only.

### `watemplates` — WhatsApp templates

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw watemplates list`, `sw watemplates create`, `sw watemplates get`, `sw watemplates update`, `sw watemplates delete`
- backend: rest · message-api
- fields:
  - `name` (text) *(required)*
  - `language` (text)
  - `category` (text)
  - `body_text` (textarea)

## AI Agents

### `agents` — AI agents

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw agents list`, `sw agents create`, `sw agents get`, `sw agents update`, `sw agents delete`, `sw agents addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `display_name` (text)
  - `prompt_text` (textarea) — What the agent should do. Sent as prompt.text.
  - `post_prompt_text` (textarea) — Optional summary pass after the call ends.

### `chunks` — Datasphere chunks

- operations: `RD`  (L=list C=create R=read U=update D=delete)
- commands: `sw chunks get`, `sw chunks delete`
- backend: rest · datasphere-api
- Chunks within a Datasphere document (drill from Datasphere).

### `datasphere` — Datasphere

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw datasphere list`, `sw datasphere create`, `sw datasphere get`, `sw datasphere update`, `sw datasphere delete`, `sw datasphere chunks`, `sw datasphere search`
- backend: rest · datasphere-api
- fields:
  - `url` (text) *(required)* — Source URL to ingest. http(s) only.
  - `name` (text)
  - `tags` (list) — Comma separated.

## Resources

### `confrooms` — conference rooms

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw confrooms list`, `sw confrooms create`, `sw confrooms get`, `sw confrooms update`, `sw confrooms delete`, `sw confrooms addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `display_name` (text)
  - `max_members` (int)
  - `record` (bool)

### `connectors` — FreeSWITCH connectors

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw connectors list`, `sw connectors create`, `sw connectors get`, `sw connectors update`, `sw connectors delete`, `sw connectors addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `token` (text) *(required)* — Shared secret the FreeSWITCH instance authenticates with.

### `cxml` — cXML scripts

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw cxml list`, `sw cxml create`, `sw cxml get`, `sw cxml update`, `sw cxml delete`, `sw cxml addresses`
- backend: rest · fabric-api
- A hosted cXML document; for your own endpoint use cxmlhooks.
- fields:
  - `name` (text) *(required)*
  - `contents` (textarea) *(required)* — e.g. <Response><Say>Hello</Say></Response>
  - `script_type` (choice=['calling', 'messaging', 'faxing'])
  - `status_callback_url` (text)
  - `status_callback_method` (choice=['POST', 'GET'])

### `cxmlapps` — cXML applications

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw cxmlapps list`, `sw cxmlapps create`, `sw cxmlapps get`, `sw cxmlapps update`, `sw cxmlapps delete`, `sw cxmlapps addresses`
- backend: sdk · fabric-api
- fields:
  - `name` (text) *(required)*

### `cxmlhooks` — cXML webhooks

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw cxmlhooks list`, `sw cxmlhooks create`, `sw cxmlhooks get`, `sw cxmlhooks update`, `sw cxmlhooks delete`, `sw cxmlhooks addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `primary_request_url` (text) *(required)*

### `fabricaddresses` — fabric addresses

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw fabricaddresses list`, `sw fabricaddresses get`
- backend: rest · fabric-api

### `flows` — call flows

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw flows list`, `sw flows create`, `sw flows get`, `sw flows update`, `sw flows delete`, `sw flows versions`, `sw flows deploy-version`, `sw flows addresses`
- backend: rest · fabric-api
- fields:
  - `title` (text) *(required)* — What the flow is called; also its display name.

### `gateways` — SIP gateways

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw gateways list`, `sw gateways create`, `sw gateways get`, `sw gateways update`, `sw gateways delete`, `sw gateways addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `uri` (text) *(required)*
  - `encryption` (choice=['required', 'optional', 'forbidden']) *(required)*
  - `codecs` (multi=['OPUS', 'OPUS@48000H@20I', 'OPUS@24000H@20I', 'OPUS@16000H@20I', 'OPUS@8000H@20I', 'G722', 'PCMU', 'PCMA', 'G729', 'VP8', 'H264']) *(required)*
  - `ciphers` (multi=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32']) *(required)*

### `relayapps` — RELAY applications

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw relayapps list`, `sw relayapps create`, `sw relayapps get`, `sw relayapps update`, `sw relayapps delete`, `sw relayapps addresses`
- backend: rest · fabric-api
- fields:
  - `name` (text) *(required)*
  - `topic` (text) *(required)* — The RELAY topic this application subscribes to.
  - `call_status_callback_url` (text)

### `resources` — fabric resources

- operations: `LRD`  (L=list C=create R=read U=update D=delete)
- commands: `sw resources list`, `sw resources get`, `sw resources delete`, `sw resources addresses`, `sw resources assign-to-sip-domain-app`, `sw resources assign-to-phone-route`, `sw resources assign-to-sip-endpoint`
- backend: rest · fabric-api
- Every fabric resource, and the routing-assignment actions.

### `sip` — SIP endpoints

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw sip list`, `sw sip create`, `sw sip get`, `sw sip update`, `sw sip delete`, `sw sip addresses`
- backend: rest · fabric-api
- fields:
  - `username` (text) *(required)* — The SIP username, shown as URI in the dashboard.
  - `password` (text) *(required)*
  - `send_as` (choice) — Outbound caller ID on calls to the PSTN. Must be a number you own, so the list is your purchased numbers.
  - `caller_id` (text) — Caller ID shown on SIP-to-SIP calls. Free text, not a purchased number.
  - `hold_music_url` (text)
  - `encryption` (choice=['default', 'required', 'optional'])
  - `codecs` (multi=['OPUS', 'OPUS@48000H@20I', 'OPUS@24000H@20I', 'OPUS@16000H@20I', 'OPUS@8000H@20I', 'G722', 'PCMU', 'PCMA', 'G729', 'VP8', 'H264'])
  - `ciphers` (multi=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])

### `sipaddr` — SIP addresses

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw sipaddr list`, `sw sipaddr create`, `sw sipaddr get`, `sw sipaddr update`, `sw sipaddr delete`
- backend: rest · fabric-api
- A SIP URI that rings a Fabric resource: the hop that makes an agent, a SWML webhook or a room callable from a SIP phone.
- fields:
  - `name` (text) *(required)* — URL-safe: lowercase letters, numbers and hyphens. Builds the URI.
  - `user` (text) — SIP username callers dial. Defaults to * (any username).
  - `calling_handler_resource_id` (choice) *(required)* — The Fabric resource inbound calls to this address are handed to.
  - `context_id` (text) — Domain (context) to group the address under. Defaults to the project's own.
  - `password` (text) — Write-only. Never returned.
  - `encryption` (choice=['required', 'optional', 'forbidden'])
  - `codecs` (multi=['OPUS', 'OPUS@48000H@20I', 'OPUS@24000H@20I', 'OPUS@16000H@20I', 'OPUS@8000H@20I', 'G722', 'PCMU', 'PCMA', 'G729', 'VP8', 'H264'])
  - `ciphers` (multi=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])
  - `ip_auth_enabled` (bool)
  - `ip_auth` (list) — IP or CIDR entries, comma separated. Required when IP auth is enabled.

### `subcreds` — subscriber SIP credentials

- operations: `CRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw subcreds get`, `sw subcreds update`, `sw subcreds delete`
- backend: rest · fabric-api
- SIP credentials under a subscriber (drill from Subscribers).
- fields:
  - `username` (text) *(required)*
  - `password` (text) *(required)*
  - `caller_id` (text) — Friendly caller ID name.
  - `send_as` (text) — Default caller ID number.
  - `encryption` (choice=['default', 'required', 'optional'])
  - `codecs` (multi=['OPUS', 'OPUS@48000H@20I', 'OPUS@24000H@20I', 'OPUS@16000H@20I', 'OPUS@8000H@20I', 'G722', 'PCMU', 'PCMA', 'G729', 'VP8', 'H264'])
  - `ciphers` (multi=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])

### `subscribers` — subscribers

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw subscribers list`, `sw subscribers create`, `sw subscribers get`, `sw subscribers update`, `sw subscribers delete`, `sw subscribers sip-credentials`, `sw subscribers addresses`
- backend: rest · fabric-api
- List rows nest the person under `subscriber`; create takes them flat.
- fields:
  - `email` (text) *(required)*
  - `password` (text)
  - `first_name` (text)
  - `last_name` (text)
  - `display_name` (text)
  - `job_title` (text)
  - `company_name` (text)
  - `time_zone` (text)
  - `country` (text)

### `subtokens` — subscriber tokens

- operations: `C`  (L=list C=create R=read U=update D=delete)
- commands: `sw subtokens create`, `sw subtokens mint-guest-token`, `sw subtokens mint-invite-token`, `sw subtokens refresh-token`, `sw subtokens mint-embed-token`
- backend: rest · fabric-api
- Mint subscriber, guest, invite, refresh and embed tokens.
- fields:
  - `reference` (text) *(required)* — Identifies the subscriber this token is for.
  - `expire_at` (int) — Unix timestamp the token expires at.
  - `application_id` (text)
  - `password` (text)
  - `fingerprint` (text) — Binds the token to one device.
  - `scope` (choice=['sat:refresh']) — Only a refresh-capable token needs a scope.
  - `first_name` (text)
  - `last_name` (text)
  - `display_name` (text)
  - `job_title` (text)
  - `time_zone` (text)
  - `country` (text)
  - `region` (choice=['us-central'])
  - `company_name` (text)

### `swml` — SWML scripts

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw swml list`, `sw swml create`, `sw swml get`, `sw swml update`, `sw swml delete`, `sw swml addresses`
- backend: rest · fabric-api
- A hosted SWML document. There is no URL field: SignalWire serves the script and mints the URL. To point at your own endpoint, use swmlhooks instead.
- fields:
  - `name` (text) *(required)*
  - `contents` (code) *(required)* — SignalWire hosts this and generates the request URL for you.
  - `script_type` (choice=['calling', 'messaging'])
  - `status_callback_url` (text)
  - `status_callback_method` (choice=['POST', 'GET'])

### `swmlhooks` — SWML webhooks

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw swmlhooks list`, `sw swmlhooks create`, `sw swmlhooks get`, `sw swmlhooks update`, `sw swmlhooks delete`, `sw swmlhooks addresses`
- backend: rest · fabric-api
- Points at an SWML endpoint you host. For a document SignalWire hosts for you, use swml instead.
- fields:
  - `name` (text)
  - `primary_request_url` (text) *(required)* — Your endpoint. Must be http or https.

## Video

### `vconf` — video conferences

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw vconf list`, `sw vconf create`, `sw vconf get`, `sw vconf update`, `sw vconf delete`, `sw vconf streams`, `sw vconf start-stream`, `sw vconf tokens`, `sw vconf show-token`, `sw vconf reset-token`
- backend: rest · video-api
- fields:
  - `name` (text) *(required)*
  - `display_name` (text) *(required)*
  - `size` (choice=['small', 'medium', 'large']) — Capacity band. A conference has no numeric participant cap.

### `videorooms` — video rooms

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw videorooms list`, `sw videorooms create`, `sw videorooms get`, `sw videorooms update`, `sw videorooms delete`, `sw videorooms streams`, `sw videorooms start-stream`, `sw videorooms mint-room-token`, `sw videorooms find-by-name`
- backend: rest · video-api
- fields:
  - `name` (text) *(required)*
  - `display_name` (text)
  - `max_members` (int)
  - `quality` (choice=['720p', '1080p'])
  - `record_on_start` (bool)
  - `join_from` (text)
  - `join_until` (text)
  - `remove_at` (text)

### `vrecordings` — room recordings

- operations: `LRD`  (L=list C=create R=read U=update D=delete)
- commands: `sw vrecordings list`, `sw vrecordings get`, `sw vrecordings delete`, `sw vrecordings events`
- backend: rest · video-api

### `vsessions` — room sessions

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw vsessions list`, `sw vsessions get`, `sw vsessions members`, `sw vsessions recordings`, `sw vsessions events`
- backend: rest · video-api

### `vstreams` — video streams

- operations: `RUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw vstreams get`, `sw vstreams update`, `sw vstreams delete`
- backend: rest · video-api
- fields:
  - `url` (text) *(required)* — RTMP destination for the stream.

## Logs

### `conflogs` — conference logs

- operations: `L`  (L=list C=create R=read U=update D=delete)
- commands: `sw conflogs list`
- backend: rest · logs-api

### `fax` — fax logs

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw fax list`, `sw fax get`
- backend: rest · fax-api

### `logs` — voice logs

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw logs list`, `sw logs get`, `sw logs events`, `sw logs log-detail`
- backend: rest · voice-api
- Completed calls. Read-only; each has an event timeline.

### `messages` — message logs

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw messages list`, `sw messages get`, `sw messages log-detail`
- backend: rest · message-api

### `vlogs` — video logs

- operations: `LR`  (L=list C=create R=read U=update D=delete)
- commands: `sw vlogs list`, `sw vlogs get`
- backend: rest · video-api

## Other

### `chattoken` — chat token

- operations: `C`  (L=list C=create R=read U=update D=delete)
- commands: `sw chattoken create`
- backend: rest · chat-api
- fields:
  - `ttl` (int) *(required)* — Validity in MINUTES, 1 to 43200. Not seconds.
  - `channels` (code) *(required)* — Per-channel permissions, e.g. {"support": {"read": true}}.
  - `member_id` (text) — Identifies the member this token acts as.
  - `state` (code) — Arbitrary state carried on the member.

### `mfa` — MFA

- operations: `live`  (L=list C=create R=read U=update D=delete)
- commands: `sw mfa send-code-by-call`, `sw mfa send-code-by-sms`, `sw mfa verify-code`
- backend: rest · relay-rest
- Send and verify multi-factor codes over call or SMS. Actions only; nothing to list.

### `projects` — subprojects

- operations: `LCRUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw projects list`, `sw projects create`, `sw projects get`, `sw projects update`, `sw projects delete`, `sw projects rotate-signing-key`
- backend: rest · projects-api
- fields:
  - `name` (text) *(required)*

### `pubsubtoken` — pubsub token

- operations: `C`  (L=list C=create R=read U=update D=delete)
- commands: `sw pubsubtoken create`
- backend: rest · pubsub-api
- fields:
  - `ttl` (int) *(required)* — Validity in MINUTES, 1 to 43200. Not seconds.
  - `channels` (code) *(required)* — Per-channel permissions, e.g. {"alerts": {"read": true}}.
  - `member_id` (text) — Identifies the member this token acts as.
  - `state` (code) — Arbitrary state carried on the member.

### `sipprofile` — SIP profile

- operations: `RU`  (L=list C=create R=read U=update D=delete)
- commands: `sw sipprofile get`, `sw sipprofile update`
- backend: rest · relay-rest
- A single project-wide record rather than a collection.
- fields:
  - `domain_identifier` (text) — The per-space SIP identifier; `domain` is built from it.
  - `default_encryption` (choice=['default', 'required', 'optional'])
  - `default_codecs` (multi=['OPUS', 'OPUS@48000H@20I', 'OPUS@24000H@20I', 'OPUS@16000H@20I', 'OPUS@8000H@20I', 'G722', 'PCMU', 'PCMA', 'G729', 'VP8', 'H264'])
  - `default_ciphers` (multi=['AEAD_AES_256_GCM_8', 'AES_256_CM_HMAC_SHA1_80', 'AES_CM_128_HMAC_SHA1_80', 'AES_256_CM_HMAC_SHA1_32', 'AES_CM_128_HMAC_SHA1_32'])
  - `default_send_as` (text)
  - `default_outbound_policy` (text)

### `tokens` — API tokens

- operations: `CUD`  (L=list C=create R=read U=update D=delete)
- commands: `sw tokens create`, `sw tokens update`, `sw tokens delete`
- backend: rest · project-api
- Create, update and revoke: the API offers no list of project tokens.
- fields:
  - `name` (text) *(required)*
  - `permissions` (multi=['calling', 'messaging', 'video', 'fax', 'chat', 'pubsub', 'numbers', 'storage', 'tasking', 'datasphere', 'management', 'fsa'])
