import { build } from "esbuild";
import { readFile, writeFile, mkdir, cp } from "node:fs/promises";
import { createHash } from "node:crypto";
import { parseArgs } from "node:util";
import { resolve } from "node:path";
import { ANCHORED_REQUEST_VERSION } from "./anchored-request.js";

const { values } = parseArgs({ options: { output: { type: "string" }, validation: { type: "string" } } });
if (!values.output || !values.validation) throw Error("Use --output NEW_DIRECTORY --validation FROZEN_JSON.");
const output = resolve(values.output), validation = await readFile(values.validation);
const validationSha = createHash("sha256").update(validation).digest("hex");
if (validationSha !== "77e98a49189cbe17051cbd8115a1505cb4eea113e3495e45e827a66ef9158233") throw Error("Expected the original frozen authored validation artifact.");
const files = ["research/anchored-request.js", "research/anchored-worker.js", "research/anchored-run.js", "research/run-validation.js", "research/redactor-metrics.js", "research/shadow-policy.js", "research/local-pii-candidate.js", "research/build-anchored.mjs", "research/anchored-eval.html", "src/contract.js", "src/model.js", "src/evaluation.js", "src/auto-redaction.js", "eval/cases.js", "eval/screening-ids.json", "package-lock.json", "../config/sensitivity-development-gates.json"];
const hashes = {};
for (const file of files.sort()) hashes[file] = createHash("sha256").update(await readFile(file)).digest("hex");
const artifactSha = createHash("sha256").update(JSON.stringify({ hashes, validationSha })).digest("hex");
await mkdir(output); // refuse to overwrite an active or frozen evaluation build.
await build({ entryPoints: { "anchored-eval": "research/anchored-run.js", "anchored-worker": "research/anchored-worker.js" }, outdir: output, bundle: true, format: "esm", target: "chrome120", minify: true,
  define: { __JUNAS_BUILD_ID__: JSON.stringify(artifactSha), __JUNAS_VALIDATION_SHA256__: JSON.stringify(validationSha) } });
await cp("research/anchored-eval.html", `${output}/anchored-eval.html`);
await cp("public/style.css", `${output}/style.css`);
await writeFile(`${output}/frozen-validation.json`, validation, { flag: "wx" });
await writeFile(`${output}/research-manifest.json`, JSON.stringify({ artifact_sha256: artifactSha, validation_sha256: validationSha, request_version: ANCHORED_REQUEST_VERSION, source_sha256: hashes, paid_api_calls: 0 }, null, 2) + "\n", { flag: "wx" });
console.log(JSON.stringify({ output, artifact_sha256: artifactSha, request_version: ANCHORED_REQUEST_VERSION }));
