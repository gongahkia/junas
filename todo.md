### Task 1 (A) +bugfix | Philosophical Alignment

**PURPOSE** — Highlighted holds do not align over the physical holds on the board image. The SVG overlay uses `preserveAspectRatio="none"` and `absolute inset-0`, which stretches to fill the parent container, but the board `<img>` uses `object-contain`, which may leave letterbox gaps. The SVG coordinate space (0–100) maps to the full container, not the visible image area, causing a positional mismatch whenever the container aspect ratio differs from the image aspect ratio.

**WHAT TO DO**
1. In `kilter-together-app/src/components/KilterBoardImage.tsx`, the root container (line 30) is `<div className="relative inline-block max-w-full">`. The first image (line 32–43) uses `object-contain` which can leave unused space. The SVG (line 47–83) uses `absolute inset-0 h-full w-full` which fills the entire container including that unused space.
2. Remove `object-contain` from the image elements (line 36). Replace the current image class with `max-w-full block` (no object-contain). This ensures the `<img>` intrinsic dimensions define the container size (since the parent is `inline-block`), and the image fills the container 1:1.
3. Change the SVG `preserveAspectRatio` (line 51) from `"none"` to `"xMidYMid meet"` so it scales uniformly and centers within the container, matching the image scaling.
4. Alternatively, if `object-contain` must stay for layout reasons: use a `useRef` on the first image, listen for `onLoad`, read `naturalWidth`/`naturalHeight` and `clientWidth`/`clientHeight`, compute the actual rendered image rect (accounting for object-contain letterboxing), and position the SVG to match that rect via `style={{ top, left, width, height }}` instead of `inset-0`.
5. The same pattern exists in `kilter-together-app/src/components/ProblemView.tsx` (line 98, which passes layers to `KilterBoardImage`) and `kilter-together-app/src/components/RoomProblemView.tsx` (line 85–100). These consume `KilterBoardImage` so fixing the component fixes both call sites.
6. In the backend, `api/models/highlighted_holds.go` lines 114–115 compute `x` as `(placement.X - bounds.MinX) / width * 100` and `y` as `(bounds.MaxY - placement.Y) / height * 100`. The Y inversion is correct (DB uses bottom-left origin, SVG uses top-left). The percentage math is verified by tests. No backend changes needed — the bug is frontend-only.

**DONE WHEN**
- [ ] On a 16×12 board image displayed in a container whose aspect ratio differs from the image, highlighted hold circles visually center on the corresponding physical hold LEDs.
- [ ] On a 7×10 board variant (different aspect ratio), holds still align correctly.
- [ ] SVG circles for start/finish/middle/foot roles render at the same relative position as the Kilter app's official overlay.
- [ ] Existing tests in `kilter-together-app/src/components/ProblemView.test.tsx` continue to pass (`npm test`).

---

### Task 2 (A) +refactor | Philosophical Alignment

**PURPOSE** — `api/rooms/service.go` line 367 hardcodes `ParentID: contextMap["gym_slug"]` when filtering surfaces. This works for Crux (which uses `gym_slug` as its parent key) but will break for any new provider that uses a different context key. New providers like MoonBoard or Tension Board will pass a different key (e.g., `board_type` or `wall_id`), causing `ParentID` to always be empty.

**WHAT TO DO**
1. In `api/rooms/service.go`, function `SetSurface` (line 351–410), change line 366–368 from:
   ```go
   filters := providers.SurfaceFilter{
       ParentID: contextMap["gym_slug"],
   }
   ```
   to:
   ```go
   filters := providers.SurfaceFilter{
       ParentID: contextMap["parent_id"],
   }
   ```
2. In `api/providers/crux.go`, function `ListSurfaces` (line 64–134), when building `ProviderSurface` for gyms (line 87–95), add `"parent_id": gym.URLSlug` to the `Meta` map. When building surfaces for walls (line 119–131), add `"parent_id": filters.ParentID` to the `Meta` map.
3. In `api/providers/kilter.go`, function `ListSurfaces` (line 42–67), add `"parent_id": ""` to the `Meta` map for each board surface (Kilter has a flat hierarchy, so parent is always empty).
4. On the frontend, wherever the context map is constructed for `SetSurface` calls (in `RoomView.tsx`), ensure the surface's `meta.parent_id` value is included as `parent_id` in the context payload. Search `RoomView.tsx` for calls to `api.setRoomSurface` and verify the context map includes a `parent_id` key sourced from `surface.meta?.parent_id ?? surface.parent_id ?? ""`.

**DONE WHEN**
- [ ] A Crux room can still select a gym and wall surface (existing flow works).
- [ ] A Kilter room can still select a board surface (existing flow works).
- [ ] No hardcoded provider-specific keys (`gym_slug`) remain in `rooms/service.go`.
- [ ] Existing tests pass: `cd api && go test ./...`.

---

### Task 3 (B) +feature | Philosophical Alignment

**PURPOSE** — The codebase only defines `ProviderKilter` and `ProviderCrux` as valid provider IDs. Adding MoonBoard, Tension Board, and Grasshopper requires their IDs to exist in both backend constants and the frontend union type so that room creation, type checking, and provider registry lookups work.

**WHAT TO DO**
1. In `api/providers/types.go` lines 7–10, add three new constants:
   ```go
   ProviderMoonboard   ProviderID = "moonboard"
   ProviderTension     ProviderID = "tension"
   ProviderGrasshopper ProviderID = "grasshopper"
   ```
