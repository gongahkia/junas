import type { LucideIcon } from "lucide-react";
import {
  BookOpenText,
  ChartColumnIncreasing,
  Copy,
  ClipboardList,
  Download,
  FileSearch,
  FileText,
  Fingerprint,
  GitCompareArrows,
  HelpCircle,
  History,
  Home,
  Keyboard,
  LayoutTemplate,
  MessageSquarePlus,
  PanelLeft,
  PenLine,
  Play,
  Search,
  Settings,
  ShieldCheck,
  Share2,
  LayoutGrid,
} from "lucide-react";
import type { KeyboardActionId } from "../keyboard";

export type CommandCategory = "shortcuts" | "research" | "analysis" | "drafting" | "tools" | "system";

export type CommandAction =
  | { kind: "command"; commandId: string }
  | { kind: "navigate"; href: string }
  | { kind: "new-chat" }
  | { kind: "click-by-text"; text: string }
  | { kind: "share" }
  | { kind: "shortcut"; shortcutId: KeyboardActionId };

export interface CommandDefinition {
  id: string;
  label: string;
  description: string;
  category: CommandCategory;
  icon: LucideIcon;
  action: CommandAction;
}

export interface CommandSection {
  category: CommandCategory;
  label: string;
  commands: CommandDefinition[];
}

const CATEGORY_ORDER: readonly CommandCategory[] = ["shortcuts", "research", "analysis", "drafting", "tools", "system"];

const CATEGORY_LABELS: Record<CommandCategory, string> = {
  shortcuts: "Shortcuts",
  research: "Research",
  analysis: "Analysis",
  drafting: "Drafting",
  tools: "Tools",
  system: "System",
};

