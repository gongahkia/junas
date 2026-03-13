# P1 + P2 Collaborative Flow Functional Requirements

## Summary

This specification defines the first high-urgency functional requirements tranche
for `Kilter Together`'s collaborative room flow. It treats the `Session Captain`
(`P1`) and the `Phone-First Guest` (`P2`) as one end-to-end mobile-first journey.

The scope is limited to:

- creating a room
- connecting the provider
- choosing the shared surface
- sharing the invite or QR code
- joining from a guest phone
- landing both users in the live room state
- recovering from common setup and join failures without restarting the whole flow

This tranche intentionally excludes recap/rematch, solo-to-room seeding, and
deeper in-room optimization after join.

## Product Goal

Reduce time-to-first-climb for live group sessions by making host setup
predictable and guest join nearly immediate.

## Personas

### P1. Session Captain

- Context: already at the gym, others are waiting, one phone must get the
  session running now.
- Goal: create a room, connect the correct provider account, choose the session
  surface, and send a working invite without troubleshooting.
- Success: a room becomes clearly share-ready in under `120 seconds` when the
  server is reachable and provider credentials are valid.

### P2. Phone-First Guest

- Context: joins from a separate phone, often mid-session, with minimal
  patience for setup or ambiguity.
- Goal: scan or open the invite, enter a display name, and land directly in the
  live room.
- Success: a guest reaches the live room in under `30 seconds` from a valid QR
  code, deep link, or pasted invite.

## Current Public Interfaces In Scope

### Mobile Surfaces

- Landing screen: `/`
- Create room: `/create`
- Join room: `/join`
- Room: `/room`
- App-level invite handling for join deep links in
  `kilter-together-mobile/lib/app.dart`

### API Contracts

- `POST /api/rooms`
- `POST /api/rooms/{slug}/provider/connect`
- `POST /api/rooms/{slug}/surface`
- `POST /api/rooms/{slug}/join`
- `GET /api/rooms/{slug}`
- `GET /api/rooms/{slug}/events`

### Session Contract

- `POST /api/rooms` and `POST /api/rooms/{slug}/join` return `{ room, session }`
- `session.token` is the bearer token for subsequent room snapshot, mutation,
  and SSE requests
- client implementations must treat `session_expired`, `session_invalid`, and
  `session_required` as rejoin flows rather than generic failures

## Journey Phases And Requirements

### Phase 1. Host Setup

#### FR-H1. Minimal room creation

- The mobile app must let the host create a room from `/create` using:
  - self-hosted server URL
  - provider
  - room name
  - host display name
  - provider credentials required by the selected provider
- The create form must validate required fields before submitting.
- The create form must load provider capabilities from the selected server
  before allowing provider selection.
- The app must use provider capability data to avoid presenting unsupported room
  providers.

#### FR-H2. Recoverable provider authentication

- Provider authentication failures during room creation must be presented as
  explicit inline and transient error feedback.
- A host must be able to retry provider authentication from the same setup flow
  without re-entering unrelated room data.
- Provider-specific credential prompts must reflect current capability metadata
  rather than hardcoded assumptions beyond the already supported providers.

#### FR-H3. Session persistence after create

- After successful room creation, the client must persist:
  - active server
  - room slug
  - host bearer token
  - host display name preference
  - last-used provider where applicable
- Successful room creation must navigate directly into `/room`.

### Phase 2. Share-Ready Handoff

#### FR-S1. Visible room readiness state

- The room screen must expose a visible `share-ready` state for hosts.
- A room is only share-ready when all of the following are true:
  - room creation succeeded
  - provider connection is valid for the room
  - a shared surface has been selected for the room
  - an invite can be copied, shared, or rendered as QR
- If any prerequisite is missing, the UI must explain what is still incomplete.

#### FR-S2. Capability-aware surface selection

- The host must be able to select the shared room surface from `/room`.
- Surface selection must follow provider capability shape:
  - direct board selection for board-like providers
  - parent/child selection for nested gym or wall providers
- Attempting to save without a required surface selection must produce a clear,
  recoverable validation message.

#### FR-S3. Invite handoff

- Once the room is share-ready, the room screen must support:
  - copying the invite link
  - native share flow
  - QR rendering from the same invite payload
- The invite payload must carry the server address and room slug needed by a
  guest device to join the correct self-hosted node.

### Phase 3. Guest Join

#### FR-G1. Multi-entry join

- Guests must be able to join by:
  - scanning a host QR code
  - opening a deep link
  - pasting a full invite
  - entering a room slug together with the server URL
