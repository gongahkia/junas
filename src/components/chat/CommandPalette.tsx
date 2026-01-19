'use client';

import { useState, useEffect, useRef } from 'react';
import {
  Search,
  FileText,
  Users,
  BarChart,
  FileSearch,
  Scale,
  BookOpen,
  Briefcase,
  FileSignature,
  Cpu,
  Sparkles,
  Tags
} from 'lucide-react';

export interface CommandItem {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  category: 'research' | 'analysis' | 'drafting' | 'tools';
  isLocal: boolean; // true = processed locally without AI
  action: () => void;
}

interface CommandPaletteProps {
  onCommandSelect: (commandId: string, commandText: string) => void;
  onClose: () => void;
  inputValue: string;
  cursorPosition: number;
}

export function CommandPalette({ 
  onCommandSelect, 
  onClose, 
  inputValue,
  cursorPosition 
}: CommandPaletteProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'search-case-law',
      label: 'search-case-law',
      description: 'Search Singapore legal database for relevant cases',
      icon: <Search className="h-4 w-4" />,
      category: 'research',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'research-statute',
      label: 'research-statute',
      description: 'Look up statutory provisions and interpretations',
      icon: <BookOpen className="h-4 w-4" />,
      category: 'research',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'extract-entities',
      label: 'extract-entities',
      description: 'Extract people, organizations, dates, citations (no AI)',
      icon: <Users className="h-4 w-4" />,
      category: 'analysis',
      isLocal: true,
      action: () => {},
    },
    {
      id: 'analyze-document',
      label: 'analyze-document',
      description: 'Get statistics, readability, keywords, structure (no AI)',
      icon: <BarChart className="h-4 w-4" />,
      category: 'analysis',
      isLocal: true,
      action: () => {},
    },
    {
      id: 'summarize-local',
      label: 'summarize-local',
      description: 'Summarize text using local ONNX model (requires download)',
      icon: <Cpu className="h-4 w-4" />,
      category: 'analysis',
      isLocal: true,
      action: () => {},
    },
    {
      id: 'ner-advanced',
      label: 'ner-advanced',
      description: 'Advanced NER using BERT model (requires download)',
      icon: <Tags className="h-4 w-4" />,
      category: 'analysis',
      isLocal: true,
      action: () => {},
    },
    {
      id: 'classify-text',
      label: 'classify-text',
      description: 'Classify text sentiment using local model (requires download)',
      icon: <Sparkles className="h-4 w-4" />,
      category: 'analysis',
      isLocal: true,
      action: () => {},
    },
    {
      id: 'analyze-contract',
      label: 'analyze-contract',
      description: 'Extract key terms, obligations, and risks from contract',
      icon: <FileSearch className="h-4 w-4" />,
      category: 'analysis',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'summarize-document',
      label: 'summarize-document',
      description: 'Generate concise summary of legal document',
      icon: <FileText className="h-4 w-4" />,
      category: 'analysis',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'due-diligence-review',
      label: 'due-diligence-review',
      description: 'Conduct legal due diligence checklist',
      icon: <Briefcase className="h-4 w-4" />,
      category: 'analysis',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'draft-clause',
      label: 'draft-clause',
      description: 'Generate legal clause based on requirements',
      icon: <FileSignature className="h-4 w-4" />,
      category: 'drafting',
      isLocal: false,
      action: () => {},
    },
    {
      id: 'check-compliance',
      label: 'check-compliance',
      description: 'Verify regulatory compliance for Singapore law',
      icon: <Scale className="h-4 w-4" />,
      category: 'tools',
      isLocal: false,
      action: () => {},
    },
  ];

  // Filter commands based on search query
  const filteredCommands = commands.filter(cmd => 
    cmd.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
    cmd.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group commands by category
  const groupedCommands = filteredCommands.reduce((acc, cmd) => {
    if (!acc[cmd.category]) {
      acc[cmd.category] = [];
    }
    acc[cmd.category].push(cmd);
    return acc;
  }, {} as Record<string, CommandItem[]>);

  // Create a flat array in display order (matching how they appear in the UI)
  const categoryOrder = ['research', 'analysis', 'drafting', 'tools'];
  const displayOrderCommands = categoryOrder.flatMap(
    category => groupedCommands[category] || []
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev =>
          prev < displayOrderCommands.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (displayOrderCommands[selectedIndex]) {
          handleCommandSelect(displayOrderCommands[selectedIndex]);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedIndex, displayOrderCommands, onClose]);

  // Update search query from input
  useEffect(() => {
    const afterSlash = inputValue.slice(cursorPosition).split(' ')[0];
    const beforeSlash = inputValue.slice(0, cursorPosition);
    const lastSlashIndex = beforeSlash.lastIndexOf('/');
    
    if (lastSlashIndex !== -1) {
      const query = beforeSlash.slice(lastSlashIndex + 1) + afterSlash;
      setSearchQuery(query);
    }
  }, [inputValue, cursorPosition]);

  const handleCommandSelect = (command: CommandItem) => {
    const commandText = `/${command.id}`;
    onCommandSelect(command.id, commandText);
  };

  const categoryLabels = {
    research: 'Research',
    analysis: 'Analysis',
    drafting: 'Drafting',
    tools: 'Tools',
  };

  let commandIndex = 0;

  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 right-0 mb-2 bg-background border border-muted-foreground/30 shadow-lg max-h-[40vh] md:max-h-[50vh] overflow-y-auto z-50 font-mono"
    >
      <div className="sticky top-0 bg-background border-b px-3 py-2 flex items-center gap-2 text-xs">
        <span className="font-medium">[ Commands ]</span>
        {searchQuery && (
          <span className="text-muted-foreground ml-auto">
            {filteredCommands.length} results
          </span>
        )}
      </div>

      {filteredCommands.length === 0 ? (
        <div className="px-3 py-8 text-center text-sm text-muted-foreground">
          No commands found
        </div>
      ) : (
        <div className="py-2">
          {categoryOrder.map((category) => {
            const cmds = groupedCommands[category];
            if (!cmds || cmds.length === 0) return null;
            return (
            <div key={category}>
              <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {categoryLabels[category as keyof typeof categoryLabels]}
              </div>
              {cmds.map((command) => {
                const currentIndex = commandIndex++;
                const isSelected = currentIndex === selectedIndex;
                
                return (
                  <button
                    key={command.id}
                    onClick={() => handleCommandSelect(command)}
                    className={`
                      w-full px-3 py-2 flex items-start gap-3 text-left transition-colors text-xs
                      ${isSelected
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted/50'
                      }
                    `}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium flex items-center gap-2">
                        {isSelected ? '> ' : ''}{command.label}
                        {command.isLocal && (
                          <span className="text-[10px] px-1.5 py-0.5 bg-green-500/20 text-green-600 dark:text-green-400 rounded">
                            LOCAL
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground line-clamp-1">
                        {command.description}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
