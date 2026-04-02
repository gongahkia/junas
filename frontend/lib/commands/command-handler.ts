/**
 * Chat command handler — wires /commands to backend API endpoints.
 */
import { checkCompliance, searchCases, extractEntities, classifyContract, searchStatutes, searchSSO, searchCommonLII } from "../api-client";

interface CommandResult { isCommand: boolean; response?: string; }

export async function handleCommand(input: string): Promise<CommandResult> {
  const match = input.match(/^\/(\S+)\s*([\s\S]*)$/);
  if (!match) return { isCommand: false };
  const [, cmd, text] = match;
  const trimmed = text.trim();
  if (!trimmed && !["use-template"].includes(cmd)) return { isCommand: true, response: `Command /${cmd} requires text input.` };

  try {
    switch (cmd) {
      case "check-compliance": {
        const data = await checkCompliance(trimmed);
        return { isCommand: true, response: formatCompliance(data) };
      }
      case "search-case-law": {
        const data = await searchCases(trimmed, 5);
        return { isCommand: true, response: formatCaseResults(data) };
      }
      case "extract-entities": {
        const data = await extractEntities(trimmed);
        return { isCommand: true, response: formatEntities(data) };
      }
      case "analyze-contract": {
        const data = await classifyContract(trimmed);
        return { isCommand: true, response: formatContractAnalysis(data) };
      }
      case "search-statute":
      case "research-statute": {
        const data = await searchStatutes(trimmed);
        return { isCommand: true, response: formatStatuteResults(data) };
      }
      default:
        return { isCommand: false };
    }
  } catch (err: any) {
    return { isCommand: true, response: `**Error:** ${err.message || "Command failed"}` };
  }
}

function formatCompliance(data: any): string {
  if (data.error) return `**Compliance Error:** ${data.error}`;
  const s = data.summary || {};
  let md = `## Compliance Check Results\n\n**Passed:** ${s.passed || 0} | **Warnings:** ${s.warnings || 0} | **Failed:** ${s.failed || 0}\n\n`;
  for (const r of data.results || []) {
    const icon = r.status === "pass" ? "✅" : r.status === "warning" ? "⚠️" : "❌";
    md += `${icon} **${r.rule_name}** (${r.severity}) — ${r.details}\n\n`;
  }
  return md;
}

function formatCaseResults(data: any): string {
  if (data.error) return `**Search Error:** ${data.error}`;
  const results = data.results || data.cases || [];
  if (results.length === 0) return "No case results found.";
  let md = `## Case Law Results\n\n`;
  for (const r of results.slice(0, 10)) {
    const title = r.title || r.case_name || r.source_id || "Unknown";
    const score = r.score ? ` (score: ${r.score.toFixed(3)})` : "";
    md += `- **${title}**${score}\n`;
    if (r.text || r.snippet) md += `  > ${(r.text || r.snippet).slice(0, 200)}...\n\n`;
  }
  return md;
}

function formatEntities(data: any): string {
  if (data.error) return `**NER Error:** ${data.error}`;
  const entities = data.entities || [];
  if (entities.length === 0) return "No entities found.";
  let md = `## Extracted Entities (${entities.length})\n\n`;
  const grouped: Record<string, string[]> = {};
  for (const e of entities) {
    const label = e.label || e.type || "UNKNOWN";
    if (!grouped[label]) grouped[label] = [];
    grouped[label].push(e.text || e.word || "");
  }
  for (const [label, texts] of Object.entries(grouped)) {
    md += `**${label}:** ${[...new Set(texts)].join(", ")}\n\n`;
  }
  return md;
}

function formatContractAnalysis(data: any): string {
  if (data.error) return `**Analysis Error:** ${data.error}`;
  const types = data.clause_types || data.predictions || [];
  if (types.length === 0) return "No clause types detected.";
  let md = `## Contract Clause Analysis\n\n`;
  for (const t of types) {
    const label = t.label || t.type || "Unknown";
    const score = t.score ? ` — ${(t.score * 100).toFixed(1)}%` : "";
    md += `- **${label}**${score}\n`;
  }
  return md;
}

function formatStatuteResults(data: any): string {
  if (data.error) return `**Search Error:** ${data.error}`;
  const results = data.results || [];
  if (results.length === 0) return "No statute results found.";
  let md = `## Statute Results\n\n`;
  for (const r of results.slice(0, 10)) {
    md += `- **${r.number || r.title || "Section"}** — ${(r.name || r.text || "").slice(0, 200)}\n`;
  }
  return md;
}
