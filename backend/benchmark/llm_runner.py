"""LLM-call task runner.

Converts the harness from "every shipped task scores 1.0 via oracle" into
producing real numbers by wrapping an ``api.services.llm_client.LLMClient``
into a ``benchmark.registry.TASKS`` runner.

Design rules:

1. **One prompt template per task.** Tasks register a prompt builder
   ``(case) -> messages`` so the runner stays generic.
2. **Disclosed prompts + model + temperature.** Every receipt records
   the prompt template SHA, the provider/model, and the temperature so
   results are reproducible. Coverage matrix §4.4.
3. **No silent retries on bad JSON.** If a model returns malformed
   output, the runner records the raw output and an empty prediction
   string; the evaluator scores 0 on that case. This is honest and
   makes JSON-parsing failures show up as a quality metric instead of
   getting hidden.
4. **Bounded concurrency.** The runner respects the harness's existing
   ``max_concurrency`` semaphore — we add no separate one.
5. **Mock client is first-class.** Tests use a ``MockLLMClient`` that
   returns deterministic canned outputs; the runner code path is
   identical between mock and real providers.

See ``docs/sglb_specs/SGLB-{04,11,08,12,15}.md`` for per-task output
contracts; each spec is the canonical reference for the expected JSON
shape.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from benchmark.schema import Case

logger = logging.getLogger(__name__)

PromptBuilder = Callable[[Case], list[dict[str, str]]]


class LLMLike(Protocol):
    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        ...


@dataclass(frozen=True)
class LLMRunnerConfig:
    """Configuration for an LLM-backed task runner.

    Attributes:
        prompt_builder: function that maps a ``Case`` to OpenAI-style
            messages. Must be deterministic for a given case.
        prompt_version: short string identifying the prompt template
            version. Recorded in receipts.
        max_tokens: hard cap on output tokens. The harness's strict
            evaluators (e.g. ``citation_format_valid``) typically need
            very few tokens; default 512 is a safe small default.
        provider_label: display string used in audit/metadata, e.g.
            ``"anthropic:claude-sonnet-4-6"``. The runner never reads
            this; it's only stored on receipts.
    """

    prompt_builder: PromptBuilder
    prompt_version: str
    max_tokens: int = 512
    provider_label: str = "unknown"


def prompt_sha(builder: PromptBuilder, sample: Case) -> str:
    """Hash a builder against a sample case so receipt SHAs are stable
    across runs of the same template against the same input. Used by
    audit and reproducibility receipts."""
    rendered = builder(sample)
    payload = "\n---\n".join(
        f"{m.get('role', '')}::{m.get('content', '')}" for m in rendered
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_llm_task(*, client: LLMLike, config: LLMRunnerConfig) -> Callable[[Case], Awaitable[str]]:
    """Build an async task runner that calls ``client.generate`` per case.

    The returned runner can be passed to ``benchmark.registry.register_task``
    or used directly via ``benchmark.runner.run``. The runner never raises
    on LLM call failure — failures are logged and an empty string is
    returned, which lets the evaluator record a score of 0 against that
    case rather than aborting the whole run.
    """

    async def _runner(case: Case) -> str:
        messages = config.prompt_builder(case)
        try:
            output = await client.generate(messages, max_tokens=config.max_tokens)
        except Exception as exc:  # noqa: BLE001 — surface as data, not crash
            logger.warning(
                "llm_runner: provider call failed case=%s provider=%s err=%s",
                case.name,
                config.provider_label,
                exc,
            )
            return ""
        return output if isinstance(output, str) else str(output)

    return _runner


# === Mock client (used by tests; never imports a real provider) ===


@dataclass
class MockLLMClient:
    """Deterministic stand-in for any real provider.

    Two configuration knobs:

    - ``canned``: a dict mapping the user-message content (last user turn)
      to the response. Lookup is by full-string match.
    - ``default_response``: returned when no canned key matches. Useful
      for "the model gets every case right" oracle-style tests.

    ``calls`` is incremented on every ``generate`` so tests can assert
    that the runner actually used the client.
    """

    canned: dict[str, str] | None = None
    default_response: str = ""
    calls: int = 0

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        del max_tokens
        self.calls += 1
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        if self.canned and last_user in self.canned:
            return self.canned[last_user]
        return self.default_response


# === Prompt builders for shipped tasks ===
#
# Each task has a builder + a version string. When the prompt changes
# materially, bump the version so old receipts remain distinguishable.


def _user_message(content: str) -> dict[str, str]:
    return {"role": "user", "content": content}


def _system_message(content: str) -> dict[str, str]:
    return {"role": "system", "content": content}


SGLB_01_PROMPT_VERSION = "sglb-01-v1"


def sglb_01_prompt_builder(case: Case) -> list[dict[str, str]]:
    """SGLB-01: predict obligation labels + penalty band from a redacted
    PDPC fact summary. Output contract: a JSON object
    ``{"obligations": [...], "penalty_band": "none|low|mid|high"}``."""
    fact_summary = str(case.inputs.get("fact_summary", "")).strip()
    return [
        _system_message(
            "You are a Singapore PDPA compliance analyst. Given a redacted "
            "fact summary from a PDPC enforcement decision, predict which "
            "PDPA obligations were breached and the penalty band imposed. "
            "Obligations must be drawn from this closed taxonomy: consent, "
            "notification, purpose_limitation, protection, retention_limitation, "
            "data_portability, dpo, dnc, data_intermediary, transfer_limitation, "
            "accountability, openness, accuracy, access_correction. "
            "Penalty band must be one of: none, low, mid, high (log10-bucketed "
            "SGD: low<5000, mid<50000, high>=50000, none if no financial "
            "penalty). Reply with a single JSON object: "
            "{\"obligations\": [<labels>], \"penalty_band\": \"<band>\"}. "
            "Do not include any other text."
        ),
        _user_message(fact_summary),
    ]


SGLB_04_PROMPT_VERSION = "sglb-04-v1"


def sglb_04_prompt_builder(case: Case) -> list[dict[str, str]]:
    """SGLB-04: classify a citation as valid / invalid per the SAL Style
    Guide. Output contract: a single-element JSON list."""
    citation = str(case.inputs.get("citation", "")).strip()
    return [
        _system_message(
            "You are an expert in the Singapore Academy of Law (SAL) citation "
            "style. Given a candidate legal citation, decide whether it "
            "conforms to the SAL Style Guide grammar (SLR Style Guide 2021 + "
            "SAL Quick Reference 2007). Reply with a single-element JSON "
            "array: either [\"valid\"] or [\"invalid\"]. Do not include any "
            "other text."
        ),
        _user_message(citation),
    ]


SGLB_11_PROMPT_VERSION = "sglb-11-v1"


def sglb_11_prompt_builder(case: Case) -> list[dict[str, str]]:
    """SGLB-11: identify fabricated SG citations in a passage. Output
    contract: a JSON array of citation strings (possibly empty)."""
    passage = str(case.inputs.get("passage", "")).strip()
    return [
        _system_message(
            "You are an expert legal-citation checker for Singapore case "
            "law. Given a passage containing several citations, identify "
            "which citations are fabricated (do not refer to a real "
            "Singapore case). Reply with a JSON array of citation strings "
            "that you believe are fabricated. If you believe every "
            "citation is real, reply with an empty JSON array []."
        ),
        _user_message(passage),
    ]


SGLB_08_PROMPT_VERSION = "sglb-08-v1"


def sglb_08_prompt_builder(case: Case) -> list[dict[str, str]]:
    """SGLB-08: classify the negotiation tone of a contract clause.
    Output contract: a single-element JSON array from the tone
    taxonomy."""
    clause_text = str(case.inputs.get("clause_text", "")).strip()
    clause_type = str(case.inputs.get("clause_type", "")).strip()
    return [
        _system_message(
            "You are an experienced Singapore contracts lawyer. Given a "
            "contract clause and its clause type, classify the negotiation "
            "tone of the clause as one of: standard, aggressive, balanced, "
            "or protective. Reply with a single-element JSON array, e.g. "
            "[\"standard\"]. Do not include any other text."
        ),
        _user_message(f"Clause type: {clause_type}\n\nClause text:\n{clause_text}"),
    ]


SGLB_12_PROMPT_VERSION = "sglb-12-v1"


def sglb_12_prompt_builder(case: Case) -> list[dict[str, str]]:
    """SGLB-12: identify which compound legal issues a scenario
    triggers. Output contract: a JSON array of issue label strings
    from the taxonomy."""
    scenario = str(case.inputs.get("scenario", "")).strip()
    return [
        _system_message(
            "You are a Singapore legal-issue spotter for compliance review. "
            "Given a compound fact pattern, identify every legal issue "
            "triggered across PDPA, the Employment Act, and the Rules of "
            "Court 2021. Reply with a JSON array of issue label strings, "
            "e.g. [\"pdpa.protection_obligation\", "
            "\"ea.notice_period_breach\"]. Use only labels from the SGLB-12 "
            "taxonomy. Reply with an empty JSON array if no issues are "
            "triggered."
        ),
        _user_message(scenario),
    ]


# === Convenience: a registry of prompt builders by task name ===

PROMPT_BUILDERS: dict[str, tuple[PromptBuilder, str]] = {
    "sglb_01": (sglb_01_prompt_builder, SGLB_01_PROMPT_VERSION),
    "sglb_04": (sglb_04_prompt_builder, SGLB_04_PROMPT_VERSION),
    "sglb_11": (sglb_11_prompt_builder, SGLB_11_PROMPT_VERSION),
    "sglb_08": (sglb_08_prompt_builder, SGLB_08_PROMPT_VERSION),
    "sglb_12": (sglb_12_prompt_builder, SGLB_12_PROMPT_VERSION),
}


def llm_task_for(
    *,
    workflow: str,
    client: LLMLike,
    provider_label: str = "unknown",
    max_tokens: int | None = None,
) -> Callable[[Case], Awaitable[str]]:
    """Convenience: build an LLM-backed runner for one of the registered
    prompt builders by workflow name."""
    if workflow not in PROMPT_BUILDERS:
        raise ValueError(
            f"no prompt builder registered for {workflow!r}; "
            f"add one to PROMPT_BUILDERS in benchmark.llm_runner"
        )
    builder, version = PROMPT_BUILDERS[workflow]
    config = LLMRunnerConfig(
        prompt_builder=builder,
        prompt_version=version,
        max_tokens=max_tokens or 512,
        provider_label=provider_label,
    )
    return build_llm_task(client=client, config=config)
