'use client';

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { StorageManager } from '@/lib/storage';
import { searchGlobalConversations, highlightQuery } from '@/lib/search';
import { Conversation } from '@/types/chat';
import { MessageSquare, Trash2, Clock, Calendar, Search } from 'lucide-react';

interface HistoryDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectConversation: (conversation: Conversation) => void;
}

export function HistoryDialog({ isOpen, onClose, onSelectConversation }: HistoryDialogProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isOpen) {
      setConversations(StorageManager.getConversations());
      setSearchQuery(''); // Reset search on open
    }
  }, [isOpen]);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    StorageManager.deleteConversation(id);
    setConversations(StorageManager.getConversations());
  };

  const formatDate = (date: any) => {
    try {
        return new Intl.DateTimeFormat('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        }).format(new Date(date));
    } catch {
        return 'Unknown date';
    }
  };

  const searchResults = searchQuery 
    ? searchGlobalConversations(searchQuery, conversations) 
    : [];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-hidden flex flex-col font-mono">
        <DialogHeader>
          <DialogTitle className="text-sm font-mono uppercase tracking-widest flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Chat History
          </DialogTitle>
        </DialogHeader>

        <div className="px-1 py-2">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-9 text-xs"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto pr-2 space-y-2 py-2">
          {searchQuery ? (
            searchResults.length === 0 ? (
               <div className="text-center py-8 text-muted-foreground text-xs">
                No matching conversations found.
              </div>
            ) : (
              searchResults.map((result) => (
                <div
                  key={result.conversationId}
                  onClick={() => {
                    const conv = conversations.find(c => c.id === result.conversationId);
                    if (conv) {
                      onSelectConversation(conv);
                      onClose();
                    }
                  }}
                  className="group relative border border-muted-foreground/20 p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                >
                   <h3 className="text-xs font-semibold truncate mb-2 text-primary">
                      {result.title || 'Untitled Conversation'}
                    </h3>
                    
                    <div className="space-y-2">
                      {result.results.slice(0, 2).map((match, idx) => (
                         <div key={idx} className="text-[10px] text-muted-foreground bg-muted/30 p-1.5 rounded border border-muted-foreground/10">
                            <span className="font-bold uppercase text-[9px] opacity-70 mb-0.5 block">{match.message.role}</span>
                            <div 
                              dangerouslySetInnerHTML={{ 
                                __html: highlightQuery(match.matchedText, searchQuery) 
                              }} 
                            />
                         </div>
                      ))}
                      {result.results.length > 2 && (
                        <div className="text-[9px] text-muted-foreground/70 italic px-1">
                          +{result.results.length - 2} more matches
                        </div>
                      )}
                    </div>
                </div>
              ))
            )
          ) : (
            conversations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-xs">
                No previous conversations found.
              </div>
            ) : (
              conversations.map((conv) => (
                <div
                  key={conv.id}
                  onClick={() => {
                    onSelectConversation(conv);
                    onClose();
                  }}
                  className="group relative border border-muted-foreground/20 p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-xs font-semibold truncate mb-1">
                        {conv.title || 'Untitled Conversation'}
                      </h3>
                      <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {conv.messages.length} messages
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(conv.updatedAt)}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDelete(conv.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-destructive transition-all"
                      title="Delete conversation"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )
          )}
        </div>

        <div className="mt-4 pt-4 border-t border-muted-foreground/10 text-center">
            <button 
                onClick={onClose}
                className="text-[10px] text-muted-foreground hover:text-foreground transition-colors"
            >
                [ CLOSE ]
            </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}