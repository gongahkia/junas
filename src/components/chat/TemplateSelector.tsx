'use client'

import { useState, useMemo, useEffect } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { FileText, X, Search, Briefcase, Users, Building, Home, DollarSign, Scale, Lightbulb, FileSignature, Star, Plus } from 'lucide-react'
import {
  legalTemplates,
  templateCategories,
  getTemplatesByCategory,
  searchTemplatesByKeywords,
  type TemplateCategory,
  type LegalTemplate,
} from '@/lib/templates'
import { getCustomTemplates, type CustomTemplate } from '@/lib/custom-templates'
import { getFavoriteTemplates, toggleFavorite, isFavorite } from '@/lib/template-favorites'
import { CustomTemplateDialog } from './CustomTemplateDialog'

interface TemplateSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelectTemplate: (template: LegalTemplate) => void
}

export function TemplateSelector({ isOpen, onClose, onSelectTemplate }: TemplateSelectorProps) {
  const [selectedCategory, setSelectedCategory] = useState<TemplateCategory>('All')
  const [selectedTemplate, setSelectedTemplate] = useState<LegalTemplate | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [customTemplates, setCustomTemplates] = useState<CustomTemplate[]>([])
  const [showCustomDialog, setShowCustomDialog] = useState(false)
  const [templateToClone, setTemplateToClone] = useState<LegalTemplate | undefined>()
  const [favorites, setFavorites] = useState<string[]>([])
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)

  // Load custom templates and favorites on mount
  useEffect(() => {
    setCustomTemplates(getCustomTemplates())
    setFavorites(getFavoriteTemplates())
  }, [isOpen]) // Reload when dialog opens

  const refreshCustomTemplates = () => {
    setCustomTemplates(getCustomTemplates())
  }

  const handleToggleFavorite = (templateId: string, e: React.MouseEvent) => {
    e.stopPropagation() // Prevent card click
    toggleFavorite(templateId)
    setFavorites(getFavoriteTemplates())
  }

  // Combine built-in and custom templates
  const allTemplates = useMemo(() => {
    return [...legalTemplates, ...customTemplates]
  }, [customTemplates])

  // Category icons mapping
  const categoryIcons: Record<TemplateCategory, any> = {
    'All': FileText,
    'Contracts': FileSignature,
    'Employment': Users,
    'Corporate': Building,
    'Property': Home,
    'Finance': DollarSign,
    'Dispute Resolution': Scale,
    'Intellectual Property': Lightbulb,
    'Clauses': Briefcase,
  }

  // Filter templates by both category and search query
  const filteredTemplates = useMemo(() => {
    let templates = selectedCategory === 'All' 
      ? allTemplates 
      : allTemplates.filter(t => t.category === selectedCategory)
    
    // Filter by favorites if enabled
    if (showFavoritesOnly) {
      templates = templates.filter(t => favorites.includes(t.id))
    }
    
    if (searchQuery.trim()) {
      // If there's a search query, apply keyword search to all templates
      const keywords = searchQuery.toLowerCase().split(/\s+/).filter(k => k.length > 0)
      templates = templates.filter(template => {
        return keywords.some(keyword => 
          template.name.toLowerCase().includes(keyword) ||
          template.category.toLowerCase().includes(keyword) ||
          template.description.toLowerCase().includes(keyword)
        )
      })
    }
    
    // Sort: favorites first, then alphabetically
    return templates.sort((a, b) => {
      const aFav = favorites.includes(a.id)
      const bFav = favorites.includes(b.id)
      if (aFav && !bFav) return -1
      if (!aFav && bFav) return 1
      return a.name.localeCompare(b.name)
    })
  }, [selectedCategory, searchQuery, allTemplates, favorites, showFavoritesOnly])

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
          <div className="pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setTemplateToClone(undefined)
                setShowCustomDialog(true)
              }}
              className="gap-2"
            >
              <Plus className="w-4 h-4" />
              Create Custom Template
            </Button>
          </div>
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
                    <Button
                      variant={showFavoritesOnly ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
                      className="gap-1.5"
                    >
                      <Star className={showFavoritesOnly ? "w-4 h-4 fill-current" : "w-4 h-4"} />
                      Favorites
                    </Button>
                    {templateCategories.map((category) => {
                      const Icon = categoryIcons[category]
                      return (
                        <Button
                          key={category}
                          variant={selectedCategory === category && !showFavoritesOnly ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => {
                            setSelectedCategory(category)
                            setShowFavoritesOnly(false)
                          }}
                          className="gap-1.5"
                        >
                          <Icon className="w-4 h-4" />
                          {category}
                        </Button>
                      )
                    })}
                  </div>
                  <div className="text-sm text-muted-foreground whitespace-nowrap ml-4">
                    {filteredTemplates.length} {filteredTemplates.length === 1 ? 'template' : 'templates'}
                  </div>
                </div>
              </div>

              {/* Template Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredTemplates.map((template) => {
                  const isCustom = 'isCustom' in template && template.isCustom
                  const isFav = favorites.includes(template.id)
                  return (
                    <Card
                      key={template.id}
                      className="cursor-pointer hover:border-primary hover:shadow-md transition-all group relative"
                      onClick={() => setSelectedTemplate(template)}
                    >
                      {/* Favorite Star Button */}
                      <button
                        onClick={(e) => handleToggleFavorite(template.id, e)}
                        className="absolute top-3 right-3 p-1.5 rounded-md hover:bg-secondary transition-colors z-10"
                        title={isFav ? "Remove from favorites" : "Add to favorites"}
                      >
                        <Star className={`w-5 h-5 transition-all ${
                          isFav 
                            ? 'text-yellow-500 fill-yellow-500' 
                            : 'text-muted-foreground hover:text-yellow-500'
                        }`} />
                      </button>
                      
                      <CardHeader className="pr-12">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-2 flex-1">
                            <FileText className="w-5 h-5 text-primary flex-shrink-0" />
                            <CardTitle className="text-lg group-hover:text-primary transition-colors">
                              {template.name}
                            </CardTitle>
                            {isCustom && (
                              <span className="px-2 py-0.5 text-xs bg-primary/10 text-primary rounded-md" title="Custom template">
                                Custom
                              </span>
                            )}
                          </div>
                        </div>
                        <CardDescription className="line-clamp-2 group-hover:line-clamp-none transition-all">
                          {template.description}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="bg-secondary px-2 py-1 rounded-md">
                            {template.category}
                          </span>
                          <span className="text-primary font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                            Click to view →
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
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

              <div className="flex justify-between space-x-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setTemplateToClone(selectedTemplate)
                    setShowCustomDialog(true)
                  }}
                  className="gap-2"
                >
                  <Star className="w-4 h-4" />
                  Save as Custom
                </Button>
                <div className="flex space-x-2">
                  <Button variant="outline" onClick={() => setSelectedTemplate(null)}>
                    Cancel
                  </Button>
                  <Button onClick={handleUseTemplate}>
                    Use This Template
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </DialogContent>

      {/* Custom Template Creator Dialog */}
      <CustomTemplateDialog
        isOpen={showCustomDialog}
        onClose={() => {
          setShowCustomDialog(false)
          setTemplateToClone(undefined)
        }}
        onSaved={refreshCustomTemplates}
        baseTemplate={templateToClone}
      />
    </Dialog>
  )
}
