"use client";
import { useMemo } from "react";
import { COMMAND_DEFINITIONS } from "../../lib/commands/definitions";

export interface CommandDef {
  id: string;
  label: string;
  description: string;
  category: string;
}

export const COMMANDS: CommandDef[] = COMMAND_DEFINITIONS.reduce<CommandDef[]>(
  (acc, definition) => {
    if (definition.action.kind !== "command") return acc;
    acc.push({
      id: definition.action.commandId,
      label: definition.label,
      description: definition.description,
      category: `${definition.category[0].toUpperCase()}${definition.category.slice(1)}`,
    });
    return acc;
  },
  [],
);

const normalizeQuery = (value: string) => value.trim().toLowerCase();

export const filterCommands = (query: string, commands: CommandDef[] = COMMANDS) => {
  const normalized = normalizeQuery(query);
  if (!normalized) return commands;

  return commands.filter((command) => {
    const haystacks = [command.id, command.label, command.description, command.category];
    return haystacks.some((field) => field.toLowerCase().includes(normalized));
  });
};

interface Props {
  query: string;
  onSelect: (commandId: string) => void;
  isOpen: boolean;
  selectedIndex: number;
}

export default function CommandSuggestions({ query, onSelect, isOpen, selectedIndex }: Props) {
  const matches = useMemo(() => {
    return filterCommands(query);
  }, [query]);

  if (!isOpen) return null;

  const selectedMatchIndex = matches.length === 0 ? -1 : Math.min(selectedIndex, matches.length - 1);

  return (
    <div style={{ position: "absolute", bottom: "100%", left: 0, right: 0, marginBottom: "0.25rem", background: "#fff", border: "1px solid #cbd5e1", borderRadius: "0.5rem", boxShadow: "0 4px 12px rgba(0,0,0,0.1)", maxHeight: "240px", overflowY: "auto", zIndex: 50 }}>
      {matches.length === 0 ? (
        <div style={{ padding: "0.75rem 0.6rem", color: "#64748b", fontSize: "0.8rem" }}>
          No matching commands
        </div>
      ) : null}
      {matches.map((cmd, i) => (
        <div
          key={cmd.id}
          onClick={() => onSelect(cmd.id)}
          style={{
            padding: "0.4rem 0.6rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.5rem",
            background: i === selectedMatchIndex ? "#dbeafe" : "transparent",
            borderBottom: i < matches.length - 1 ? "1px solid #f1f5f9" : "none",
          }}
        >
          <span style={{ fontFamily: "monospace", fontSize: "0.8rem", fontWeight: 600, color: "#1d4ed8" }}>/{cmd.id}</span>
          <span style={{ fontSize: "0.8rem", color: "#475569" }}>{cmd.description}</span>
          <span style={{ marginLeft: "auto", fontSize: "0.65rem", color: "#94a3b8", fontWeight: 600 }}>{cmd.category}</span>
        </div>
      ))}
    </div>
  );
}
