'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { FileText, Sparkles, X } from 'lucide-react';
import { type LegalTemplate, type TemplateField } from '@/lib/templates';

interface TemplateFormProps {
  template: LegalTemplate;
  fields: TemplateField[];
  onSubmit: (formData: Record<string, string>) => void;
  onCancel: () => void;
}

export function TemplateForm({ template, fields, onSubmit, onCancel }: TemplateFormProps) {
  const [formData, setFormData] = useState<Record<string, string>>(() => {
    const initialData: Record<string, string> = {};
    fields.forEach(field => {
      initialData[field.id] = '';
    });
    return initialData;
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleChange = (fieldId: string, value: string) => {
    setFormData(prev => ({ ...prev, [fieldId]: value }));
    // Clear error for this field when user starts typing
    if (errors[fieldId]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[fieldId];
        return newErrors;
      });
    }
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    fields.forEach(field => {
      if (field.required && !formData[field.id]?.trim()) {
        newErrors[field.id] = `${field.label} is required`;
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    onSubmit(formData);
  };

  const renderField = (field: TemplateField) => {
    const commonProps = {
      id: field.id,
      value: formData[field.id] || '',
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        handleChange(field.id, e.target.value),
      placeholder: field.placeholder || `Enter ${field.label.toLowerCase()}`,
      className: errors[field.id] ? 'border-red-500' : '',
    };

    switch (field.type) {
      case 'textarea':
        return (
          <Textarea
            {...commonProps}
            rows={3}
            className={`resize-none ${errors[field.id] ? 'border-red-500' : ''}`}
          />
        );

      case 'date':
        return <Input {...commonProps} type="date" />;

      case 'email':
        return <Input {...commonProps} type="email" />;

      case 'number':
        return <Input {...commonProps} type="number" />;

      case 'select':
        return (
          <select
            id={field.id}
            value={formData[field.id] || ''}
            onChange={(e) => handleChange(field.id, e.target.value)}
            className={`w-full px-3 py-2 border rounded-md ${
              errors[field.id] ? 'border-red-500' : 'border-input'
            } bg-background`}
          >
            <option value="">Select an option</option>
            {field.options?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        );

      default:
        return <Input {...commonProps} type="text" />;
    }
  };

  return (
    <div className="border-t bg-background">
      <div className="max-w-6xl mx-auto px-6 py-6">
        <Card className="border-primary/20">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-primary" />
                    {template.name}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {template.description}
                  </CardDescription>
                </div>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onCancel}
                className="h-8 w-8 p-0"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Informational banner */}
              <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 p-4 rounded-lg">
                <p className="text-sm text-blue-900 dark:text-blue-100">
                  <strong>Fill in the details below.</strong> Junas will use this information to
                  draft a comprehensive legal document tailored to your needs.
                </p>
              </div>

              {/* Dynamic form fields */}
              {fields.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>This template doesn't require any specific fields.</p>
                  <p className="text-sm mt-2">Click "Generate Document" to proceed.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {fields.map((field) => (
                    <div
                      key={field.id}
                      className={field.type === 'textarea' ? 'md:col-span-2' : ''}
                    >
                      <label
                        htmlFor={field.id}
                        className="block text-sm font-medium mb-2"
                      >
                        {field.label}
                        {field.required && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {field.description}
                        </p>
                      )}
                      {errors[field.id] && (
                        <p className="text-xs text-red-500 mt-1">{errors[field.id]}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Form actions */}
              <div className="flex items-center justify-between pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  <span className="text-red-500">*</span> Required fields
                </div>
                <div className="flex gap-2">
                  <Button type="button" variant="outline" onClick={onCancel}>
                    Cancel
                  </Button>
                  <Button type="submit" className="gap-2">
                    <Sparkles className="w-4 h-4" />
                    Generate Document
                  </Button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
