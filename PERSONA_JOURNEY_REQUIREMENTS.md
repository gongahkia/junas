# Persona Journey Functional Requirements

## Summary

This specification defines the next tranche of functional requirements for
`Kilter Together`, derived from front-end persona journeys and pain point
analysis. It builds on the P1/P2 collaborative flow spec and extends coverage
to returning users, solo researchers, Crux regulars, and cross-session
continuity.

The scope covers room templates, mid-session surface changes, navigation guards,
catalog filtering improvements, onboarding refinements, credential fast paths,
participant indicators, rematch flows, queue automation, app-not-installed
fallback, richer recent rooms, multi-select shortlisting, background
notifications, personal climb logs, provider token refresh, and Crux metadata
surfacing.

## Personas

### P1. Session Captain

- Context: at the gym, others waiting, one phone must get the session running.
- Goal: create room, connect provider, choose surface, send invite.
- Success: room share-ready in under 120s.

### P2. Phone-First Guest

- Context: joins from a separate phone via QR or paste, minimal patience.
- Goal: scan/open invite, enter display name, land in live room.
- Success: live room in under 30s from valid invite.

### P3. Solo Project Researcher

- Context: scouts climbs alone, filters, favorites, builds shortlist offline.
- Goal: find climbs matching a grade range, save a plan, seed into future room.
- Success: shortlist of 8+ climbs saved and shareable in under 5 minutes.

### P4. Crux Gym Regular

- Context: uses Crux-backed rooms, expects gym/wall terminology.
- Goal: switch walls mid-session without closing the room.
- Success: wall change reflected for all participants within 10s.

### P6. Returning Session Regular

- Context: has used the app across multiple sessions at the same gym.
- Goal: rejoin or clone previous sessions without re-doing setup.
- Success: re-create last week's session config in under 30s.

### P5. Community Self-Host Operator

- No new requirements in this tranche. See existing observability stack.

## User Journeys

### Journey 1: Session Captain — "Tuesday Night Crew"

```
Open app → /create → enter server → pick provider → enter creds →
name room "Tuesday Steep" → share QR → wait for 3 guests →
pick board/angle → browse catalog → queue 8 climbs →
rotate through queue → close room → view recap
```

Pain points:
1. Credential re-entry every session despite stored credentials.
2. No session templates — same config recreated weekly.
3. Waiting room ambiguity — no clear guest join count signal.
4. Queue exhaustion — manual re-queue when queue runs dry.
5. No mid-session surface change — must close and re-create.

### Journey 2: Phone-First Guest — "First Time at the Gym"

```
Receive QR → scan → app opens /join pre-filled →
enter display name → land in room → see current climb →
vote on a few → add one to queue → leave when done
```

Pain points:
1. App not installed — QR leads nowhere.
2. Display name friction — must type every join.
3. Orientation shock — too many panels, no first-action hint.
4. No notification when current climb changes while backgrounded.
5. Accidental back-navigation exits room without confirmation.

### Journey 3: Solo Project Researcher — "Weekend Spray Wall Planning"

```
Open app → /solo → pick board → set angle →
filter grade V4-V6 → browse 30 climbs → shortlist 8 →
save as plan → share link → later: seed into room
```

Pain points:
1. No grade range filter — single value only.
2. No bulk shortlist actions — 8 individual taps.
3. Plan sharing is one-way and read-only.
4. No climb attempt history for personal tracking.
5. Offline images may be incomplete with no per-image status.

### Journey 4: Returning Session Regular — "Thursday Regulars"

```
Open app → see recent room → tap → session expired → rejoin →
notice leftover climbs if room reused
```

Pain points:
1. Session expiry is silent and abrupt.
2. No room reuse / rematch from closed rooms.
3. Recent rooms lack context (board, angle, climb count).
4. No personal stats across sessions.

### Journey 5: Crux Gym Regular — "Wall-Hopping at the Gym"

```
Open app → /create → pick Crux → authenticate →
pick gym → pick wall A → queue climbs → crew moves to wall B →
must close room and re-create
```

Pain points:
1. No mid-session wall switch.
2. Provider auth token expiry with no proactive refresh.
3. Crux metadata (color, foot rules) underused in catalog cards.

## Functional Requirements

### Tier 1 — High impact, moderate complexity

#### FR-R1. Room templates / clone

Host can save a room configuration (provider, surface, angle, settings) as a
named template and re-use it to create future rooms in 2 taps from the landing
screen or create screen.

- Templates are stored locally on device in app prefs.
- A template captures: server URL, provider ID, surface ID, surface context
  (board_id, angle, gym_slug), room name template, fist bumps enabled, and
  optionally a reference to stored provider credentials.