export const COMMAND_DEFINITIONS: readonly CommandDefinition[] = [
  {
    id: "open-command-palette",
    label: "Open Command Palette",
    description: "Search commands and app pages",
    category: "shortcuts",
    icon: Keyboard,
    action: { kind: "shortcut", shortcutId: "open-command-palette" },
  },
  {
    id: "open-keyboard-help",
    label: "Open Keyboard Help",
    description: "Show every keyboard shortcut",
    category: "shortcuts",
    icon: HelpCircle,
    action: { kind: "shortcut", shortcutId: "open-keyboard-help" },
  },
  {
    id: "focus-chat-input",
    label: "Focus Chat Input",
    description: "Jump to the chat composer",
    category: "shortcuts",
    icon: MessageSquarePlus,
    action: { kind: "shortcut", shortcutId: "focus-chat-input" },
  },
  {
    id: "toggle-session-sidebar",
    label: "Toggle Session Sidebar",
    description: "Show or hide the sidebar",
    category: "shortcuts",
    icon: PanelLeft,
    action: { kind: "shortcut", shortcutId: "toggle-session-sidebar" },
  },
  {
    id: "export-current-view-docx",
    label: "Export Current View to DOCX",
    description: "Download the active exportable view",
    category: "shortcuts",
    icon: Download,
    action: { kind: "shortcut", shortcutId: "export-current-view-docx" },
  },
  {
    id: "copy-last-assistant-response",
    label: "Copy Last Assistant Response",
    description: "Copy the newest Junas response",
    category: "shortcuts",
    icon: Copy,
    action: { kind: "shortcut", shortcutId: "copy-last-assistant-response" },
  },
  {
    id: "jump-to-page-palette",
    label: "Jump to Page",
    description: "Open page-only palette",
    category: "shortcuts",
    icon: Search,
    action: { kind: "shortcut", shortcutId: "jump-to-page-palette" },
  },
  {
    id: "rerun-last-benchmark",
    label: "Re-run Last Benchmark",
    description: "Repeat the latest leaderboard run",
    category: "shortcuts",
    icon: Play,
    action: { kind: "shortcut", shortcutId: "rerun-last-benchmark" },
  },
  {
    id: "search-case-law",
    label: "Search Case Law",
    description: "Search legal databases for case law",
    category: "research",
    icon: Search,
    action: { kind: "command", commandId: "search-case-law" },
  },
  {
    id: "research-statute",
    label: "Research Statute",
    description: "Look up statutory provisions",
    category: "research",
    icon: BookOpenText,
    action: { kind: "command", commandId: "research-statute" },
  },
  {
    id: "check-compliance",
    label: "Check Compliance",
    description: "Verify document against compliance rules",
    category: "analysis",
    icon: ShieldCheck,
    action: { kind: "command", commandId: "check-compliance" },
  },
  {
    id: "analyze-contract",
    label: "Analyze Contract",
    description: "Extract key terms and risks from a contract",
    category: "analysis",
    icon: FileSearch,
    action: { kind: "command", commandId: "analyze-contract" },
  },
  {
    id: "summarize-document",
    label: "Summarize Document",
    description: "AI-powered document summary",
    category: "analysis",
    icon: FileText,
    action: { kind: "command", commandId: "summarize-document" },
  },
  {
    id: "extract-entities",
    label: "Extract Entities",
    description: "Identify persons, organizations, dates, citations",
    category: "analysis",
    icon: Fingerprint,
    action: { kind: "command", commandId: "extract-entities" },
  },
  {
    id: "analyze-document",
    label: "Analyze Document",
    description: "Statistics, readability, and structure analysis",
    category: "analysis",
    icon: ChartColumnIncreasing,
    action: { kind: "command", commandId: "analyze-document" },
  },
  {
    id: "due-diligence-review",
    label: "Due Diligence Review",
    description: "Legal due diligence checklist",
    category: "analysis",
    icon: ClipboardList,
    action: { kind: "command", commandId: "due-diligence-review" },
  },
  {
    id: "draft-clause",
    label: "Draft Clause",
    description: "Generate a legal clause for a specific purpose",
    category: "drafting",
    icon: PenLine,
    action: { kind: "command", commandId: "draft-clause" },
  },
  {
    id: "use-template",
    label: "Use Template",
    description: "Open the template library",
    category: "drafting",
    icon: LayoutTemplate,
    action: { kind: "command", commandId: "use-template" },
  },
  {
    id: "redline",
    label: "Redline Compare",
    description: "Compare two versions of a document",
    category: "tools",
    icon: GitCompareArrows,
    action: { kind: "command", commandId: "redline" },
  },
  {
    id: "new-chat",
    label: "New Chat",
    description: "Start a fresh conversation",
    category: "system",
    icon: MessageSquarePlus,
    action: { kind: "shortcut", shortcutId: "new-chat" },
  },
  {
    id: "home",
    label: "Home",
    description: "Go to the dashboard",
    category: "system",
    icon: Home,
    action: { kind: "navigate", href: "/" },
  },
  {
    id: "research",
    label: "Research",
    description: "Open the research workspace",
    category: "system",
    icon: Search,
    action: { kind: "navigate", href: "/research" },
  },
  {
    id: "glossary",
    label: "Glossary",
    description: "Open the legal glossary",
    category: "system",
    icon: BookOpenText,
    action: { kind: "navigate", href: "/glossary" },
  },
  {
    id: "statutes",
    label: "Statutes",
    description: "Open the statutes browser",
    category: "system",
    icon: LayoutGrid,
    action: { kind: "navigate", href: "/statutes" },
  },
  {
    id: "contracts",
    label: "Contracts",
    description: "Open the contract analysis workspace",
    category: "system",
    icon: FileSearch,
    action: { kind: "navigate", href: "/contracts" },
  },
  {
    id: "history",
    label: "History",
    description: "Open saved conversations",
    category: "system",
    icon: History,
    action: { kind: "navigate", href: "/chat" },
  },
  {
    id: "export",
    label: "Export Chat",
    description: "Download the current chat as Markdown",
    category: "system",
    icon: Download,
    action: { kind: "click-by-text", text: "Export .md" },
  },
  {
    id: "share",
    label: "Share Chat",
    description: "Copy a shareable link to the clipboard",
    category: "system",
    icon: Share2,
    action: { kind: "share" },
  },
  {
    id: "settings",
    label: "Settings",
    description: "Open API keys and provider preferences",
    category: "system",
    icon: Settings,
    action: { kind: "navigate", href: "/settings" },
  },
];

export function getCommandSections(definitions: readonly CommandDefinition[] = COMMAND_DEFINITIONS): CommandSection[] {
  return CATEGORY_ORDER.map((category) => ({
    category,
    label: CATEGORY_LABELS[category],
    commands: definitions.filter((definition) => definition.category === category),
  })).filter((section) => section.commands.length > 0);
}

export function matchesCommandQuery(definition: CommandDefinition, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;

  return [
    definition.id,
    definition.label,
    definition.description,
    CATEGORY_LABELS[definition.category],
  ].some((value) => value.toLowerCase().includes(q));
}
