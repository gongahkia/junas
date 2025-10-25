'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileText, Search, Scale, PenTool, Shield, BookOpen } from 'lucide-react';

interface DefaultPromptsProps {
  onPromptSelect: (prompt: string) => void;
}

const promptCategories = [
  {
    title: 'Contract Analysis',
    icon: FileText,
    color: 'text-blue-600',
    prompts: [
      'Review this contract and identify key risks, obligations, and missing clauses',
      'Analyze this NDA for one-sided terms and suggest balanced alternatives',
      'Extract all dates, parties, payment terms, and termination clauses from this agreement',
      'Compare this contract against standard industry terms and flag deviations',
      'Identify ambiguous language that could lead to disputes',
    ],
  },
  {
    title: 'Case Law & Research',
    icon: Search,
    color: 'text-green-600',
    prompts: [
      'Summarize the key holdings and legal principles from this case',
      'Find similar cases involving employment law in Singapore jurisdiction',
      'Extract ratio decidendi and obiter dicta from this judgment',
      'Identify precedents cited in this case and their relevance',
      'Draft a case brief with facts, issues, holdings, and reasoning',
    ],
  },
  {
    title: 'Statutory Analysis',
    icon: Scale,
    color: 'text-purple-600',
    prompts: [
      'Explain the statutory obligations under section 4 of the Companies Act',
      'Compare provisions between the Employment Act and the Industrial Relations Act',
      'Identify all defined terms in this statute and their implications',
      'Check compliance requirements under the Personal Data Protection Act',
      'Summarize legislative amendments to the Companies Act in the past 5 years',
    ],
  },
  {
    title: 'Document Drafting',
    icon: PenTool,
    color: 'text-orange-600',
    prompts: [
      'Draft a cease and desist letter for trademark infringement',
      'Generate a client advisory memo on data protection compliance',
      'Create a term sheet for a joint venture with key commercial terms',
      'Draft discovery requests for a breach of contract case',
      'Prepare a legal opinion on employment termination citing relevant authorities',
    ],
  },
  {
    title: 'Due Diligence',
    icon: Shield,
    color: 'text-red-600',
    prompts: [
      'Extract all material representations and warranties from this contract',
      'Identify potential regulatory compliance issues in this document',
      'Flag intellectual property ownership and licensing terms',
      'Summarize indemnification and liability provisions',
      'Check for jurisdiction and dispute resolution clauses',
    ],
  },
  {
    title: 'Citation & Research',
    icon: BookOpen,
    color: 'text-indigo-600',
    prompts: [
      'Find the full text of Lim Swee Khiang v Borden Co (Pte) Ltd [2006] 4 SLR(R) 745',
      'Verify if Tan Kok Tim Stanley v Personal Representatives [2019] SGCA 50 is still good law',
      'Search for cases interpreting section 4 of the Companies Act',
      'Locate Singapore statutes related to employment law',
      'Find academic commentary on the doctrine of frustration in contract law',
    ],
  },
];

export function DefaultPrompts({ onPromptSelect }: DefaultPromptsProps) {
  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-foreground mb-4">
          Welcome to Junas
        </h1>
        <p className="text-muted-foreground text-xl max-w-2xl mx-auto">
          Your AI legal assistant for Singapore law. Choose a prompt to get started.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6 max-w-6xl mx-auto">
        {promptCategories.map((category) => {
          const Icon = category.icon;
          return (
            <Card key={category.title} className="hover:shadow-lg transition-shadow">
              <CardHeader>
                <div className="flex items-center space-x-2">
                  <Icon className={`h-5 w-5 ${category.color}`} />
                  <CardTitle className="text-lg">{category.title}</CardTitle>
                </div>
                <CardDescription>
                  {category.prompts.length} prompts available
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {category.prompts.slice(0, 3).map((prompt, index) => (
                    <Button
                      key={index}
                      variant="ghost"
                      className="w-full justify-start text-left h-auto p-3"
                      onClick={() => onPromptSelect(prompt)}
                    >
                      <span className="text-sm leading-relaxed">{prompt}</span>
                    </Button>
                  ))}
                  {category.prompts.length > 3 && (
                    <div className="text-xs text-muted-foreground text-center pt-2">
                      +{category.prompts.length - 3} more prompts
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="mt-8 text-center">
        <p className="text-sm text-muted-foreground">
          Or start typing your own question in the input below
        </p>
      </div>
    </div>
  );
}