2. In `kilter-together-app/src/types.ts` line 2, expand the union:
   ```typescript
   export type ProviderId = "kilter" | "crux" | "moonboard" | "tension" | "grasshopper";
   ```
3. In `kilter-together-app/src/components/RoomView.tsx`, search for any `providerId === "kilter"` or `providerId === "crux"` conditionals. At line 62 of `RoomProblemView.tsx`, the condition `providerId === "kilter" ? "Route grade" : "Secondary info"` should remain — new providers will fall through to "Secondary info" which is correct.

**DONE WHEN**
- [ ] `providers.Get(providers.ProviderMoonboard)` returns an error `unsupported provider "moonboard"` (expected — no implementation yet, but the const exists).
- [ ] TypeScript compilation succeeds with the expanded `ProviderId` type (`npm run build`).
- [ ] Existing tests pass on both backend and frontend.

---

### Task 4 (B) +feature | Philosophical Alignment

**PURPOSE** — Adding a new provider requires implementing the 6-method `Provider` interface, registering it, and wiring frontend support. Without a documented scaffold, each new provider author must reverse-engineer the contract from Kilter and Crux implementations, increasing ramp-up time and risk of subtle incompatibilities.

**WHAT TO DO**
1. Create `api/providers/provider_scaffold.go.example` (not compiled — `.go.example` extension). Include a complete skeleton struct implementing all 6 methods of the `Provider` interface from `api/providers/types.go` lines 79–86: `ID()`, `ValidateConnection()`, `ListSurfaces()`, `ListClimbs()`, `GetClimb()`, `RefreshCatalog()`.
2. In each method body, include a comment explaining: (a) what the method must return, (b) how errors should be formatted (plain `fmt.Errorf`, no wrapping with custom types yet), (c) the expected ID format for `ListClimbs`/`GetClimb` (prefix with provider name, e.g. `moonboard:123`).
3. Include inline comments noting: how `ListClimbsInput.Context` carries provider-specific keys, how `SurfaceFilter.ParentID` works for hierarchical vs flat surface models, and how `ProviderCacheEntry` can be used for HTTP caching (reference `api/providers/crux.go` lines 281–323).
4. Include the `init()` registration pattern from `api/providers/register.go`.

**DONE WHEN**
- [ ] The file `api/providers/provider_scaffold.go.example` exists and contains a compilable (if renamed to `.go`) implementation skeleton.
- [ ] All 6 interface methods are present with doc comments.
- [ ] `go build ./...` still passes (`.go.example` is not compiled).

---

### Task 5 (B) +security | Philosophical Alignment

**PURPOSE** — When a user in a Kilter room submits a Crux-format climb ID (e.g., `crux:123`), the Kilter provider's `GetClimb` will fail with a parse error, but the error message is opaque. The rooms layer (`service.go`) does not validate that the climb ID prefix matches the room's provider before dispatching. Early rejection with a clear error improves debuggability and prevents provider-specific parsing errors from leaking.

**WHAT TO DO**
1. In `api/rooms/service.go`, function `getRoomClimb` (lines 1145–1159), before calling `provider.GetClimb`, add a prefix check:
   ```go
   expectedPrefix := string(providers.ProviderID(room.ProviderID)) + ":"
   if !strings.HasPrefix(climbID, expectedPrefix) {
       return nil, fmt.Errorf("climb %q does not belong to provider %s", climbID, room.ProviderID)
   }
   ```
2. This function is the single gateway for `ToggleVote`, `AddQueueEntry`, `AddFinalist`, `PromoteClimb`, and `PickRandom*` — so all paths benefit from this check.

**DONE WHEN**
- [ ] Passing `climbID="crux:123"` to a Kilter room returns error `climb "crux:123" does not belong to provider kilter`.
- [ ] Passing a valid `kilter:14:uuid-here` climb ID to a Kilter room still succeeds.
- [ ] Existing tests pass: `cd api && go test ./...`.

---

### Task 6 (B) +feature | Philosophical Alignment

**PURPOSE** — MoonBoard is one of the most widely used commercial climbing boards. Without a MoonBoard provider, Kilter Together cannot serve MoonBoard users, limiting the addressable user base for public launch.

**WHAT TO DO**
1. Create `api/providers/moonboard.go`. Implement the `Provider` interface (6 methods).
2. MoonBoard uses an API at `https://moonboard.com`. Authentication is email + password via POST to `/Account/Login` which returns a session cookie. Implement `ValidateConnection` to perform this login and store the session cookie in the `SecretPayload` as `{"email": "...", "password": "...", "session": "..."}`. Return metadata `{"email": email}`.
3. `ListSurfaces` should return available board types: MoonBoard 2016 (40°), MoonBoard 2017 (40°), MoonBoard 2019 (40°), MoonBoard Masters 2017 (25°/40°), MoonBoard Masters 2019 (25°/40°). These are static and can be hardcoded as `ProviderSurface` entries with `Kind: "board"`.
4. `ListClimbs` should query the MoonBoard API for problems on the selected board. Use the cached JSON pattern from `api/providers/crux.go` lines 281–323 (the `ProviderCacheEntry` GORM model) with a 5-minute TTL.
5. Climb ID format: `moonboard:{boardType}:{problemId}`.
6. `GetClimb` should fetch a single problem by ID.
7. `RefreshCatalog` should invalidate cache entries with `provider_id = "moonboard"`.
8. Register in `api/providers/register.go`: add `MustRegister(NewMoonboardProvider())`.
9. [Unverified] The exact MoonBoard API endpoints and response schemas need to be confirmed against the actual API documentation or network traffic. The implementation may need adjustment once the real API contract is known.

