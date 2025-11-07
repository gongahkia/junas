'use client'

import { useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { saveCustomTemplate, cloneTemplate } from '@/lib/custom-templates'
import { templateCategories, type TemplateCategory, type LegalTemplate } from '@/lib/templates'
import { useToast } from '@/components/ui/toast'

interface CustomTemplateDialogProps {
  isOpen: boolean
  onClose: () => void
  onSaved?: () => void
  baseTemplate?: LegalTemplate // If provided, starts as a clone
}

export function CustomTemplateDialog({ isOpen, onClose, onSaved, baseTemplate }: CustomTemplateDialogProps) {
  const [name, setName] = useState(baseTemplate?.name || '')
  const [description, setDescription] = useState(baseTemplate?.description || '')
  const [category, setCategory] = useState<TemplateCategory>(baseTemplate?.category as TemplateCategory || 'Contracts')
  const [prompt, setPrompt] = useState(baseTemplate?.prompt || '')
  const [isSaving, setIsSaving] = useState(false)
  const { addToast } = useToast()

  const handleSave = async () => {
    if (!name.trim() || !description.trim() || !prompt.trim()) {
      addToast({
        type: 'error',
        title: 'Validation Error',
        description: 'Please fill in all fields',
        duration: 3000
      })
      return
    }

    setIsSaving(true)
    try {
      if (baseTemplate) {
        cloneTemplate(baseTemplate, { name, description, category, prompt })
      } else {
        saveCustomTemplate({ name, description, category, prompt })
      }

      addToast({
        type: 'success',
        title: 'Template Saved',
        description: `"${name}" has been saved to your custom templates`,
        duration: 3000
      })

      // Reset form
      setName('')
      setDescription('')
      setCategory('Contracts')
      setPrompt('')

      onSaved?.()
      onClose()
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Save Failed',
        description: 'Failed to save custom template. Please try again.',
        duration: 3000
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {baseTemplate ? 'Save as Custom Template' : 'Create Custom Template'}
          </DialogTitle>
          <DialogDescription>
            {baseTemplate 
              ? 'Customize and save this template with your modifications'
              : 'Create a new legal document template for future use'
            }
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="template-name">Template Name</Label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., My Custom NDA"
            />
          </div>

          <div>
            <Label htmlFor="template-description">Description</Label>
            <Textarea
              id="template-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this template's purpose"
              rows={2}
            />
          </div>

          <div>
            <Label htmlFor="template-category">Category</Label>
            <select
              id="template-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as TemplateCategory)}
              className="w-full px-3 py-2 border rounded-md"
            >
              {templateCategories.filter(c => c !== 'All').map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="template-prompt">Template Prompt</Label>
            <Textarea
              id="template-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter the detailed prompt that will be used to generate documents from this template..."
              rows={12}
              className="font-mono text-sm"
            />
          </div>
        </div>

        <div className="flex justify-end space-x-2 pt-4">
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : baseTemplate ? 'Save as Custom' : 'Create Template'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
