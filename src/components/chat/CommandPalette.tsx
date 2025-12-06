'use client';

import { useState, useEffect, useRef } from 'react';
import { Command } from 'lucide-react';
import { 
  Database, 
  Search, 
  FileText, 
  Users, 
  BarChart, 
  FileSearch,
  Scale,
  BookOpen,
  Briefcase,
  FileSignature
} from 'lucide-react';

export interface CommandItem {
  id: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  category: 'research' | 'analysis' | 'drafting' | 'tools';
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
      action: () => {},
    },
    {
      id: 'analyze-contract',
      label: 'analyze-contract',
      description: 'Extract key terms, obligations, and risks from contract',
      icon: <FileSearch className="h-4 w-4" />,
      category: 'analysis',
      action: () => {},
    },
    {
      id: 'extract-entities',
      label: 'extract-entities',
      description: 'Identify persons, organizations, dates, and legal references',
      icon: <Users className="h-4 w-4" />,
      category: 'analysis',
      action: () => {},
    },
    {
      id: 'summarize-document',
      label: 'summarize-document',
      description: 'Generate concise summary of legal document',
      icon: <FileText className="h-4 w-4" />,
      category: 'analysis',
      action: () => {},
    },
    {
      id: 'draft-clause',
      label: 'draft-clause',
      description: 'Generate legal clause based on requirements',
      icon: <FileSignature className="h-4 w-4" />,
      category: 'drafting',
      action: () => {},
    },
    {
      id: 'check-compliance',
      label: 'check-compliance',
      description: 'Verify regulatory compliance for Singapore law',
      icon: <Scale className="h-4 w-4" />,
      category: 'tools',
      action: () => {},
    },
    {
      id: 'research-statute',
      label: 'research-statute',
      description: 'Look up statutory provisions and interpretations',
      icon: <BookOpen className="h-4 w-4" />,
      category: 'research',
      action: () => {},
    },
    {
      id: 'due-diligence-review',
      label: 'due-diligence-review',
      description: 'Conduct legal due diligence checklist',
      icon: <Briefcase className="h-4 w-4" />,
      category: 'analysis',
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

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => 
          prev < filteredCommands.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredCommands[selectedIndex]) {
          handleCommandSelect(filteredCommands[selectedIndex]);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedIndex, filteredCommands, onClose]);

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
      className="absolute bottom-full left-0 right-0 mb-2 bg-background border rounded-lg shadow-lg max-h-96 overflow-y-auto z-50"
    >
      <div className="sticky top-0 bg-background border-b px-3 py-2 flex items-center gap-2">
        <Command className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Commands</span>
        {searchQuery && (
          <span className="text-xs text-muted-foreground ml-auto">
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
          {Object.entries(groupedCommands).map(([category, cmds]) => (
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
                      w-full px-3 py-2 flex items-start gap-3 text-left transition-colors
                      ${isSelected 
                        ? 'bg-primary/10 text-primary' 
                        : 'hover:bg-muted/50'
                      }
                    `}
                  >
                    <div className={`
                      mt-0.5 flex-shrink-0
                      ${isSelected ? 'text-primary' : 'text-muted-foreground'}
                    `}>
                      {command.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium">
                        {command.label}
                      </div>
                      <div className="text-xs text-muted-foreground line-clamp-1">
                        {command.description}
                      </div>
                    </div>
                    <div className="text-xs text-muted-foreground font-mono flex-shrink-0">
                      /{command.id}
                    </div>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}

      <div className="sticky bottom-0 bg-muted/50 border-t px-3 py-2 text-xs text-muted-foreground">
        <div className="flex items-center justify-between">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>Esc Close</span>
        </div>
      </div>
    </div>
  );
}