**DONE WHEN**
- [ ] `providers.Get(providers.ProviderMoonboard)` returns a valid provider instance.
- [ ] `ValidateConnection` returns an error for invalid credentials and metadata for valid ones.
- [ ] `ListSurfaces` returns at least the MoonBoard 2019 (40°) entry.
- [ ] `ListClimbs` returns paginated results with climb names, grades, and setter names.
- [ ] `go build ./...` succeeds.
- [ ] A new room can be created with `provider_id: "moonboard"` (end-to-end test via API).

---

### Task 7 (B) +feature | Philosophical Alignment

**PURPOSE** — Tension Board is another major commercial climbing board. Without a Tension Board provider, Kilter Together excludes Tension Board users from collaborative sessions.

**WHAT TO DO**
1. Create `api/providers/tension.go`. Implement the `Provider` interface.
2. Tension Board uses an API similar to Kilter's own backend. Authentication is via username/password. The Tension Board app communicates with an API endpoint for syncing data. Implement `ValidateConnection` to authenticate against the Tension Board API.
3. `ListSurfaces` should return available board sizes (Tension Board 1, Tension Board 2, etc.).
4. `ListClimbs` should query for problems with pagination. Use the `ProviderCacheEntry` caching pattern.
5. Climb ID format: `tension:{boardType}:{problemId}`.
6. Register in `api/providers/register.go`: add `MustRegister(NewTensionProvider())`.
7. [Unverified] The exact Tension Board API endpoints, auth flow, and response schemas need to be confirmed. The implementation may require API key negotiation or OAuth-style tokens.

**DONE WHEN**
- [ ] `providers.Get(providers.ProviderTension)` returns a valid provider instance.
- [ ] `ValidateConnection` authenticates and returns metadata.
- [ ] `ListSurfaces` returns at least one board entry.
- [ ] `ListClimbs` returns paginated results.
- [ ] `go build ./...` succeeds.

---

### Task 8 (B) +feature | Philosophical Alignment

**PURPOSE** — Grasshopper Board is a growing player in the commercial climbing board market. Supporting it expands Kilter Together's reach to gyms using Grasshopper hardware.

**WHAT TO DO**
1. Create `api/providers/grasshopper.go`. Implement the `Provider` interface.
2. Grasshopper Board uses its own app and API for problem management. Implement `ValidateConnection` to authenticate against the Grasshopper API.
3. `ListSurfaces` should return available board configurations.
4. `ListClimbs` should query for problems with pagination and caching.
5. Climb ID format: `grasshopper:{boardId}:{problemId}`.
6. Register in `api/providers/register.go`: add `MustRegister(NewGrasshopperProvider())`.
7. [Unverified] The Grasshopper Board API is not publicly documented. Implementation will require reverse-engineering the app's network traffic or contacting Grasshopper for API access.

**DONE WHEN**
- [ ] `providers.Get(providers.ProviderGrasshopper)` returns a valid provider instance.
- [ ] `ValidateConnection` authenticates and returns metadata.
- [ ] `ListSurfaces` and `ListClimbs` return valid data.
- [ ] `go build ./...` succeeds.

---

### Task 9 (A) +infra | DX/Utility

**PURPOSE** — The entire backend uses Go's stdlib `log` package (`log.Println`, `log.Printf`). This provides no log levels, no structured fields, no JSON output, and no context propagation. For a public launch, logs need to be queryable and machine-parseable. Go 1.21+ includes `log/slog` in stdlib — zero new dependencies required (the project uses Go 1.23).

**WHAT TO DO**
1. In `api/main.go`, set up a default slog handler at startup. Add before the `serve` command runs:
   ```go
   slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo})))
   ```
2. In `api/config/db.go`, replace all `log.Println` (line 33) and `log.Printf` (lines 37, 79) calls with `slog.Info` or `slog.Warn`:
   - Line 33: `slog.Info("kilter database connection established")`
   - Line 37: `slog.Warn("failed to apply some performance indexes", "error", err)`
   - Line 79: `slog.Warn("failed to create index", "error", err)`
3. In `api/bootstrap/run.go`, replace all `fmt.Printf` progress messages with `slog.Info` calls with structured fields (e.g., `slog.Info("downloading base database", "source", url)`).
4. In `api/bootstrap/sync.go`, replace `fmt.Printf` calls with `slog.Info` / `slog.Warn`.
5. Remove `"log"` imports from all modified files and add `"log/slog"`.

**DONE WHEN**
- [ ] `grep -r 'log\.Print' api/` returns zero matches (no stdlib log usage remains).
- [ ] Running `go run . serve` outputs JSON-formatted log lines to stdout.
- [ ] Each log line includes at minimum: `time`, `level`, `msg` keys.
- [ ] `go build ./...` succeeds.
- [ ] Existing tests pass: `cd api && go test ./...`.

---

### Task 10 (B) +infra | DX/Utility

**PURPOSE** — The chi `middleware.RequestID` is registered in `api/routes/routes.go` line 17 but is never propagated to any log call. Request correlation is impossible — a single error log cannot be traced back to the HTTP request that caused it.

