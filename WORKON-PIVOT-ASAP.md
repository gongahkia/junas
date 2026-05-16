# Aki — Adoption Pivot

## North star
Be the default privacy filter that devs reach for when they stream, record, or screen-share on macOS. Optimize for installs and stars, not revenue.

## Decisions (locked)
| Axis | Choice |
|---|---|
| Audience | Devs who stream / record / Loom |
| Platform (v1) | macOS-first, signed `.dmg` + Homebrew cask |
| Monetization | Pure FOSS (MIT). No telemetry, no upsell, no Sponsor button yet |
| Scope | Keep Rust engine, replace TUI with menu-bar app as primary surface; TUI stays as `--tui` power-user mode |
| Hero demo | Live `export AWS_SECRET_ACCESS_KEY=AKIA...` in iTerm → ASCII redaction on virtual-cam preview |
| Launch | Slow burn / Twitter-first → Show HN once metrics + polish hit threshold |

## Positioning (one sentence)
*Aki is a real-time privacy filter for screen sharing that detects secrets and PII on your screen and redacts them before the pixels leave your machine.* Local-first. Open source. macOS.

## Carry-overs from commercial-viability research
Takeaways that still matter even though we're not selling:
- Category is real and validated (BlurScreen $19, Loom blur gated to Business, Chrome ext ecosystem). [Inference] No need to educate the market that this problem exists.
- DOM-based blur tools (Loom, ContextBlur, DataBlur) break on Notion / Figma / Google Docs / terminals. Aki's OCR-pixel approach covers exactly the surfaces they miss. **Lead with this in copy.**
- Enterprise DLP space ($20–200/user/yr) is irrelevant to v1 — they want Windows + policy + audit. Ignore. Revisit only if a contributor wants to ship a `aki-enterprise` fork.
- Streamers leaking keys on stream is a recurring viral moment. Every incident is a free distribution event if Aki is the first result for "blur api key stream mac".

## Carry-overs from HN / stars research
- Comparable Show HNs (30ms screen sharing in Rust; screen capture + OCR SDK in Rust; Omni-Glass) all hit front page. Aki has a sharper narrative hook than any of them.
- HN reviewers will hit on: OCR latency, Tesseract accuracy on small text, regex brittleness, "Prevent vs reduce" framing. Pre-empt all four in README.
- [Speculation] Realistic v1 ceiling: 1k–10k stars first week if launch is clean; long tail driven by every "I leaked my key on stream" tweet.

## What stays
- 4-thread crossbeam pipeline (capture → detect → transform → output). Genuine engineering moat.
- Incremental OCR + adaptive 8×6 grid story — that's the HN-comment-section answer to "isn't OCR per-frame slow?"
- All five transforms. ASCII stays the hero (signature visual).
- ScreenCaptureKit + CoreMediaIO DAL path. Already wired.
- TUI lives on as `aki --tui` for HN crowd, demos, and headless setups.

## What changes
- **Primary UI**: macOS menu-bar app (SwiftUI shell calling the Rust core via FFI / sidecar binary). Source picker, transform dropdown, output dropdown, pause, stats line. That's it.
- **Install**: signed `.dmg` + `brew install --cask aki` (tap, no formula gymnastics). `cargo run` stops being step 1.
- **README**: hero GIF up top (the `export AKIA…` → ASCII demo). Install in 3 lines. Detected-types badge grid. Architecture diagram moves below the fold.
- **Version sanity**: `Cargo.toml` says 0.1.0; badge says 1.0.0 passing. Pick one and align before anyone screenshots it.
- **Honest copy**: replace any "prevents leaks / ensures privacy" language with "reduces leak risk" or "redacts detected secrets". Honest framing is itself a HN-comment-section win. (Matches CLAUDE.md inference-labelling directive.)

