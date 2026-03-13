# Kilter Together Product Plan

This repo now carries a persona-driven implementation plan so product work stays tied to actual user journeys instead of isolated feature requests.

The current mobile-first functional requirements spec for the highest-urgency
collaborative flow lives in [P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md](./P1_P2_COLLABORATIVE_FLOW_REQUIREMENTS.md).

## Personas

### 1. Session Captain
- Uses the app to create the room, authenticate the provider, choose the shared surface, invite guests, and run the session.
- Needs fast setup, low-friction credential handling, clear readiness signals, and reliable room controls.
- Current implementation focus:
  - typed room/provider error responses
  - clearer “room ready to share” state
  - provider capability discovery instead of hardcoded assumptions

### 2. Phone-First Guest
- Joins from a phone by QR code or invite URL, picks a display name, votes, and adds climbs to the queue.
- Needs clean join failures, quick rename/rejoin recovery, and obvious next actions.
- Current implementation focus:
  - `display_name_taken`, `session_expired`, `session_invalid`, and `room_closed` error codes
  - inline join guidance and rejoin messaging
  - QR scanner failure reporting outside the browser console

### 3. Solo Project Researcher
- Uses solo browse to scout Kilter climbs, compare options, and return later.
- Needs stronger discovery and persistence than the current basic browse flow.
- Delivered in the current implementation:
  - grade-aware, setter, name, and sort filters
  - favorites, shortlist, and saved filter presets
  - resume links plus room seeding from shortlist or board context

### 4. Crux Gym Regular
- Uses Crux-backed room flows and expects gym/wall terminology, wall-aware selection, and provider-specific metadata.
- Needs the UI to reflect provider differences without becoming fragmented.
- Delivered in the current implementation:
  - provider capabilities declare `surface_hierarchy`
  - frontend adapts board vs nested surface flows from capability data
  - Crux solo browse is available through the provider-specific solo route
  - Crux climb cards and detail views now surface source, color, and foot-rule metadata

### 5. Community Self-Host Operator
- Runs bootstrap, configures secrets, observes runtime health, and diagnoses production issues.
- Needs more than terminal logs and browser devtools to support the app confidently.
- Delivered in the current implementation:
- protected operator status endpoint
- Prometheus/Grafana/Loki/Tempo/Alertmanager/Alloy stack
- Sentry-compatible GlitchTip integration path for frontend/backend exceptions
- production Alertmanager templates, routing examples, and an operator drilldown workflow

## Delivered In This Tranche

- Loading slideshow interval reduced to `300ms`.
- Machine-readable room/provider/session error responses with request and trace metadata.
- Provider capability endpoint at `/api/providers/capabilities`.
- Protected operator status endpoint at `/api/operator/status`.
- Backend tracing, structured request IDs, and Sentry-compatible error hooks.
- Frontend capability-aware provider selection and typed join/load error handling.
- `co_host` permissions, session summaries, recent sessions, and host defaults.
- Solo favorites, shortlist, saved filters, grade filtering, and room seeding from solo context.
- Self-hosted observability stack config under [`observability/`](/Users/gongahkia/Desktop/coding/projects/kilter-together/observability) and [`docker-compose.observability.yml`](/Users/gongahkia/Desktop/coding/projects/kilter-together/docker-compose.observability.yml).

## Remaining Optional Follow-Ups

- Hosted incident tooling outside the repo, such as a dedicated NOC dashboard, ticketing bot, or centralized organization-wide GlitchTip deployment.