**WHAT TO DO**
1. In `api/routes/routes.go`, add a new middleware after `middleware.RequestID` (line 17) that extracts the request ID and injects it into the request context for slog:
   ```go
   r.Use(func(next http.Handler) http.Handler {
       return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
           requestID := middleware.GetReqID(r.Context())
           ctx := r.Context()
           if requestID != "" {
               logger := slog.Default().With("request_id", requestID)
               ctx = context.WithValue(ctx, slogContextKey, logger)
           }
           next.ServeHTTP(w, r.WithContext(ctx))
       })
   })
   ```
2. Create a small helper in `api/routes/routes.go` (or a new `api/logging/context.go` if preferred) that extracts the logger from context:
   ```go
   func LoggerFromContext(ctx context.Context) *slog.Logger {
       if logger, ok := ctx.Value(slogContextKey).(*slog.Logger); ok {
           return logger
       }
       return slog.Default()
   }
   ```
3. In `api/handlers/rooms.go` and `api/handlers/handlers.go`, use `routes.LoggerFromContext(r.Context())` instead of bare `slog.Info`/`slog.Error` for request-scoped logging.

**DONE WHEN**
- [ ] A log line emitted during a request handler includes a `request_id` field matching the `X-Request-Id` response header.
- [ ] Two concurrent requests produce logs with different `request_id` values.
- [ ] `go build ./...` succeeds.

---

### Task 11 (A) +refactor | DX/Utility

**PURPOSE** — Error classification in `api/handlers/rooms.go` line 636–647 (`connectProviderStatus`) uses `strings.Contains(err.Error(), "forbidden")` to determine HTTP status codes. This is fragile — any change to the error message string in `service.go` silently breaks status code mapping.

**WHAT TO DO**
1. In `api/rooms/service.go`, define sentinel errors at the top of the file:
   ```go
   var (
       ErrForbidden        = errors.New("forbidden")
       ErrRoomNotFound     = errors.New("room not found")
       ErrRoomClosed       = errors.New("room is closed")
       ErrSessionExpired   = errors.New("room session expired")
       ErrSessionInvalid   = errors.New("invalid room session")
       ErrProviderNotConnected = errors.New("provider is not connected")
   )
   ```
2. Replace `fmt.Errorf("forbidden")` at lines 249, 284, 358, 538, 575, 605, 624, 652, 705, 796, 825, 851, 877 with `ErrForbidden`. Use `fmt.Errorf("...: %w", ErrForbidden)` when wrapping with additional context.
3. Replace `fmt.Errorf("room not found")` at line 1099 with `ErrRoomNotFound`.
4. Replace `fmt.Errorf("room is closed")` at line 160 with `ErrRoomClosed`.
5. Replace `fmt.Errorf("room session expired")` at line 246 with `ErrSessionExpired`.
6. Replace `fmt.Errorf("invalid room session")` at line 243 with `ErrSessionInvalid`.
7. Replace `fmt.Errorf("provider is not connected")` at line 1072 with `ErrProviderNotConnected`.
8. In `api/handlers/rooms.go` function `connectProviderStatus` (line 636–647), replace string matching with:
   ```go
   func connectProviderStatus(err error) int {
       switch {
       case err == nil:
           return http.StatusOK
       case errors.Is(err, rooms.ErrForbidden):
           return http.StatusForbidden
       default:
           return http.StatusBadRequest
       }
   }
   ```
9. In `api/handlers/handlers.go` line 80, replace `strings.Contains(err.Error(), "invalid cursor")` with a similar pattern: define `var ErrInvalidCursor = errors.New("invalid cursor")` in `api/models/models.go` and wrap cursor errors with it.

**DONE WHEN**
- [ ] No `strings.Contains(err.Error()` patterns remain in `api/handlers/`.
- [ ] `errors.Is(err, rooms.ErrForbidden)` correctly identifies forbidden errors.
- [ ] Existing tests pass: `cd api && go test ./...`.

---

### Task 12 (B) +bugfix | DX/Utility

**PURPOSE** — In `api/rooms/service.go` lines 259 and 263, the results of updating participant `last_seen_at` and room `last_active_at` are silently discarded with `_ =`. If these updates fail (e.g., DB locked, disk full), the room's activity tracking silently becomes stale, making room expiry logic (`closeExpiredRooms`) unreliable.

**WHAT TO DO**
1. In `api/rooms/service.go` function `Authenticate` (lines 225–272), replace lines 259–263:
   ```go
   _ = config.AppDB.WithContext(ctx).Model(&participant).Updates(map[string]any{
       "last_seen_at": now,
       "updated_at":   now,
   }).Error
   _ = config.AppDB.WithContext(ctx).Model(&room).Update("last_active_at", now).Error
   ```
   with logged-but-non-fatal errors:
   ```go
   if err := config.AppDB.WithContext(ctx).Model(&participant).Updates(map[string]any{
       "last_seen_at": now,
       "updated_at":   now,
   }).Error; err != nil {
       slog.Warn("failed to update participant last_seen_at", "error", err, "participant_id", participant.ID)
   }
   if err := config.AppDB.WithContext(ctx).Model(&room).Update("last_active_at", now).Error; err != nil {
       slog.Warn("failed to update room last_active_at", "error", err, "room_slug", room.Slug)
   }
   ```
