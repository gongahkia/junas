'use client';

import { useState, useEffect, useCallback } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { X, ChevronUp, ChevronDown } from 'lucide-react';
import { Card } from '@/components/ui/card';

interface ChatSearchProps {
  isOpen: boolean;
  onClose: () => void;
  messages: Array<{ id: string; content: string; role: string }>;
  onHighlight?: (matchIndexes: number[]) => void;
}

export function ChatSearch({ isOpen, onClose, messages, onHighlight }: ChatSearchProps) {
  const [query, setQuery] = useState('');
  const [currentMatch, setCurrentMatch] = useState(0);
  const [matches, setMatches] = useState<Array<{ messageIndex: number; positions: number[] }>>([]);

  const findMatches = useCallback((searchQuery: string) => {
    if (!searchQuery.trim()) {
      setMatches([]);
      setCurrentMatch(0);
      return;
    }

    const results: Array<{ messageIndex: number; positions: number[] }> = [];
    const lowerQuery = searchQuery.toLowerCase();

    messages.forEach((msg, idx) => {
      const content = msg.content.toLowerCase();
      const positions: number[] = [];
      let pos = content.indexOf(lowerQuery);
      while (pos !== -1) {
        positions.push(pos);
        pos = content.indexOf(lowerQuery, pos + 1);
      }
      if (positions.length > 0) {
        results.push({ messageIndex: idx, positions });
      }
    });

    setMatches(results);
    setCurrentMatch(results.length > 0 ? 0 : -1);

    // Notify parent of match indexes for highlighting
    if (onHighlight) {
      const allIndexes = results.map(r => r.messageIndex);
      onHighlight(allIndexes);
    }
  }, [messages, onHighlight]);

  useEffect(() => {
    findMatches(query);
  }, [query, findMatches]);

  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setMatches([]);
      setCurrentMatch(0);
    }
  }, [isOpen]);

  const handleNext = () => {
    if (matches.length === 0) return;
    const total = matches.reduce((sum, m) => sum + m.positions.length, 0);
    setCurrentMatch((prev) => (prev + 1) % total);
  };

  const handlePrev = () => {
    if (matches.length === 0) return;
    const total = matches.reduce((sum, m) => sum + m.positions.length, 0);
    setCurrentMatch((prev) => (prev - 1 + total) % total);
  };

  const totalMatches = matches.reduce((sum, m) => sum + m.positions.length, 0);

  if (!isOpen) return null;

  return (
    <div className="fixed top-16 right-4 z-50 w-80">
      <Card className="p-3 shadow-lg">
        <div className="flex items-center gap-2">
          <Input
            type="text"
            placeholder="Search in conversation..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 h-8 text-sm"
            autoFocus
          />
          <div className="flex items-center gap-1">
            {totalMatches > 0 && (
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {currentMatch + 1}/{totalMatches}
              </span>
            )}
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={handlePrev} disabled={totalMatches === 0}>
              <ChevronUp className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={handleNext} disabled={totalMatches === 0}>
              <ChevronDown className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
