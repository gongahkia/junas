# Security Policy

Aki is a local-first privacy tool, so security reports are especially useful when they show a way for screen pixels, OCR text, detections, logs, configs, or release artifacts to leave the user's machine unexpectedly.

## Reporting A Vulnerability

Please email security-sensitive reports to:

```text
angryapplegravy@gmail.com
```

Use a subject such as `Aki security report`. Include:

- The affected version, commit, or branch.
- The platform and install path you used.
- Clear reproduction steps.
- Expected and actual behavior.
- Any local logs needed to understand the issue, with secrets and personal data removed.

Do not paste real tokens, private keys, customer data, screen recordings, or OCR text into the report. Use fake or reserved fixture values where possible. If you need an encrypted path before sharing details, email first and ask for one.

Please avoid opening a public issue for a vulnerability until it has been triaged.

## Scope

Reports are in scope when they affect Aki's privacy, local execution, or release integrity. Examples include:

- Screen pixels, OCR text, detections, config, or logs being uploaded or exposed unexpectedly.
- Local diagnostics such as `aki doctor` collecting or transmitting more than documented.
- The opt-in local LLM detector sending data outside the configured endpoint.
- The local control server accepting unintended remote control or leaking state.
- Redaction pipeline bugs that reliably expose detected sensitive regions after a transform should have been applied.
- Release, signing, update, or package integrity problems that could lead users to install the wrong binary.
- Command injection, path traversal, or unsafe file overwrite behavior in CLI, offline redaction, or packaging flows.

The following are usually out of scope unless they expose a concrete Aki-specific risk:

- Reports that require a maliciously modified Aki binary.
- Social engineering, phishing, or physical access scenarios.
- Generic dependency CVEs without a demonstrated impact on this project.
- Denial-of-service reports that only affect the reporter's own local process.
- Requests for a bug bounty or paid testing program.

## Expected Response

Aki is a small FOSS project, so there is no formal SLA or bounty program. The maintainer will review credible reports on a best-effort basis, prioritize issues that could expose private user data, and coordinate public disclosure once a fix or mitigation is ready.

Supported targets are the current `main` branch and the latest published release. Older commits may receive fixes when the same issue affects a supported target.