2. Similarly in `AddFinalist` (line 556), `_ = config.AppDB...Scan(&maxPosition).Error` — log the error:
   ```go
   if err := config.AppDB.WithContext(ctx).Model(&RoomFinalistEntry{}).
       Where("room_id = ?", viewer.Room.ID).
       Select("COALESCE(MAX(position), 0)").
       Scan(&maxPosition).Error; err != nil {
       slog.Warn("failed to get max finalist position", "error", err, "room_id", viewer.Room.ID)
   }
   ```

**DONE WHEN**
- [ ] `grep '_ = config.AppDB' api/rooms/service.go` returns zero matches.
- [ ] A simulated DB error during `Authenticate` produces a warning-level log line (not a 500 error to the client).
- [ ] Existing tests pass: `cd api && go test ./...`.

---

### Task 13 (A) +bugfix | DX/Utility

**PURPOSE** — The frontend SSE connection in `RoomView.tsx` line 404 closes on any error with no logging, no retry, and no user notification. Once the connection drops, the room becomes stale silently — participants see outdated data with no indication. The server side (`handlers/rooms.go` lines 177–185) has no heartbeat mechanism, so the client cannot distinguish "server is alive but idle" from "connection died."

**WHAT TO DO**
1. **Server heartbeat:** In `api/handlers/rooms.go` function `StreamRoomEvents` (lines 147–186), add a periodic heartbeat inside the `for` loop. Add a `time.Ticker` at 15-second intervals that sends a comment line:
   ```go
   ticker := time.NewTicker(15 * time.Second)
   defer ticker.Stop()
   for {
       select {
       case <-ctx.Done():
           return
       case event := <-eventChannel:
           writeSSEEvent(w, event)
           flusher.Flush()
       case <-ticker.C:
           fmt.Fprintf(w, ": heartbeat\n\n")
           flusher.Flush()
       }
   }
   ```
2. **Client reconnection:** In `kilter-together-app/src/components/RoomView.tsx` lines 391–412, replace the current SSE setup with reconnection logic:
   ```typescript
   eventSource.onerror = () => {
     eventSource.close();
     // reconnect after 3 seconds
     const retryTimeout = window.setTimeout(() => {
       void refreshRoomState();
     }, 3000);
     return () => window.clearTimeout(retryTimeout);
   };
   ```
   Use a ref to track the retry timeout and clean it up in the effect cleanup function. Cap retries at 5 attempts to avoid infinite reconnection loops on auth failure.
3. **Server write errors:** In `api/handlers/rooms.go` function `writeSSEEvent` (lines 655–658), check for write errors and return a bool indicating success. In the `StreamRoomEvents` loop, if a write fails, return early (client disconnected).

**DONE WHEN**
- [ ] An SSE client that stays connected for 20 seconds receives at least one `: heartbeat` comment line.
- [ ] When the SSE connection is interrupted (simulate by restarting the server), the client reconnects within 5 seconds and receives a fresh event.
- [ ] After 5 failed reconnection attempts, the client stops retrying.
- [ ] Existing tests pass.

---

### Task 14 (B) +security | DX/Utility

**PURPOSE** — HTTP error responses in `api/handlers/handlers.go` line 50 include raw decoder error messages (`"failed to decode query params: " + err.Error()`), and line 84 includes raw DB errors (`"failed to retrieve climbs: " + err.Error()`). These leak internal implementation details (table names, column names, query structures) to API consumers.

**WHAT TO DO**
1. In `api/handlers/handlers.go` line 50, change:
   ```go
   writeJSONError(w, http.StatusBadRequest, "failed to decode query params: "+err.Error())
   ```
   to:
   ```go
   writeJSONError(w, http.StatusBadRequest, "invalid query parameters")
   ```
   Log the full error server-side: `slog.Warn("failed to decode query params", "error", err)`.
2. In `api/handlers/handlers.go` line 84, change:
   ```go
   writeJSONError(w, http.StatusInternalServerError, "failed to retrieve climbs: "+err.Error())
   ```
   to:
   ```go
   slog.Error("failed to retrieve climbs", "error", err)
   writeJSONError(w, http.StatusInternalServerError, "failed to retrieve climbs")
   ```
3. In `api/handlers/handlers.go` line 105, change:
   ```go
   writeJSONError(w, http.StatusInternalServerError, "failed to retrieve board options: "+err.Error())
   ```
   to:
   ```go
   slog.Error("failed to retrieve board options", "error", err)
   writeJSONError(w, http.StatusInternalServerError, "failed to retrieve board options")
   ```
4. In `api/handlers/rooms.go`, lines 92 and 97 expose `err.Error()` to clients. Replace with generic messages and log the full error server-side.

**DONE WHEN**
- [ ] No HTTP JSON error response in `api/handlers/` contains `err.Error()` concatenated into user-facing messages (exceptions: auth-related messages that are already generic like "invalid request body").
- [ ] A malformed query string to `GET /api/climbs` returns `{"error":"invalid query parameters"}` without internal details.
- [ ] The full error is logged server-side at warn or error level.
- [ ] Existing tests pass.

---

### Task 15 (B) +test | DX/Utility

**PURPOSE** — Provider connection validation (Kilter login, Crux token auth) has zero test coverage. The only provider test is `crux_test.go` which only tests `normalizeCruxToken`. If authentication logic regresses, no test catches it before production.

