import { admitText } from "./contract.js";
import TARGETS from "../../config/sensitivity-development-gates.json" with { type: "json" };

export function validateCases(cases) {
  if (!Array.isArray(cases) || !cases.length || cases.length > 1000) throw Error("Expected 1–1000 development cases.");
  const ids = new Set();
  for (const item of cases) {
    admitText(item.text);
    if (typeof item.id !== "string" || ids.has(item.id) || item.split !== "development" || item.reference_kind !== "authored_synthetic_development_expectation") throw Error("Invalid, duplicated or non-development case identity.");
    ids.add(item.id);
    for (const c of ["pii", "mnpi"]) if (!["present", "not_detected", "unknown"].includes(item.expected?.[c])) throw Error("Invalid expected state.");
    for (const s of item.pii_evidence ?? []) if (Array.from(item.text).slice(s.start_char, s.end_char).join("") !== s.matched_text) throw Error("Invalid reference span.");
  }
  return cases;
}

function quantile(values, fraction) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  return sorted.length ? sorted[Math.max(0, Math.ceil(sorted.length * fraction) - 1)] : null;
}
export function scoreResults(cases, rows) {
  validateCases(cases);
  const byId = new Map();
  for (const row of rows) {
    if (byId.has(row.id) || !cases.some(c => c.id === row.id)) throw Error("Duplicate or unknown result identity.");
    byId.set(row.id, row);
  }
  const counts = { pii: {}, mnpi: {} }, byFamily = {};
  let failed = 0, exact = 0, overlap = 0, gold = 0;
  for (const item of cases) {
    const row = byId.get(item.id);
    if (row && row.text !== item.text) throw Error("Result source does not match the reference case.");
    if (!row || row.error) failed++;
    const family = byFamily[item.family] ??= { documents: 0, pii_agreement: 0, mnpi_agreement: 0 };
    family.documents++;
    for (const category of ["pii", "mnpi"]) {
      const state = row?.error ? "error" : row?.states?.[category] ?? "error";
      if (!["present", "not_detected", "unknown", "error"].includes(state)) throw Error("Invalid result state.");
      const key = `${item.expected[category]}→${state}`;
      counts[category][key] = (counts[category][key] ?? 0) + 1;
      if (state === item.expected[category]) family[`${category}_agreement`]++;
    }
    const available = row?.error ? [] : [...(row?.pii_evidence ?? [])];
    for (const p of available) if (!Number.isInteger(p.start_char) || !Number.isInteger(p.end_char) || p.start_char < 0 || p.end_char <= p.start_char || p.end_char > Array.from(item.text).length || Array.from(item.text).slice(p.start_char, p.end_char).join("") !== p.matched_text) throw Error("Invalid prediction evidence.");
    const references = item.pii_evidence ?? [];
    gold += references.length;
    const matching = kind => {
      const owners = new Map();
      function assign(index, seen) {
        const reference = references[index];
        for (let i = 0; i < available.length; i++) {
          const p = available[i];
          const matches = p.label === reference.label && (kind === "exact"
            ? p.start_char === reference.start_char && p.end_char === reference.end_char
            : p.start_char < reference.end_char && reference.start_char < p.end_char);
          if (!matches || seen.has(i)) continue;
          seen.add(i);
          if (!owners.has(i) || assign(owners.get(i), seen)) { owners.set(i, index); return true; }
        }
        return false;
      }
      for (let i = 0; i < references.length; i++) assign(i, new Set());
      return owners.size;
    };
    exact += matching("exact"); overlap += matching("overlap");
  }
  const latency = rows.filter(r => !r.error).map(r => r.inference_ms);
  const measurements = {};
  for (const category of ["pii", "mnpi"]) {
    const count = (reference, prediction) => counts[category][`${reference}→${prediction}`] ?? 0;
    const positive = cases.filter(c => c.expected[category] === "present").length;
    const negative = cases.filter(c => c.expected[category] === "not_detected").length;
    measurements[`${category}_positive_detection`] = count("present", "present") / positive;
    measurements[`${category}_positive_abstention_rate`] = count("present", "unknown") / positive;
    measurements[`${category}_negative_flag_rate`] = count("not_detected", "present") / negative;
    measurements[`${category}_negative_abstention_rate`] = count("not_detected", "unknown") / negative;
  }
  measurements.pii_exact_span_agreement = gold ? exact / gold : null;
  measurements.pii_overlap_span_agreement = gold ? overlap / gold : null;
  const targets = Object.fromEntries(Object.entries(TARGETS).map(([key, limit]) => {
    const value = measurements[key.slice(0, -4)];
    return [key, { target: limit, observed: value, passed: Number.isFinite(value) && (key.endsWith("_min") ? value >= limit : value <= limit) }];
  }));
  return { schema_version: "junas.short_development_eval.v1", reference_kind: "authored_synthetic_development_expectation",
    interpretation: "Development expectation agreement, not independent accuracy; failures remain in denominators.",
    documents: cases.length, received: rows.length, failed, counts, by_family: byFamily, measurements, targets,
    passed: !failed && Object.values(targets).every(t => t.passed),
    pii_spans: { reference: gold, exact_matches: exact, overlapping_matches: overlap },
    inference_ms: { samples: latency.filter(Number.isFinite).length, p50: quantile(latency, .5), p95: quantile(latency, .95) },
  };
}
