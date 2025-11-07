'use client'

import { useState, useMemo } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { FileText, X, Search } from 'lucide-react'
import {
  legalTemplates,
  templateCategories,
  getTemplatesByCategory,
  searchTemplatesByKeywords,
  type TemplateCategory,
  type LegalTemplate,
} from '@/lib/templates'

interface TemplateSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelectTemplate: (template: LegalTemplate) => void
}

export function TemplateSelector({ isOpen, onClose, onSelectTemplate }: TemplateSelectorProps) {
  const [selectedCategory, setSelectedCategory] = useState<TemplateCategory>('All')
  const [selectedTemplate, setSelectedTemplate] = useState<LegalTemplate | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  // Filter templates by both category and search query
  const filteredTemplates = useMemo(() => {
    let templates = getTemplatesByCategory(selectedCategory)
    
    if (searchQuery.trim()) {
      // If there's a search query, apply keyword search
      const searchResults = searchTemplatesByKeywords(searchQuery)
      // Intersect with category filter
      if (selectedCategory !== 'All') {
        templates = searchResults.filter(t => templates.some(ct => ct.id === t.id))
      } else {
        templates = searchResults
      }
    }
    
    return templates
  }, [selectedCategory, searchQuery])

  const handleUseTemplate = () => {
    if (selectedTemplate) {
      onSelectTemplate(selectedTemplate)
      setSelectedTemplate(null)
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Legal Document Templates</DialogTitle>
          <DialogDescription>
            Select a template to get started with common legal documents for Singapore law
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {!selectedTemplate ? (
            <div className="space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search templates by name, category, or description..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-10"
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    aria-label="Clear search"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>

              {/* Category Filter */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-2">
                    {templateCategories.map((category) => (
                      <Button
                        key={category}
                        variant={selectedCategory === category ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setSelectedCategory(category)}
                      >
                        {category}
                      </Button>
                    ))}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {filteredTemplates.length} {filteredTemplates.length === 1 ? 'template' : 'templates'}
                  </div>
                </div>
              </div>

              {/* Template Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredTemplates.map((template) => (
                  <Card
                    key={template.id}
                    className="cursor-pointer hover:border-primary transition-colors"
                    onClick={() => setSelectedTemplate(template)}
                  >
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex items-center space-x-2">
                          <FileText className="w-5 h-5 text-primary" />
                          <CardTitle className="text-lg">{template.name}</CardTitle>
                        </div>
                      </div>
                      <CardDescription>{template.description}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="text-xs text-muted-foreground">
                        Category: {template.category}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {filteredTemplates.length === 0 && (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="text-lg font-medium mb-2">No templates found</p>
                  <p className="text-sm">
                    {searchQuery 
                      ? `No templates match "${searchQuery}". Try a different search term.`
                      : `No templates found in the "${selectedCategory}" category.`
                    }
                  </p>
                  {(searchQuery || selectedCategory !== 'All') && (
                    <Button
                      variant="link"
                      size="sm"
                      onClick={() => {
                        setSearchQuery('')
                        setSelectedCategory('All')
                      }}
                      className="mt-2"
                    >
                      Clear filters
                    </Button>
                  )}
                </div>
              )}
            </div>
          ) : (
            // Template Detail View
            <div className="space-y-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedTemplate(null)}
                className="mb-2"
              >
                ← Back to templates
              </Button>

              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle>{selectedTemplate.name}</CardTitle>
                      <CardDescription className="mt-2">
                        {selectedTemplate.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="text-sm font-semibold mb-2">Category:</div>
                    <div className="text-sm text-muted-foreground">
                      {selectedTemplate.category}
                    </div>
                  </div>

                  <div>
                    <div className="text-sm font-semibold mb-2">Template Prompt:</div>
                    <div className="text-sm text-muted-foreground bg-muted p-4 rounded-md whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {selectedTemplate.prompt}
                    </div>
                  </div>

                  <div className="bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 p-4 rounded-md">
                    <p className="text-sm text-yellow-900 dark:text-yellow-100">
                      <strong>Disclaimer:</strong> This template provides a starting point only.
                      Always consult with a qualified lawyer for legal advice specific to your situation.
                    </p>
                  </div>
                </CardContent>
              </Card>

              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setSelectedTemplate(null)}>
                  Cancel
                </Button>
                <Button onClick={handleUseTemplate}>
                  Use This Template
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
