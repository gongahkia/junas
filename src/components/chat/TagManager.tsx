'use client';

import { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { X, Tag } from 'lucide-react';
import { Conversation } from '@/types/chat';

interface TagManagerProps {
  conversation: Conversation;
  onUpdateTags: (conversationId: string, tags: string[]) => void;
}

export function TagManager({ conversation, onUpdateTags }: TagManagerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [localTags, setLocalTags] = useState<string[]>(conversation.tags || []);

  const handleAddTag = () => {
    const trimmed = newTag.trim().toLowerCase();
    if (trimmed && !localTags.includes(trimmed)) {
      const updated = [...localTags, trimmed];
      setLocalTags(updated);
      setNewTag('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setLocalTags(localTags.filter(t => t !== tag));
  };

  const handleSave = () => {
    onUpdateTags(conversation.id, localTags);
    setIsOpen(false);
  };

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 px-2 text-muted-foreground hover:bg-muted"
        onClick={() => setIsOpen(true)}
      >
        <Tag className="w-3 h-3" />
        <span className="sr-only">Manage tags</span>
      </Button>

      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Manage Tags</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="Add tag..."
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
                className="flex-1"
              />
              <Button onClick={handleAddTag}>Add</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {localTags.map(tag => (
                <div key={tag} className="inline-flex items-center gap-1 px-2 py-1 bg-primary/10 text-primary rounded-md text-xs">
                  <Tag className="w-3 h-3" />
                  <span>{tag}</span>
                  <button onClick={() => handleRemoveTag(tag)} className="hover:text-destructive">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {localTags.length === 0 && (
                <p className="text-xs text-muted-foreground">No tags yet. Add tags to organize conversations.</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsOpen(false)}>Cancel</Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