- The join screen must prefill server and slug when those values are present in
  the invite payload or deep link.

#### FR-G2. Minimal guest input

- The only required guest-authored field for join is display name.
- The client should remember the last successful display name on the device and
  prefill it on later joins.
- A successful join must persist the guest bearer token and navigate directly
  into `/room`.

#### FR-G3. Clean join failures

- The guest join flow must distinguish and surface these failure categories:
  - malformed or unsupported invite
  - camera unavailable or QR scan failure
  - `display_name_taken`
  - `room_closed`
  - `session_invalid`
  - `session_expired`
  - `session_required`
- Handled failures must tell the guest what to do next from the same screen.
- Join failures must not require clearing app storage or relaunching the app.

### Phase 4. Live Room Landing

#### FR-L1. Direct landing into live room state

- After successful create or join, the user must land in the live `/room` view
  rather than an intermediate waiting state.
- The initial room load must use the saved bearer token to request
  `GET /api/rooms/{slug}`.
- The client must attach to `GET /api/rooms/{slug}/events` after initial load so
  live room state stays current.

#### FR-L2. Shared room truth

- Host and guest devices must converge on the same room snapshot for:
  - room slug and status
  - provider identity
  - selected surface
  - participant list
  - queue, finalists, and current climb when present
- Existing in-room actions such as vote and queue remain available after
  landing, but their deeper optimization is out of scope for this tranche.

#### FR-L3. Rejoin-oriented auth failure handling

- If a saved room token becomes invalid, expired, or missing, the app must route
  the user back to `/join` with a reason that explains whether the issue is:
  - `session_required`
  - `session_invalid`
  - `session_expired`
- The join flow must preserve enough context to let the user rejoin the same
  room without manually rediscovering the server and slug when possible.

## Acceptance Scenarios

### Host setup readiness

- Given a reachable server and valid provider credentials, the host can create a
  room, connect the provider, select the room surface, and reach share-ready
  state within `120 seconds`.
- Given invalid provider credentials, the host sees a specific setup failure and
  can retry without restarting `/create` or recreating the room.
- Given a provider with nested surfaces, the host can complete both parent and
  child selection before the room is considered share-ready.

### Guest instant join

- Given a valid QR invite, the guest can scan, confirm display name, and land in
  the live room within `30 seconds`.
- Given a valid deep link or pasted invite, the guest skips manual server and
  slug discovery and lands in the live room within `30 seconds`.
- Given a typed slug plus server URL, the guest can still join when QR or deep
  links are unavailable.

### Recoverable failures

- Given a malformed QR or unsupported invite payload, the guest gets a clear
  error and can retry scan or paste from the same screen.
- Given camera permission denial or unavailable camera hardware, the guest is
  told to use paste or manual entry instead.
- Given a duplicate display name, the guest is told the name is taken and can
  resubmit a different name from the same join state.
- Given a closed room, the guest is told the room is closed and is not taken
  into a broken room state.
- Given an expired or invalid saved room token, the app redirects back to join
  with the appropriate reason and allows rejoin.

### Shared live room landing

- Given successful create or join on two devices, both devices resolve the same
  room slug, selected surface, participant list, and room status.
- Given new room events after landing, both devices update from server-driven
  state rather than requiring manual reload to continue the session.

## Success Metrics

### M1. Time To Share-Ready Room

- Definition: time from the host tapping `Create room` to the room satisfying
  all share-ready criteria.
- Target: median under `120 seconds`.

### M2. Guest Join To Live Room

- Definition: time from guest scan/open/paste action to the first successful
  live `/room` render.
- Target: median under `30 seconds`.

### M3. Recoverable Setup Or Join Failure Rate

- Definition: share of handled setup and join failures that can be retried to
  success without app restart, storage clearing, or new room creation.
- Target: at least `90%` for the handled failure categories in this document.

## Deferred Work

- advanced host controls beyond readiness and recovery
- deeper optimization of guest participation after landing in the room
- recap and rematch workflows
- solo planning and handoff into collaborative rooms
- new provider onboarding beyond currently supported collaborative providers

## Assumptions

- This is a mobile-first requirements document; web parity is not required in
  this tranche.
- The scope stays within currently supported collaborative providers and their
  existing capability model.
- Existing queue, finalists, voting, and session controls remain part of the
  room once landed, but they are not the optimization target of this spec.
- The success metric thresholds are default product targets for the first
  implementation pass and can be revised once production telemetry exists.
