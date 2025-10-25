import { ContractAnalysis, RiskFlag } from '@/types/tool';

export class ContractAnalyzer {
  static async analyzeContract(text: string): Promise<ContractAnalysis> {
    const analysis: ContractAnalysis = {
      parties: [],
      effectiveDate: '',
      term: '',
      paymentTerms: [],
      terminationProvisions: [],
      liabilityProvisions: [],
      disputeResolution: '',
      governingLaw: '',
      riskFlags: [],
    };

    // Extract parties
    analysis.parties = await this.extractParties(text);

    // Extract effective date
    analysis.effectiveDate = await this.extractEffectiveDate(text);

    // Extract term
    analysis.term = await this.extractTerm(text);

    // Extract payment terms
    analysis.paymentTerms = await this.extractPaymentTerms(text);

    // Extract termination provisions
    analysis.terminationProvisions = await this.extractTerminationProvisions(text);

    // Extract liability provisions
    analysis.liabilityProvisions = await this.extractLiabilityProvisions(text);

    // Extract dispute resolution
    analysis.disputeResolution = await this.extractDisputeResolution(text);

    // Extract governing law
    analysis.governingLaw = await this.extractGoverningLaw(text);

    // Analyze for risk flags
    analysis.riskFlags = await this.identifyRiskFlags(text);

    return analysis;
  }