**WHAT TO DO**
1. Create `api/providers/kilter_test.go`. Test:
   - `parseKilterClimbID` with valid input `"kilter:14:abc-123"` → boardID=14, uuid="abc-123".
   - `parseKilterClimbID` with invalid input `"crux:123"` → error.
   - `parseKilterContext` with missing board ID → error.
   - `parseKilterContext` with unsupported angle → error.
   - `mapKilterClimbs` with an empty slice → empty result.
2. Expand `api/providers/crux_test.go`. Add tests:
   - `parseCruxClimbID` with valid input `"crux:456"` → 456.
   - `parseCruxClimbID` with invalid input `"kilter:14:uuid"` → error.
   - `decodeOffsetCursor` with empty string → 0.
   - `decodeOffsetCursor` with valid base64 → correct offset.
   - `decodeOffsetCursor` with negative offset → error.
   - `sortCruxClimbs` with "newest" sort → descending by CreatedAt.
   - `sortCruxClimbs` with "popular" sort → descending by NumberOfSends.

**DONE WHEN**
- [ ] `cd api && go test ./providers/...` passes with all new tests.
- [ ] At least 5 test cases in `kilter_test.go` and 7 in `crux_test.go`.

---

### Task 16 (B) +test | DX/Utility

**PURPOSE** — Room permission boundaries (guest vs host) have no dedicated test coverage. If a guest gains access to host-only endpoints (AddFinalist, ReorderQueue, CloseRoom, RemoveParticipant), the collaborative session model breaks.

**WHAT TO DO**
1. In `api/routes/rooms_routes_test.go`, add a test section that:
   - Creates a room (gets host cookie).
   - Joins the room as a guest (gets participant cookie).
   - Attempts host-only operations using the guest cookie:
     - `POST /api/rooms/{slug}/finalists` → expects 401 Unauthorized.
     - `PATCH /api/rooms/{slug}/finalists/reorder` → expects 401 Unauthorized.
     - `POST /api/rooms/{slug}/queue/promote` → expects 401 Unauthorized.
     - `PATCH /api/rooms/{slug}/queue/reorder` → expects 401 Unauthorized.
     - `POST /api/rooms/{slug}/close` → expects 401 Unauthorized.
     - `DELETE /api/rooms/{slug}/participants/{hostId}` → expects 401 Unauthorized.
   - Verifies guest CAN:
     - `PUT /api/rooms/{slug}/votes/{climbId}` → expects 200 OK.
     - `POST /api/rooms/{slug}/queue` → expects 201 Created.
     - `PUT /api/rooms/{slug}/participants/me/status` → expects 200 OK.

**DONE WHEN**
- [ ] All permission boundary test cases pass: `cd api && go test ./routes/...`.
- [ ] At least 9 test assertions covering guest-forbidden and guest-allowed operations.

---

### Task 17 (B) +test | DX/Utility

**PURPOSE** — Pagination edge cases (empty results, last page exactly at boundary, malformed cursor, `page_size=0`, `page_size=999`) have no test coverage. These are common sources of off-by-one errors and panics in production.

**WHAT TO DO**
1. In `api/routes/routes_test.go`, add test cases:
   - `GET /api/climbs?angle=40&page_size=0` → should default to `page_size=10` (verify by response `page_size` field).
   - `GET /api/climbs?angle=40&page_size=999` → should clamp to `page_size=10` (per existing logic in `handlers.go` lines 54–57).
   - `GET /api/climbs?angle=40&cursor=INVALID_BASE64` → should return 400 with "invalid cursor" error.
   - `GET /api/climbs?angle=40&page_size=1` → paginate through all results one at a time until `has_more=false`, verify no duplicates across pages.
   - `GET /api/climbs?angle=40&name=ZZZZNONEXISTENT` → should return empty climbs array with `has_more=false`.

**DONE WHEN**
- [ ] All pagination edge-case tests pass: `cd api && go test ./routes/...`.
- [ ] At least 5 new test cases covering boundary conditions.

---

### Task 18 (A) +infra | Stability/Scaling

**PURPOSE** — No rate limiting exists on any endpoint. A single client can create unlimited rooms, hammer provider authentication (which calls external APIs), or spam climb catalog searches. Pre-launch, this is a denial-of-service vector and could result in IP bans from upstream providers (Kilter, Crux).

**WHAT TO DO**
1. Add `golang.org/x/time` as a dependency: `cd api && go get golang.org/x/time/rate`.
2. In `api/routes/routes.go`, add a rate limiting middleware after line 18 (`middleware.RealIP`):
   ```go
   r.Use(httprate.LimitByIP(100, time.Minute))
   ```
   Use the `github.com/go-chi/httprate` package (chi-ecosystem compatible) or implement with `golang.org/x/time/rate` and a sync.Map of per-IP limiters.
3. Apply a stricter limit to write endpoints. Inside the `/api/rooms` route group, add a separate limiter for `POST` routes: 10 room creations per minute per IP.
4. Apply a stricter limit to provider connection: `POST /api/rooms/{slug}/provider/connect` should be limited to 5 attempts per minute per IP (to protect upstream provider APIs from brute-force credential testing).

**DONE WHEN**
- [ ] A client sending 101 requests to `GET /api/climbs` within 1 minute receives a `429 Too Many Requests` on the 101st request.
- [ ] A client creating 11 rooms within 1 minute receives a `429` on the 11th.
- [ ] Normal usage (< 100 req/min) is unaffected.
- [ ] `go build ./...` succeeds.

