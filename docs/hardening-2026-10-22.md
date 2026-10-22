# Local hardening changes, 22 October 2026

This branch changes privacy and persistence behavior. It has not been deployed or
published. README.md files are intentionally unchanged.

## Compatibility and recovery

- Irreversible `/anonymize` and `/redact` responses keep policy outcomes, finding
  IDs, rules, severity and offsets, while omitting raw span values, nested detector
  text, metadata previews, suggestion rationales and free-form advisory output.
  `/anonymize` keeps an empty `matched_text` field for response compatibility.
  Use `/review` in a trusted context when original span diagnostics are required.
- Default journal snapshots hash known nested text-bearing fields as well as top-level
  spans. The existing explicit `JUNAS_REVIEW_PERSIST_SPANS=1` opt-in still permits
  raw span retention. Existing journals are not rewritten: doing so would break
  their HMAC chains. Handle older retained records under your retention policy.
- Tenant identity is preserved until the filesystem boundary. Ordinary lowercase
  IDs keep their paths; IDs containing unsafe punctuation, uppercase characters, long
  names or reserved filesystem components use a separate hash namespace. This
  also applies to tenant surfacing configuration. Older ambiguous paths may have
  mixed tenants. Review and separate those records before any manual migration;
  no automatic migration or deletion occurs.
- Journals, subject indexes and mapping writes now use bounded process-shared
  local file locks, supporting the production launcher's multiple workers.
  Keep lock files in place while the service runs. Network-filesystem semantics
  and Windows runtime behavior require separate validation.
- New audit packs use schema version 2. The signed manifest binds every member's
  bytes and records the verified journal snapshot and signing-key version. The
  verifier checks a single-review slice, which can start after sequence zero and
  omit interleaved reviews. Whole-chain verification is the exporter's signed
  attestation; omitted records are not independently replayed from the pack.
  Older packs without signed member hashes fail closed and require re-export.

## Correctness and privacy

Crossing detection spans now retain their uncovered tails during replacement.
Public gaps and unapproved finding spans remain outside a rewrite selection.
The browser adapter binds an approval to the same connected composer and exact
text, serializes repeated submit actions and blocks malformed review responses.
Validation responses retain schema diagnostics without echoing submitted values.

The SG NRIC rationale acknowledges consent/deemed consent and authorised legal
bases. The 31 December 2026 date concerns NRIC authentication phase-out, as stated
in the [MDDI notice](https://www.mddi.gov.sg/newsroom/responsible-use-of-nric-numbers-across-public-and-private-sectors/).
The UEN rationale distinguishes purpose limitation (PDPA s18) from notification
(s20). Detection and configured review policy do not determine statutory liability.

## Validation scope

Evidence is maintained under the sibling `legal-tech-hardening/junas` directory.
Measured checks include real Chrome/Chromium extensions with a synthetic vendor
page and actual loopback backend, two-worker API concurrency/persistence/restart,
corruption failures, whole-response privacy, separate-process storage tests and
bounded local size/soak workloads. Office fixture APIs are explicit mocks; native
Outlook and Word are unavailable on this host. Remote providers remain disabled.
The native Swift app compiles and its sidecar startup/error QA paths pass. Its
display/window source currently changes protocol state without capturing frames;
these checks do not establish screen redaction. Packaged sidecar lookup is deferred.

The Docker command now launches the already installed Uvicorn executable. The
previous `uv run` command attempted to fetch build tools at offline startup. The
new command passes an offline container smoke via an explicit command override;
a clean corrected-image rebuild remains blocked by a Docker Hub metadata timeout.
The configured mypy check still fails with the same 127 diagnostics reproduced
on the exact original source. These are unresolved, not passing checks.

Local Tesseract 5.5.3 misreads the tested S-prefix NRIC as a dollar-prefixed token.
That failed case is retained. OCR accuracy is best effort and needs independent
review; a passing clearer fixture does not resolve that blind spot. No readiness
claim covers every layout, jurisdiction, provider, browser or OCR input.
