'use client'

import { useState, useMemo } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Search, MessageSquare, User, Bot, X } from 'lucide-react'
import { Message } from '@/types/chat'
import { searchMessages, type SearchResult } from '@/lib/search'
import { Button } from '@/components/ui/button'

interface SearchDialogProps {
  isOpen: boolean
  onClose: () => void
  messages: Message[]
  onMessageSelect?: (messageId: string) => void
}

export function SearchDialog({ isOpen, onClose, messages, onMessageSelect }: SearchDialogProps) {
  const [query, setQuery] = useState('')

  // Perform search with memoization for performance
  const searchResults = useMemo(() => {
    if (!query.trim()) return []
    return searchMessages(query, messages, { limit: 20 })
  }, [query, messages])

  const handleMessageClick = (messageId: string) => {
    onMessageSelect?.(messageId)
    onClose()
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Search Conversation</DialogTitle>
          <DialogDescription>
            Search through your conversation messages
          </DialogDescription>
        </DialogHeader>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search messages..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-10"
            autoFocus
          />
          {query && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setQuery('')}
              className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto space-y-3 mt-4">
          {!query.trim() ? (
            <div className="text-center py-12 text-muted-foreground">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>Start typing to search through your messages</p>
            </div>
          ) : searchResults.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No messages found matching "{query}"</p>
            </div>
          ) : (
            <>
              <div className="text-sm text-muted-foreground mb-2">
                Found {searchResults.length} {searchResults.length === 1 ? 'message' : 'messages'}
              </div>
              {searchResults.map((result) => (
                <SearchResultItem
                  key={result.message.id}
                  result={result}
                  query={query}
                  onClick={() => handleMessageClick(result.message.id)}
                />
              ))}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// Separate component for search result items
function SearchResultItem({
  result,
  query,
  onClick,
}: {
  result: SearchResult
  query: string
  onClick: () => void
}) {
  const { message, matchedText } = result
  const isUser = message.role === 'user'

  // Highlight the query in the matched text
  const highlightedText = useMemo(() => {
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi')
    return matchedText.replace(
      regex,
      '<mark class="bg-yellow-200 dark:bg-yellow-800 rounded px-0.5">$1</mark>'
    )
  }, [matchedText, query])

  return (
    <Card
      className="p-4 cursor-pointer hover:bg-accent transition-colors"
      onClick={onClick}
    >
      <div className="flex items-start space-x-3">
        {/* Icon */}
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser ? 'bg-primary text-primary-foreground' : 'bg-secondary text-secondary-foreground'
          }`}
        >
          {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-semibold">
              {isUser ? 'User' : 'Junas'}
            </span>
            {message.timestamp && (
              <span className="text-xs text-muted-foreground">
                {new Date(message.timestamp).toLocaleString()}
              </span>
            )}
          </div>
          <div
            className="text-sm text-muted-foreground line-clamp-3"
            dangerouslySetInnerHTML={{ __html: highlightedText }}
          />
        </div>
      </div>
    </Card>
  )
}

// Utility function to escape regex special characters
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}
