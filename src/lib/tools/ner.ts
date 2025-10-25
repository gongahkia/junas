import { NERResult } from '@/types/tool';

export class NERProcessor {
  static async extractEntities(text: string): Promise<NERResult> {
    const entities = {
      PERSON: [] as string[],
      ORG: [] as string[],
      DATE: [] as string[],
      MONEY: [] as string[],
      LAW: [] as string[],
      GPE: [] as string[],
    };

    // Extract PERSON entities (names, parties)
    const personPatterns = [
      /(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*/g,
      /[A-Z][a-z]+\s+[A-Z][a-z]+/g, // Simple name pattern
      /(?:Plaintiff|Defendant|Appellant|Respondent|Claimant|Respondent)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gi,
    ];
    
    personPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.PERSON.push(...matches.map(m => m.trim()));
      }
    });

    // Extract ORG entities (companies, courts, organizations)
    const orgPatterns = [
      /(?:Ltd|Limited|Inc|Corporation|Corp|LLC|Pte|Private|Public)\s+[A-Z][a-z]+/gi,
      /(?:Court|Tribunal|Commission|Authority|Ministry|Department)\s+of\s+[A-Z][a-z]+/gi,
      /[A-Z][a-z]+\s+(?:Court|Tribunal|Commission|Authority)/gi,
    ];
    
    orgPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.ORG.push(...matches.map(m => m.trim()));
      }
    });

    // Extract DATE entities
    const datePatterns = [
      /\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}/g,
      /\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}/g,
      /(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}/gi,
      /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}/gi,
    ];
    
    datePatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.DATE.push(...matches.map(m => m.trim()));
      }
    });

    // Extract MONEY entities
    const moneyPatterns = [
      /\$[\d,]+(?:\.\d{2})?/g,
      /S\$[\d,]+(?:\.\d{2})?/g,
      /USD\s*[\d,]+(?:\.\d{2})?/gi,
      /SGD\s*[\d,]+(?:\.\d{2})?/gi,
      /[\d,]+(?:\.\d{2})?\s*(?:dollars?|USD|SGD)/gi,
    ];
    
    moneyPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.MONEY.push(...matches.map(m => m.trim()));
      }
    });

    // Extract LAW entities (statutes, cases, legal provisions)
    const lawPatterns = [
      /(?:s\.|section)\s*\d+[a-z]?(?:\s*\([a-z]\))?/gi,
      /(?:Act|Regulation|Rule|Order)\s+(?:No\.?\s*)?\d+\s+of\s+\d{4}/gi,
      /(?:\[|\()\d{4}(\]|\))\s+[A-Z][a-z]+\s+v\.\s+[A-Z][a-z]+/g,
      /(?:Case|Matter|Appeal)\s+(?:No\.?\s*)?\d+\s+of\s+\d{4}/gi,
      /(?:Singapore|SG)\s+(?:Companies|Employment|Contract|Property)\s+(?:Act|Law)/gi,
    ];
    
    lawPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.LAW.push(...matches.map(m => m.trim()));
      }
    });

    // Extract GPE entities (geopolitical entities, jurisdictions)
    const gpePatterns = [
      /Singapore/gi,
      /(?:United States|USA|US)/gi,
      /(?:United Kingdom|UK|Britain)/gi,
      /(?:Malaysia|Malaysia)/gi,
      /(?:Hong Kong|HK)/gi,
      /(?:Australia|AUS)/gi,
      /(?:China|PRC)/gi,
      /(?:India|IND)/gi,
    ];
    
    gpePatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        entities.GPE.push(...matches.map(m => m.trim()));
      }
    });

    // Remove duplicates and calculate confidence
    Object.keys(entities).forEach(key => {
      entities[key as keyof typeof entities] = [...new Set(entities[key as keyof typeof entities])];
    });

    const totalEntities = Object.values(entities).flat().length;
    const confidence = totalEntities > 0 ? Math.min(0.9, 0.5 + (totalEntities / 100)) : 0;

    return {
      entities,
      confidence,
    };
  }

  static async extractParties(text: string): Promise<string[]> {
    const partyPatterns = [
      /(?:between|BETWEEN)\s+([^,]+(?:\s+and\s+[^,]+)*)/gi,
      /(?:Plaintiff|Defendant|Appellant|Respondent|Claimant|Respondent)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gi,
      /(?:Company|Corporation|Ltd|Limited|Inc|LLC|Pte)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)/gi,
    ];

    const parties: string[] = [];
    
    partyPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        matches.forEach(match => {
          const party = match.replace(/(?:between|BETWEEN|Plaintiff|Defendant|Appellant|Respondent|Claimant|Company|Corporation|Ltd|Limited|Inc|LLC|Pte)\s*:?\s*/i, '').trim();
          if (party && !parties.includes(party)) {
            parties.push(party);
          }
        });
      }
    });

    return parties;
  }

  static async extractDates(text: string): Promise<{ dates: string[]; types: Record<string, string[]> }> {
    const datePatterns = {
      // Standard date formats
      standard: /\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}/g,
      iso: /\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}/g,
      // Written dates
      written: /(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}/gi,
      abbreviated: /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}/gi,
      // Legal date references
      legal: /(?:on|as of|effective|commencing)\s+(?:the\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})/gi,
    };

    const dates: string[] = [];
    const types: Record<string, string[]> = {};

    Object.entries(datePatterns).forEach(([type, pattern]) => {
      const matches = text.match(pattern);
      if (matches) {
        types[type] = matches.map(m => m.trim());
        dates.push(...matches.map(m => m.trim()));
      }
    });

    return {
      dates: [...new Set(dates)],
      types,
    };
  }

  static async extractMonetaryAmounts(text: string): Promise<{ amounts: string[]; currencies: string[] }> {
    const moneyPatterns = [
      /\$[\d,]+(?:\.\d{2})?/g,
      /S\$[\d,]+(?:\.\d{2})?/g,
      /USD\s*[\d,]+(?:\.\d{2})?/gi,
      /SGD\s*[\d,]+(?:\.\d{2})?/gi,
      /[\d,]+(?:\.\d{2})?\s*(?:dollars?|USD|SGD)/gi,
    ];

    const amounts: string[] = [];
    const currencies: string[] = [];

    moneyPatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        amounts.push(...matches.map(m => m.trim()));
        
        // Extract currency codes
        matches.forEach(match => {
          if (match.includes('USD')) currencies.push('USD');
          if (match.includes('SGD') || match.includes('S$')) currencies.push('SGD');
          if (match.includes('$') && !match.includes('S$')) currencies.push('USD');
        });
      }
    });

    return {
      amounts: [...new Set(amounts)],
      currencies: [...new Set(currencies)],
    };
  }
}