## What's new (build list, ordered)
1. Fix README install block (it currently ends on an empty `$` line — line 36–37). Anything else is wasted polish until this is done.
2. Record hero GIF. iTerm + virtual-cam preview side-by-side. ≤10s loop. `.webm` or asciinema for the terminal half. Pin at top of README.
3. SwiftUI menu-bar shell. Calls existing Rust binary as a sidecar (no FFI complexity in v1). Layout per the mock the user picked:
   ```
   ┌──────────────────────────────────┐
   │  Aki  ● REC                      │
   ├──────────────────────────────────┤
   │ Source:  iTerm2          ▾       │
   │ Transform: ASCII         ▾       │
   │ Output:  OBS virtual cam ▾       │
   │ [ Pause ]   [ Open TUI … ]       │
   │ 12 redactions · 28 fps · 6% CPU  │
   └──────────────────────────────────┘
   ```
4. Codesign + notarize. Unsigned macOS apps in 2026 are dead on arrival.
5. Homebrew cask. `brew tap gongahkia/aki && brew install --cask aki` is the README install line.
6. Pre-empt the HN comments — add a `# Known limitations` section: OCR race window on first-frame appearance, Tesseract small-text accuracy, regex-vs-entropy detection tradeoff. Owning these reads as honest, not weak.
7. Adopt gitleaks / trufflehog rule packs as an optional detector source. Stronger detection story, free credibility transfer.
8. Telemetry: explicit `# We collect nothing` line. The privacy crowd checks for this.

## Anti-goals (things to deliberately NOT do)
- No Windows in v1. The audience we picked is Mac-heavy; Windows triples scope.
- No cloud / no account / no sync / no team features.
- No paid tier, no Sponsor button at launch. Anything monetary in the README halves star velocity. [Inference]
- No "AI" framing in copy. Despite the ONNX neural transform, leading with "AI privacy" attracts the wrong crowd and triggers HN allergies.
- No premature SDK / library positioning. We're an app first. Library extraction happens only if real demand shows up.

## Slow-burn → Show HN trigger
Twitter-first means we don't burn the HN launch on a half-polished v1. Gate the Show HN post on all of these being true:
- Signed `.dmg` downloads cleanly on a stock Mac
- `brew install --cask aki` works end-to-end
- Hero GIF is in the README
- At least one external user (not the author) has installed and confirmed it works on their setup
- Known-limitations section is written
- Version numbers are consistent across `Cargo.toml`, badge, releases

[Inference] Hitting all six puts launch quality above the median Show HN, which is usually enough to clear front page given the hook strength.

## Open questions to revisit
- SwiftUI shell ↔ Rust binary: stdio JSON-RPC vs Unix socket vs FFI? Pick during build.
- Codesign cert: personal Developer ID, or set up a project-level identity?
- Do we ship a default-on `redaction log` (local file, what was redacted and when) for users who want to verify nothing slipped through? Useful but adds surface area.
- Homebrew tap name: `gongahkia/aki` vs `gongahkia/tap`? Latter is convention; former is brandable.

---

# Further additions (Phase-2 and beyond)

Everything below is post-v1. Listed in priority order within each section. All items must pass the same filters: FOSS-compatible, macOS-first, dev-streamer-aligned, no telemetry, no cloud, no rebrand to "AI". Anything outside those rails belongs in Stretch or gets cut.

## Phase-2 features (sorted by virality-to-effort ratio)

