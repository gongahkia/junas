# Junas MCP Example Prompts

Use these prompts from an MCP-capable client after configuring
`junas-mcp`.

## Individual tools

1. Call `health` and show the repo version and git SHA.

2. Use `verify_citation` to validate `[2023] SGCA 5`.

3. Use `verify_citation` to explain why `definitely not a citation` is invalid.

4. Use `lookup_statute` for `s 13 PDPA`.

5. Use `lookup_statute` for `s 18 Employment Act`.

6. Use `retrieve_cases` with query `breach of confidence employment non-compete` and `k=5`.

7. Use `check_compliance` for this text under `pdpa`: `The organisation may collect personal data for onboarding after obtaining consent.`

8. Use `check_compliance` for this text under `employment_act`: `Either party may terminate employment by giving one month notice. CPF contributions apply.`

9. Use `check_compliance` for this text under `roc_2021`: `The claimant will commence proceedings by originating claim under the Rules of Court 2021.`

10. Use `run_benchmark` for task `sglb_04` and model `ollama`, then summarize the score.

## Chained workflows

1. Validate these citations with `verify_citation`, then look up any statute citation with `lookup_statute`: `[2009] 2 SLR(R) 332`; `s 13 PDPA`.

2. Run `check_compliance` on a short employment clause under `employment_act`, then retrieve cases for any flagged restraint-of-trade issue.

3. Run `run_benchmark` for `sglb_16` with model `ollama`, then explain which evaluator was used and whether external model calls were made.