---

### Task 19 (B) +security | Stability/Scaling

**PURPOSE** — Auth cookies in `api/handlers/rooms.go` lines 625–633 set `HttpOnly: true` and `SameSite: Lax` but omit `Secure: true`. Without the `Secure` flag, cookies are transmitted over plaintext HTTP, making session hijacking trivial on non-HTTPS connections. For public launch, this must be configurable.

**WHAT TO DO**
1. In `api/config/runtime.go`, add a new field `SecureCookies bool` to `RuntimeConfig`. Load from env var `KILTER_TOGETHER_SECURE_COOKIES` (default: `true` for production, override to `false` for local dev).
2. In `api/handlers/rooms.go` function `setSignedCookie` (lines 619–634), add `Secure: config.GetRuntimeConfig().SecureCookies` to the `http.Cookie` struct (after line 630).
3. In `api/.env.example`, add `KILTER_TOGETHER_SECURE_COOKIES=true` with a comment explaining it should be `false` for local HTTP development.

**DONE WHEN**
- [ ] With `KILTER_TOGETHER_SECURE_COOKIES=true`, cookies include the `Secure` flag (verify via `Set-Cookie` response header).
- [ ] With `KILTER_TOGETHER_SECURE_COOKIES=false` (or unset for dev), cookies omit `Secure` to allow HTTP dev.
- [ ] Existing tests pass.

---

### Task 20 (B) +security | Stability/Scaling

**PURPOSE** — No explicit CORS middleware is configured in `api/routes/routes.go`. The chi default does not set CORS headers, which means the frontend on a different origin (e.g., `localhost:5173` during dev, or a separate domain in production) will have requests blocked by the browser. Additionally, without an explicit allowlist, a deployed API could be called from any origin.

**WHAT TO DO**
1. In `api/config/runtime.go`, add a new field `AllowedOrigins []string` to `RuntimeConfig`. Load from env var `KILTER_TOGETHER_ALLOWED_ORIGINS` (comma-separated, e.g., `http://localhost:5173,https://kilter.example.com`). Default to `*` for dev convenience.
2. Add `github.com/go-chi/cors` dependency: `cd api && go get github.com/go-chi/cors`.
3. In `api/routes/routes.go`, add CORS middleware before the route definitions (after line 18):
   ```go
   r.Use(cors.Handler(cors.Options{
       AllowedOrigins:   config.GetRuntimeConfig().AllowedOrigins,
       AllowedMethods:   []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
       AllowedHeaders:   []string{"Accept", "Content-Type", "Authorization"},
       AllowCredentials: true,
       MaxAge:           300,
   }))
   ```
4. In `api/.env.example`, add `KILTER_TOGETHER_ALLOWED_ORIGINS=http://localhost:5173`.

**DONE WHEN**
- [ ] A preflight `OPTIONS` request to `/api/climbs` from `http://localhost:5173` returns `Access-Control-Allow-Origin: http://localhost:5173`.
- [ ] A request from an unlisted origin (when not using `*`) does not receive CORS headers.
- [ ] Existing tests pass.

---

### Task 21 (B) +test | Stability/Scaling

**PURPOSE** — `ServeImage` in `api/handlers/handlers.go` lines 141–159 uses `filepath.Base` and `strings.Contains` checks to prevent directory traversal. The implementation is correct, but it has zero test coverage. If a future refactor accidentally removes the `filepath.Base` call, there is no test to catch the regression.

**WHAT TO DO**
1. In `api/routes/routes_test.go`, add test cases for `GET /api/images/{filename}`:
   - Valid filename `"original-16x12-bolt-ons-v2.png"` → 200 (if file exists in test image dir) or appropriate status.
   - Path traversal attempt `"../../../etc/passwd"` → after `filepath.Base`, becomes `passwd` → 404 (file not found, not 200 with /etc/passwd content).
   - Path traversal with encoded slashes `"..%2F..%2Fetc%2Fpasswd"` → verify Base sanitization handles this.
   - Empty filename → 400 "filename is required".
   - Filename with null byte `"test\x00.png"` → verify no path injection.
2. Set up a temp directory with a known test image file in the test setup, and configure `RuntimeConfig.ImageDir` to point to it.

**DONE WHEN**
- [ ] All 5 path traversal test cases pass: `cd api && go test ./routes/...`.
- [ ] No test case returns the contents of a file outside `ImageDir`.

---

### Task 22 (B) +security | Stability/Scaling

**PURPOSE** — No maximum length is enforced on `nameFilter`, `setterFilter` (from `api/handlers/handlers.go` line 19–27 `GetClimbsParams`), `displayName` (from `api/handlers/rooms.go` line 21–26), or other string inputs. An attacker could send a 10MB name filter string, consuming memory and potentially causing slow LIKE queries.

**WHAT TO DO**
1. In `api/handlers/handlers.go` function `GetClimbs` (line 46), after decoding params, clamp string lengths:
   ```go
   if len(params.Name) > 200 {
       params.Name = params.Name[:200]
   }
   if len(params.Setter) > 200 {
       params.Setter = params.Setter[:200]
   }
   ```
2. In `api/handlers/rooms.go` function `CreateRoom` (line 70), after decoding the request, clamp:
   ```go
   if len(request.DisplayName) > 50 {
       request.DisplayName = request.DisplayName[:50]
   }
   ```