- The create screen offers a "From template" selector when templates exist.
- Templates can be created from the create screen after successful room creation
  ("Save as template?" prompt) or from the recap screen.
- Templates can be managed (renamed, deleted) from the settings screen.

Personas: P1, P6.
Addresses: Captain pain #2, Regular pain #2.

#### FR-R2. Mid-session surface change

Host can change the board, wall, or angle from within the live room without
closing it. The backend already supports `POST /rooms/{slug}/surface` after
initial set. The Flutter room screen currently disables the surface picker
after the first surface is committed.

- Room screen re-enables the surface picker for users with `manageSurface`
  permission when the room is open.
- Changing the surface triggers a room-wide SSE event. All participants see the
  updated surface context and the catalog reloads automatically.
- A confirmation dialog warns "Changing the surface will reset the catalog view
  for all participants."
- Queue and finalists are preserved across surface changes.

Personas: P1, P4.
Addresses: Captain pain #5, Crux pain #1.

#### FR-R3. Back-navigation guard

Room screen intercepts system back gesture and hardware back button with a
confirmation dialog: "Leave this room? You can rejoin later with the same
invite."

- Uses `PopScope` (or `WillPopScope` on older Flutter) to intercept.
- Dialog offers "Stay" (default) and "Leave" actions.
- Does not trigger on programmatic navigation (e.g., room close redirect).

Personas: P2.
Addresses: Guest pain #5.

#### FR-R4. Grade range filter

Solo and room catalog filters accept a min and max grade instead of a single
value.

- The catalog filter UI shows two dropdowns or a range slider for grade
  selection.
- The API client passes `grade_min` and `grade_max` query parameters.
- If the backend does not yet support range params, the client filters
  post-fetch until backend support lands.
- Grade values use the provider's native grade scale (V-scale for Kilter,
  provider-native for Crux).

Personas: P3.
Addresses: Solo pain #1.

#### FR-R5. Contextual first-action hint

After a guest joins a room, show a non-modal inline card at the top of the
room view: "Start by voting on the current climb or browsing the catalog."

- The hint auto-dismisses after the user's first interaction (vote, queue add,
  or catalog browse).
- The hint does not appear if the user has previously completed the guest room
  guided tour.
- The hint is a lightweight `AnimatedContainer` that slides away, not a modal
  sheet.

Personas: P2.
Addresses: Guest pain #3.

### Tier 2 — High impact, higher complexity

#### FR-R6. Quick-start credentials

On `/create`, if the host has stored credentials for the selected provider,
pre-fill the credential fields and show a "Use saved credentials" chip. The
manual entry fields are collapsed unless the host taps "Change."

- Credential storage already exists via `flutter_secure_storage` and
  `ProviderSecretRepository`.
- The create screen checks for stored credentials when the provider selection
  changes.
- If stored credentials are found, the auth fields section shows a summary
  chip (e.g., "Saved Crux credentials") with a "Change" action.
- Submitting with saved credentials skips the validation prompt — credentials
  are sent directly to `POST /api/rooms`.

Personas: P1, P4.
Addresses: Captain pain #1.

#### FR-R7. Participant join indicators

After sharing the invite, show a real-time participant count badge in the room
header (e.g., "3 joined").

- The room header already shows participant count via `room.participants.length`.
- Add a more prominent badge or counter next to the room name when the
  participant list is collapsed.
- Show a "Waiting for guests..." placeholder state when only the host is
  present.
- Badge updates live via SSE events.

Personas: P1.
Addresses: Captain pain #3.

#### FR-R8. Room rematch / re-open

From a recap screen or a closed recent room entry, allow the host to create a
new room pre-filled with the same configuration.

- The recap screen shows a "Rematch" button if the current user was the
  original host.
- Tapping "Rematch" navigates to `/create` with query parameters that pre-fill
  the server, provider, surface, angle, room name (appended with "II", "III",
  etc.), and fist bumps setting.
- The finalists list from the closed room is offered as a seed queue for the
  new room.
- Recent room entries for closed rooms show a "Rematch" action.

Personas: P1, P6.
Addresses: Regular pain #2.

#### FR-R9. Queue auto-refill suggestion

When the active queue drops to 0 `queued` entries (all entries are `done` or
`current`), show an inline prompt: "Queue empty — add top-voted climbs?"

- Tapping the prompt bulk-enqueues the top N (default 5) voted climbs that are
  not already in the queue or finalists.
- The prompt only appears for users with `manageQueue` permission.
- If there are no voted climbs available, the prompt instead says "Queue empty —
  browse the catalog to add more."

Personas: P1.
Addresses: Captain pain #4.