  private static async extractParties(text: string): Promise<string[]> {
    const partyPatterns = [
      /(?:between|BETWEEN)\s+([^,]+(?:\s+and\s+[^,]+)*)/gi,
      /(?:Party|Parties)\s+(?:A|B|1|2)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gi,
      /(?:Company|Corporation|Ltd|Limited|Inc|LLC|Pte)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gi,
    ];

    const parties: string[] = [];
    
    partyPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        matches.forEach(match => {
          const party = match.replace(/(?:between|BETWEEN|Party|Parties|Company|Corporation|Ltd|Limited|Inc|LLC|Pte)\s*[A-Z]?\s*:?\s*/i, '').trim();
          if (party && !parties.includes(party)) {
            parties.push(party);
          }
        });
      }
    });

    return parties;
  }

  private static async extractEffectiveDate(text: string): Promise<string> {
    const datePatterns = [
      /(?:effective|commencing|starting)\s+(?:on\s+)?(?:the\s+)?(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})/gi,
      /(?:effective|commencing|starting)\s+(?:on\s+)?(?:the\s+)?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})/gi,
    ];

    for (const pattern of datePatterns) {
      const match = text.match(pattern);
      if (match) {
        return match[1] || match[0];
      }
    }

    return '';
  }

  private static async extractTerm(text: string): Promise<string> {
    const termPatterns = [
      /(?:term|duration|period)\s+(?:of\s+)?(\d+\s+(?:years?|months?|days?))/gi,
      /(?:for\s+a\s+)?(?:period\s+of\s+)?(\d+\s+(?:years?|months?|days?))/gi,
      /(?:commencing|starting)\s+(?:on\s+)?(?:the\s+)?\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s+(?:and\s+)?(?:continuing\s+for\s+)?(\d+\s+(?:years?|months?|days?))/gi,
    ];

    for (const pattern of termPatterns) {
      const match = text.match(pattern);
      if (match) {
        return match[1] || match[0];
      }
    }

    return '';
  }

  private static async extractPaymentTerms(text: string): Promise<string[]> {
    const paymentPatterns = [
      /(?:payment|pay|compensation|fee|price)\s+(?:of\s+)?(\$[\d,]+(?:\.\d{2})?)/gi,
      /(?:payment|pay|compensation|fee|price)\s+(?:of\s+)?(\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|USD|SGD))/gi,
      /(?:monthly|quarterly|annually|per\s+month|per\s+year)\s+(?:payment\s+of\s+)?(\$[\d,]+(?:\.\d{2})?)/gi,
    ];

    const payments: string[] = [];
    
    paymentPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        payments.push(...matches.map(m => m.trim()));
      }
    });

    return [...new Set(payments)];
  }

  private static async extractTerminationProvisions(text: string): Promise<string[]> {
    const terminationPatterns = [
      /(?:termination|terminate|end|expire)\s+(?:may\s+be\s+)?(?:by\s+)?(?:either\s+party\s+)?(?:with\s+)?(\d+\s+(?:days?|months?|years?)\s+(?:written\s+)?notice)/gi,
      /(?:termination|terminate|end|expire)\s+(?:may\s+be\s+)?(?:by\s+)?(?:either\s+party\s+)?(?:with\s+)?(?:immediate\s+effect)/gi,
      /(?:breach|default|violation)\s+(?:of\s+)?(?:this\s+)?(?:agreement|contract)\s+(?:shall\s+)?(?:result\s+in\s+)?(?:immediate\s+)?(?:termination)/gi,
    ];

    const terminations: string[] = [];
    
    terminationPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        terminations.push(...matches.map(m => m.trim()));
      }
    });

    return [...new Set(terminations)];
  }

  private static async extractLiabilityProvisions(text: string): Promise<string[]> {
    const liabilityPatterns = [
      /(?:liability|liable|responsible)\s+(?:for\s+)?(?:any\s+)?(?:and\s+all\s+)?(?:damages?|losses?|claims?|costs?)/gi,
      /(?:indemnify|indemnification|hold\s+harmless)\s+(?:against\s+)?(?:any\s+)?(?:and\s+all\s+)?(?:damages?|losses?|claims?|costs?)/gi,
      /(?:limitation\s+of\s+liability|liability\s+cap|maximum\s+liability)/gi,
    ];

    const liabilities: string[] = [];
    
    liabilityPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        liabilities.push(...matches.map(m => m.trim()));
      }
    });

    return [...new Set(liabilities)];
  }

  private static async extractDisputeResolution(text: string): Promise<string> {
    const disputePatterns = [
      /(?:dispute|disagreement|controversy)\s+(?:shall\s+be\s+)?(?:resolved\s+by\s+)?(?:arbitration|mediation|litigation)/gi,
      /(?:arbitration|mediation|litigation)\s+(?:in\s+)?(?:Singapore|Hong Kong|London|New York)/gi,
      /(?:governing\s+law|applicable\s+law)\s+(?:of\s+)?(?:Singapore|Hong Kong|England|New York)/gi,
    ];

    for (const pattern of disputePatterns) {
      const match = text.match(pattern);
      if (match) {
        return match[0];
      }
    }

    return '';
  }

  private static async extractGoverningLaw(text: string): Promise<string> {
    const lawPatterns = [
      /(?:governing\s+law|applicable\s+law)\s+(?:of\s+)?(?:Singapore|Hong Kong|England|New York|United States)/gi,
      /(?:this\s+)?(?:agreement|contract)\s+(?:shall\s+be\s+)?(?:governed\s+by\s+)?(?:the\s+)?(?:laws?\s+of\s+)?(?:Singapore|Hong Kong|England|New York|United States)/gi,
    ];

    for (const pattern of lawPatterns) {
      const match = text.match(pattern);
      if (match) {
        return match[0];
      }
    }

    return '';
  }

  private static async identifyRiskFlags(text: string): Promise<RiskFlag[]> {
    const riskFlags: RiskFlag[] = [];

    // Check for one-sided terms
    const oneSidedPatterns = [
      /(?:company|corporation|party\s+a)\s+(?:may|shall|will)\s+(?:terminate|end|cancel)/gi,
      /(?:employee|worker|staff)\s+(?:shall|will|must)\s+(?:not|never)/gi,
      /(?:company|corporation)\s+(?:reserves\s+the\s+right\s+to|may\s+unilaterally)/gi,
    ];

    oneSidedPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        riskFlags.push({
          type: 'one-sided',
          description: 'One-sided termination or restriction clause detected',
          severity: 'medium',
          clause: matches[0],
          suggestion: 'Consider balancing the clause to provide mutual rights and obligations',
        });
      }
    });

    // Check for missing clauses
    const missingClausePatterns = [
      /(?:confidentiality|non-disclosure)/gi,
      /(?:intellectual\s+property|IP)/gi,
      /(?:force\s+majeure|act\s+of\s+god)/gi,
      /(?:severability|survival)/gi,
    ];

    const hasConfidentiality = text.match(/(?:confidentiality|non-disclosure)/gi);
    const hasIP = text.match(/(?:intellectual\s+property|IP)/gi);
    const hasForceMajeure = text.match(/(?:force\s+majeure|act\s+of\s+god)/gi);
    const hasSeverability = text.match(/(?:severability|survival)/gi);

    if (!hasConfidentiality) {
      riskFlags.push({
        type: 'missing',
        description: 'No confidentiality or non-disclosure clause found',
        severity: 'high',
        suggestion: 'Consider adding a confidentiality clause to protect sensitive information',
      });
    }

    if (!hasIP) {
      riskFlags.push({
        type: 'missing',
        description: 'No intellectual property clause found',
        severity: 'medium',
        suggestion: 'Consider adding an IP clause to clarify ownership of intellectual property',
      });
    }

    if (!hasForceMajeure) {
      riskFlags.push({
        type: 'missing',
        description: 'No force majeure clause found',
        severity: 'low',
        suggestion: 'Consider adding a force majeure clause to address unforeseen circumstances',
      });
    }

    if (!hasSeverability) {
      riskFlags.push({
        type: 'missing',
        description: 'No severability clause found',
        severity: 'low',
        suggestion: 'Consider adding a severability clause to ensure contract validity',
      });
    }

    // Check for ambiguous language
    const ambiguousPatterns = [
      /(?:reasonable|appropriate|suitable|adequate)/gi,
      /(?:as\s+soon\s+as\s+possible|ASAP)/gi,
      /(?:best\s+efforts|reasonable\s+efforts)/gi,
      /(?:material|significant|substantial)/gi,
    ];

    ambiguousPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches && matches.length > 3) {
        riskFlags.push({
          type: 'ambiguous',
          description: 'Multiple instances of ambiguous language detected',
          severity: 'medium',
          clause: matches[0],
          suggestion: 'Consider defining specific terms and timeframes to avoid disputes',
        });
      }
    });

    // Check for unusual terms
    const unusualPatterns = [
      /(?:penalty|fine|forfeit)\s+(?:of\s+)?(\$[\d,]+(?:\.\d{2})?)/gi,
      /(?:exclusive|sole)\s+(?:right|authority|power)/gi,
      /(?:irrevocable|permanent|forever)/gi,
    ];

    unusualPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        riskFlags.push({
          type: 'unusual',
          description: 'Unusual or potentially problematic clause detected',
          severity: 'high',
          clause: matches[0],
          suggestion: 'Review this clause carefully and consider if it is necessary and fair',
        });
      }
    });

    return riskFlags;
  }
}
