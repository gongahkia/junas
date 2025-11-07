'use client';

import { Conversation } from '@/types/chat';
import { Button } from '@/components/ui/button';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from '@/components/ui/select';
import { Trash2, GitBranch } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

interface ConversationSwitcherProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew?: () => void;
}

export function ConversationSwitcher({ conversations, activeId, onSelect, onDelete, onNew }: ConversationSwitcherProps) {
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (!conversations.length) {
    return <div className="text-xs text-muted-foreground">No conversations yet</div>;
  }

  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 min-w-0">
        <Select value={activeId || ''} onValueChange={(val) => onSelect(val)}>
          <SelectTrigger className="h-8 text-xs">
            <SelectValue placeholder="Select conversation" />
          </SelectTrigger>
          <SelectContent>
            {conversations.map(c => (
              <SelectItem key={c.id} value={c.id} className="text-xs">
                <div className="flex items-center gap-1">
                  {c.parentId && <GitBranch className="w-3 h-3 text-muted-foreground" />}
                  <span className="truncate max-w-[180px]" title={c.title}>{c.title}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {onNew && (
        <Button variant="outline" size="sm" className="h-8" onClick={onNew}>New</Button>
      )}
      {activeId && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-muted-foreground hover:bg-muted"
          onClick={() => {
            if (!confirmDelete) {
              setConfirmDelete(activeId);
              setTimeout(() => setConfirmDelete(null), 3000);
              return;
            }
            onDelete(activeId);
            setConfirmDelete(null);
          }}
        >
          <Trash2 className={cn('w-3 h-3', confirmDelete ? 'text-destructive' : '')} />
          <span className="sr-only">Delete conversation</span>
        </Button>
      )}
    </div>
  );
}