### Tier S — ship within weeks of v1
- **`aki redact <video.mov>`** — drop a recorded video file, get the same file back with secrets blurred. Same engine, no real-time pressure, no virtual cam needed. Expands TAM from "future streamers" to "anyone with a screen recording sitting on disk". [Inference] Highest-leverage single feature in the doc. Every Loom user is a potential install.
- **`aki demo`** — built-in fake-secret rolling display so users can verify install without setting up a real stream. Doubles as the one-command demo for tweets, issues, and bug reports ("paste `aki demo` output").
- **`aki doctor`** — diagnostic: ScreenCaptureKit perms, CoreMediaIO DAL state, virtual-cam install, OBS reachability, Tesseract data path. Standard pattern (rustup, brew doctor). HN-crowd-pleaser, halves "doesn't work on my machine" issue volume.
- **`# Known limitations` section in README** (already on v1 list at #6; promoted here as a reminder it must ship).

### Tier A — Phase-2 proper
- **Per-app detection profiles auto-selected on foreground window** — iTerm/Alacritty → secrets-heavy ruleset; Slack/Discord → email + PII; VS Code/Cursor → "everything"; browser → DOM-aware fallback. Foreground window is already polled by the source picker; the routing layer is small.
- **Community rule pack repo (`gongahkia/aki-rules`)** — separate repo where every internal-company key format or new SaaS token shape becomes a PR. Stars accrue to both repos; contribution barrier is one regex + one test case. Best community-building moat we have.
- **OBS source plugin** (in addition to virtual cam) — distributable via `obsproject.com/forum/resources`. That site has a built-in streamer audience that doesn't read HN.
- **gitleaks / trufflehog rule-pack import** — optional toggle, instant +200 patterns, free credibility transfer. Mentions both projects in the README, which is itself reciprocal-traffic.

### Tier B — bigger swings, same philosophy
- **Time-machine buffer** — last 30s of frames kept in a ring buffer; if the auto-detector misses something, hotkey scrubs back and retroactively redacts before the recording is finalized. Real-time stream output unaffected (you can't unsend pixels), but Loom/local-recording flow benefits hugely. [Inference] Single most "wow"-able feature for a v2 demo GIF.
- **Local-LLM detector (opt-in, off by default)** — low-confidence OCR regions get classified by a local model (Ollama / Llama / Phi) as secret-shaped or not. Modern and headline-able while remaining local-first. Strictly opt-in so it doesn't drag the default install footprint.
- **AppleScript + Shortcuts entitlements** — "redact last 30s and copy to clipboard" becomes a one-keystroke Raycast / Shortcuts action. macOS power-user signal; very cheap once the menu-bar app exists.
- **Multi-display capture** — currently single source; honest extension once the menu-bar shell is stable.
- **Direct MP4 output sink** — write redacted frames straight to disk, skipping the virtual-cam step. For non-streamers who just want a redacted recording.

## Portfolio-mode additions (this also gets you a job)

The repo gets read by recruiters and senior engineers evaluating you. Each artifact below is cheap and signals seniority well above "side project":

- **`BENCHMARKS.md`** — real numbers, not vibes. FPS at 1080p / 1440p / 4K, end-to-end frame latency, RSS, OCR cell hit-rate, redaction recall on a fixture corpus. The corpus itself (a held-out set of synthetic frames with known secrets) is a separate flex.
- **`ARCHITECTURE.md`** — single page: pipeline diagram, backpressure-shed-not-blocked, the adaptive FrameDiff grid, the 10-frame transform crossfade. 80% already in the README; promote it.
- **Public roadmap as a GitHub Project board** — readers see velocity and direction without asking. Even three columns (Now / Next / Later) is enough.
- **Companion blog post**: *"30 FPS OCR-and-redact on a laptop, in Rust"* — separate HN beat, drives traffic back to the repo. [Inference] Engineering blog posts in this slot routinely outperform the launch post itself.
- **Tag releases with changelogs.** An empty Releases page reads as abandonware regardless of how active `main` is.
- **`CONTRIBUTING.md` + ~5 hand-picked `good first issue`s** — converts star-clickers into contributors, which compounds. Good candidates: "add detector for X", "add OBS scene preset for Y", "improve `aki doctor` output formatting".
- **CI badge that actually means something** — wire `cargo test`, `cargo clippy -- -D warnings`, `cargo fmt --check`, plus a smoke test of the redaction pipeline against fixtures.
- **A SECURITY.md** with a real PGP-or-email reporting path. Cheap; signals adult engineering.

## Distribution & ecosystem hooks

Each is one more discovery surface. None requires changing the core product:
- **Homebrew cask** — canonical install (already in v1 list).
- **`cargo install aki`** — dev / HN install path; one CI step away.
- **Nix flake** — marginal effort, disproportionate goodwill from the privacy/oss crowd.
- **MacUpdate / Setapp listing** — non-dev streamers find apps here, not on GitHub. Free.
- **OBS plugin listing** (per Tier A) — same logic, different community.
- **Pre-written launch copy per platform** — `r/obs`, `r/Twitch`, `r/macapps`, `r/rust`, `r/programming`, HN, Lobste.rs, Bluesky `#rust`, Mastodon. Each platform has different etiquette; drafting them in advance prevents launch-day flailing.
- **Backlink farming via writeups** — guest posts on Tailscale-style engineering blogs, talks at local Rust meetups, conference lightning talks. Each backlink compounds SEO for the "blur api key stream mac" long-tail query.

## Brand & polish (cheap, high leverage)

- **One-page landing site** at `aki.sh` or `getaki.app` — hero GIF, install line, "what it detects" grid, link to repo. Three hours of work. Wins the SEO race for *"hide api key in stream mac"* and similar queries that the GitHub repo itself never will.
- **Logo / wordmark / favicon set** — current `thehand.webp` is fine for the repo but won't scale to a landing page, OG image, or App Store. Cheap commission, lasting payoff.
- **60-second narrated YouTube short** — different surface from the GIF, embedded above it in the README. Some readers watch, some skim.
- **Easter egg**: hold ⌥ while clicking the menu-bar icon → cycles transforms instantly; ⌥⌘-click → opens a hidden "stress test" panel. HN crowd loves these; zero adoption cost.
- **Stickers** — `aki sticker` command outputs a print-ready postcard PDF. Conference-floor virality. [Speculation] Disproportionately memorable for engineering audiences relative to cost.
- **OG / Twitter card image** — generated from the hero GIF. Every shared link previews well, which compounds.

## Stretch (aligned but firmly out of v1/v2 scope)

Listed here so they don't sneak into the build by accident, and so future-you doesn't re-derive them:
- **Face / webcam blur** — same OCR-pipeline philosophy applied to a face-detector model. Different input domain (webcam, not screen). Likely a sister project (`aki-face`?), not a feature inside Aki.
- **Audio redaction** — bleep "my password is…". Philosophically against Aki's visual-only frame; skip unless someone forks it and it works.
- **Browser extension companion** — DOM-aware blur for sub-12px text that OCR struggles with. Different codebase; only worth pursuing if v1 hits a real accuracy ceiling.
- **Headless server mode** — Aki as a CI / staging-room redactor for screen-recording SaaS to pipe video through. Sounds like a library extraction; revisit only after real inbound interest.
- **Windows port** — only after Aki is dominant in its macOS niche. Different capture stack, different virtual-cam stack, different signing story.

## Anti-goals reaffirmed
Re-stating here because Phase-2 is exactly where mission-drift starts:
- No accounts, no cloud, no telemetry, no paid tier.
- No Windows until macOS adoption is settled.
- No "AI-powered" rebrand even after adding the local-LLM detector. The framing stays concrete: *"detects secrets and PII on your screen and redacts them."*
- No feature whose primary justification is "monetizable later." Every Phase-2 addition must earn its keep on adoption alone.

## Success metrics (track these, ignore the rest)

For each phase, the only numbers that matter:
- **v1**: GitHub stars, Homebrew install count, completed install funnel (download → first redaction), `aki doctor` pass-rate.
- **Phase-2**: `aki redact <file>` invocation count (if we ship an opt-in counter) or proxy via release-download deltas, community rule-pack PR cadence, OBS plugin downloads, contributor count.
- **Vanity-but-real**: front-page time on Show HN, peak concurrent stargazers, mentions per week on dev Twitter / Bluesky.

[Inference] Tracking revenue, retention cohorts, or "MAU" here would be both impossible (no telemetry) and the wrong objective. Adoption metrics are downloads + stars + contributors + mentions; everything else is noise.
