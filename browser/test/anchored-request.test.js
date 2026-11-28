import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { copyFile, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { anchoredRequest, sourceQuotes } from "../research/anchored-request.js";
import { decodeProposal } from "../src/contract.js";

test("source-anchored grammar rejects fabricated, repeated and contradictory evidence", async () => {
  // this pinned dependency ships UMD despite its ESM package flag; use its CommonJS entry wrapper.
  const require = createRequire(import.meta.url), temporary = await mkdtemp(join(tmpdir(), "junas-grammar-"));
  try {
    const entry = join(temporary, "xgrammar.cjs");
    await copyFile(require.resolve("@mlc-ai/web-xgrammar"), entry);
    const { Grammar, Testings } = require(entry);
    const text = "🙂 Personal email: mira@example.test. Repeat repeat. Repeat repeat.";
    assert.ok(!sourceQuotes(text).includes("Repeat repeat"));
    const request = anchoredRequest(text);
    const grammar = await Grammar.fromJSONSchema(request.response_format.schema);
    try {
      const accepts = output => Testings.isGrammarAcceptString(grammar, JSON.stringify(output));
      const output = { pii_state: "present", pii: [{ label: "EMAIL", quote: "mira@example.test", confidence: .9 }], mnpi_state: "not_detected", mnpi: [], complete: true };
      assert.equal(await accepts(output), true);
      assert.equal(await accepts({ ...output, pii: [] }), false);
      assert.equal(await accepts({ ...output, pii_state: "not_detected" }), false);
      assert.equal(await accepts({ ...output, pii: [{ ...output.pii[0], quote: "fabricated@example.test" }] }), false);
      assert.equal(await accepts({ ...output, pii: [{ ...output.pii[0], quote: "Repeat repeat" }] }), false);
      // numeric bounds are checked by Junas; this grammar runtime does not enforce them.
      const invalidEstimate = { ...output, pii: [{ ...output.pii[0], confidence: 1.5 }] };
      assert.throws(() => decodeProposal(text, { finish_reason: "stop", message: { content: JSON.stringify(invalidEstimate) } }, true), /confidence/);
      assert.equal(await accepts({ ...output, pii_state: "unknown", pii: [] }), true);
    } finally { grammar.dispose(); }
    assert.ok(!anchoredRequest(text, "Llama-3.2-3B-Instruct-q4f16_1-MLC").extra_body);
  } finally { await rm(temporary, { recursive: true, force: true }); }
});