3. Apply the same 50-char limit to `JoinRoom` (line 104) for `request.DisplayName`.
4. In `api/handlers/rooms.go` function `ListRoomCatalogClimbs` (line 250), clamp the `q` search parameter:
   ```go
   search := r.URL.Query().Get("q")
   if len(search) > 200 {
       search = search[:200]
   }
   ```

**DONE WHEN**
- [ ] A `GET /api/climbs?angle=40&name=AAAA...` (300 chars) works but the name filter is truncated to 200 chars in the query.
- [ ] A room creation with a 100-char display name stores only the first 50 chars.
- [ ] Existing tests pass.

---

### Task 23 (B) +infra | Stability/Scaling

**PURPOSE** — No request/response logging middleware exists beyond chi's default `middleware.Logger` (which logs minimal info to stdout in plaintext). For observability, every request should be logged with method, path, status code, latency, and request ID in structured JSON format.

**WHAT TO DO**
1. In `api/routes/routes.go`, replace `middleware.Logger` (line 15) with a custom structured logger middleware that uses `slog`:
   ```go
   r.Use(func(next http.Handler) http.Handler {
       return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
           start := time.Now()
           ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
           next.ServeHTTP(ww, r)
           slog.Info("http request",
               "method", r.Method,
               "path", r.URL.Path,
               "status", ww.Status(),
               "duration_ms", time.Since(start).Milliseconds(),
               "request_id", middleware.GetReqID(r.Context()),
               "remote_addr", r.RemoteAddr,
           )
       })
   })
   ```
2. This replaces Task 10's request ID propagation for log lines emitted by the middleware itself. Task 10 handles propagation into handler-level logging.

**DONE WHEN**
- [ ] Every HTTP request produces a structured JSON log line with `method`, `path`, `status`, `duration_ms`, and `request_id`.
- [ ] `middleware.Logger` is no longer in the middleware stack (replaced by the structured version).
- [ ] `go build ./...` succeeds.

---

### Task 24 (B) +bugfix | Stability/Scaling

**PURPOSE** — In `api/handlers/rooms.go` function `writeSSEEvent` (lines 655–658), both `json.Marshal` and `fmt.Fprintf` errors are silently discarded. If JSON marshaling fails, the client receives a malformed event. If the write fails (client disconnected), the server keeps trying to write to a dead connection until `ctx.Done()`.

**WHAT TO DO**
1. Change `writeSSEEvent` signature to return a `bool`:
   ```go
   func writeSSEEvent(w http.ResponseWriter, payload rooms.EventPayload) bool {
       eventBytes, err := json.Marshal(payload)
       if err != nil {
           slog.Warn("failed to marshal SSE event", "error", err)
           return false
       }
       if _, err := fmt.Fprintf(w, "event: room\ndata: %s\n\n", string(eventBytes)); err != nil {
           return false
       }
       return true
   }
   ```
2. In `StreamRoomEvents` (lines 177–185), check the return value:
   ```go
   case event := <-eventChannel:
       if !writeSSEEvent(w, event) {
           return
       }
       flusher.Flush()
   ```
3. Apply the same pattern to the initial event write (line 173) and heartbeat writes (if Task 13 is implemented).

**DONE WHEN**
- [ ] A disconnected SSE client causes the server goroutine to exit within one event cycle (not hang until `ctx.Done()`).
- [ ] A JSON marshal failure logs a warning instead of sending corrupt data.
- [ ] Existing tests pass.

---

### Task 25 (C) +security | Stability/Scaling

**PURPOSE** — Encryption in `api/security/crypto.go` uses a single hardcoded key from `KILTER_TOGETHER_ENCRYPTION_KEY`. If the key is compromised, all provider secrets (Kilter passwords, Crux tokens) stored in `RoomProviderConnection.SecretCiphertext` must be re-encrypted manually. There is no versioning or rotation mechanism.

**WHAT TO DO**
1. In `api/config/runtime.go`, add a new optional field `PreviousEncryptionKey string` loaded from env var `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY`.
2. In `api/rooms/service.go` function `providerForRoom` (lines 1065–1086), after decryption fails with the current key (line 1075), attempt decryption with the previous key:
   ```go
   decrypted, err := security.DecryptString(config.GetRuntimeConfig().EncryptionKey, connection.SecretCiphertext)
   if err != nil && config.GetRuntimeConfig().PreviousEncryptionKey != "" {
       decrypted, err = security.DecryptString(config.GetRuntimeConfig().PreviousEncryptionKey, connection.SecretCiphertext)
       if err == nil {
           // re-encrypt with new key
           reEncrypted, reErr := security.EncryptString(config.GetRuntimeConfig().EncryptionKey, decrypted)
           if reErr == nil {
               config.AppDB.WithContext(ctx).Model(&connection).Update("secret_ciphertext", reEncrypted)
           }
       }
   }
   if err != nil {
       return nil, nil, err
   }
   ```
3. In `api/.env.example`, add `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY=` with a comment explaining key rotation workflow.

**DONE WHEN**
- [ ] A secret encrypted with the old key can be decrypted when `KILTER_TOGETHER_PREVIOUS_ENCRYPTION_KEY` is set to the old key.
- [ ] After successful decryption with the old key, the stored ciphertext is re-encrypted with the new key (verify by reading the DB row).
- [ ] If both keys fail, the error propagates normally.
- [ ] Existing tests pass: `cd api && go test ./...`.