#### FR-R10. App-not-installed fallback

The invite QR code and deep link encode a URL that resolves to a lightweight
static HTML page served by the backend when opened in a mobile browser without
the app installed.

- The backend serves a static page at `GET /join/{slug}` (outside `/api/`)
  that shows the room name, participant count, and app store badges.
- The page includes an `intent://` URI (Android) and universal link (iOS) that
  opens the app if installed.
- The page is minimal HTML with inline CSS, no JS framework.
- The QR payload switches from `kiltertogether://join?...` to
  `https://<server>/join/<slug>?server=<server>` so browsers can resolve it.

Personas: P2.
Addresses: Guest pain #1.

### Tier 3 — Nice to have, lower urgency

#### FR-R11. Richer recent rooms

Recent room entries on the landing screen and in the recent rooms modal show
board/wall name, angle, climb count, and relative timestamp.

- `RecentRoom` model already stores `surfaceName`. Extend with `angle`,
  `climbCount`, and `lastVisitedAt` (already present).
- Landing screen cards show: room name, provider icon, surface context
  (e.g., "Original 12×12 @ 40°"), climb count, and "2 days ago".
- Recent rooms modal shows the same expanded info.

Personas: P6.
Addresses: Regular pain #3.

#### FR-R12. Multi-select shortlist

Solo browse supports long-press multi-select to add multiple climbs to the
shortlist or queue in one batch action.

- Long-pressing a climb tile enters multi-select mode with checkboxes.
- A floating action bar appears at the bottom: "Add N to shortlist" /
  "Add N to queue."
- Tapping outside or pressing "Done" exits multi-select mode.
- Works in both solo Kilter browse and solo provider browse.

Personas: P3.
Addresses: Solo pain #2.

#### FR-R13. Current-climb notification

When the app is backgrounded and the queue `current` entry changes, fire a
local notification: "Now climbing: <climb name>."

- Uses `flutter_local_notifications` package.
- Notification is only sent if the user has opted in via settings.
- A new setting toggle: "Notify when current climb changes" (default: off).
- The SSE listener continues in the background (within platform limits) or
  re-checks on app resume.

Personas: P2.
Addresses: Guest pain #4.

#### FR-R14. Personal climb log

Per-device history of climbs encountered across sessions, with optional
attempt status and notes.

- Stored locally in SQLite (`app.db` or a dedicated `climb_log.db`).
- Each log entry: climb ID, provider ID, surface context, timestamp, status
  (seen/attempted/sent/completed), optional free-text note.
- Accessible from a new "Log" tab or section in settings.
- Solo browse and room catalog views show a subtle indicator if the climb
  has a log entry.
- Export as JSON or CSV from settings.

Personas: P3, P6.
Addresses: Solo pain #4, Regular pain #4.

#### FR-R15. Provider token proactive refresh

When the Crux provider connection metadata includes a token expiry timestamp,
run a background refresh before it lapses.

- The room controller checks `room.connection.metadata['token_expires_at']`
  during the periodic session refresh cycle.
- If the token expires within 30 minutes, call
  `POST /rooms/{slug}/provider/connect` with the stored credentials.
- If refresh fails, surface a non-blocking banner: "Provider connection
  expiring — re-enter credentials to stay connected."
- Only triggers for providers whose capabilities declare
  `requires_token_refresh: true`.

Personas: P4.
Addresses: Crux pain #2.

#### FR-R16. Crux metadata in catalog cards

Climb list tiles for Crux-backed rooms show color dot, hold type icon, and
foot rule badge when the data is available in `ProviderClimb.meta`.

- The climb tile checks `climb.meta['color']`, `climb.meta['hold_type']`, and
  `climb.meta['foot_rule']`.
- Color is rendered as a small filled circle using the hex value.
- Hold type is rendered as a label chip (e.g., "Crimp", "Jug").
- Foot rule is rendered as a subtle badge (e.g., "Feet follow hands").
- These elements are only shown when the metadata keys are present, so
  non-Crux providers are unaffected.

Personas: P4.
Addresses: Crux pain #3.

## Implementation Priority

| Phase | Requirements | Rationale |
|-------|-------------|-----------|
| A | FR-R3, FR-R5, FR-R7, FR-R11, FR-R16 | Pure frontend, no backend changes, small scope |
| B | FR-R1, FR-R2, FR-R6, FR-R8 | Frontend with local storage or minor backend interaction |
| C | FR-R4, FR-R9, FR-R12 | Catalog/queue enhancements, may need backend params |
| D | FR-R10, FR-R13, FR-R14, FR-R15 | New backend endpoint, platform integration, or new storage |
