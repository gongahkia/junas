import re
import sys
import os
import json
import spacy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_config_val, _cfg
from dataclasses import dataclass, field
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from typing import Optional

RESTRICTED_LIST_PATH = os.path.join(os.path.dirname(__file__), "restricted_list.json")
ABS_THRESHOLD = get_config_val("thresholds", "mnpi_abs", "MNPI_ABS_THRESHOLD", 1000000.0, float)
PCT_THRESHOLD = get_config_val("thresholds", "mnpi_pct", "MNPI_PCT_THRESHOLD", 5.0, float)

LEXICON_SCORE_THRESHOLD = float(_cfg.get("lexicon", {}).get("score_threshold", 10.0))
LEXICON_WEIGHTS = _cfg.get("lexicon_weights", {})
DEFAULT_HIGH_WEIGHT = float(LEXICON_WEIGHTS.get("default_high", 3.0))
DEFAULT_INFO_WEIGHT = float(LEXICON_WEIGHTS.get("default_info", 0.5))

def get_rule_weight(rule: str, severity: str) -> float:
    if rule in LEXICON_WEIGHTS:
        return float(LEXICON_WEIGHTS[rule])
    return DEFAULT_HIGH_WEIGHT if severity == "high" else DEFAULT_INFO_WEIGHT

MONEY_PATTERN = re.compile( # matches $1,000,000 | €500K | £2.5M | ¥100B | 1.5 billion etc
    r'[\$€£¥]?\s*\d[\d,]*\.?\d*\s*(?:thousand|million|billion|trillion|[KMBT])\b'
    r'|[\$€£¥]\s*\d[\d,]*\.?\d*',
    re.IGNORECASE
)
PCT_PATTERN = re.compile(r'(\d+\.?\d*)\s*%') # matches N% values

MULTIPLIERS = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}

def _parse_amount(raw: str) -> Optional[float]:
    cleaned = re.sub(r'[\$€£¥,\s]', '', raw).lower() # strip currency symbols and commas
    for suffix, mult in MULTIPLIERS.items():
        if cleaned.endswith(suffix):
            try:
                return float(cleaned[:len(cleaned)-len(suffix)]) * mult
            except ValueError:
                return None
    try:
        return float(cleaned)
    except ValueError:
        return None

@dataclass
class LexiconHit:
    rule: str # which rule triggered
    matched_text: str
    severity: str # "high" or "info"
    detail: str = ""
    score: float = 0.0

@dataclass
class LexiconResult:
    flagged: bool = False
    high_risk_short_circuit: bool = False # if true, skip downstream models
    total_score: float = 0.0
    hits: list = field(default_factory=list)
    restricted_entities_found: list = field(default_factory=list)

class LexiconFilter:
    def __init__(self, restricted_list_path: str = RESTRICTED_LIST_PATH):
        self.nlp = spacy.load("en_core_web_sm")
        self.restricted = self._load_restricted(restricted_list_path)
        self.analyzer = self._build_presidio()
    def _load_restricted(self, path: str) -> list:
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return data.get("entities", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    def _build_presidio(self) -> AnalyzerEngine:
        engine = AnalyzerEngine()
        fin_patterns = [ # custom financial data patterns
            Pattern("ISIN", r'\b[A-Z]{2}[A-Z0-9]{9}\d\b', 0.7),
            Pattern("CUSIP", r'\b[A-Z0-9]{9}\b', 0.4),
        ]
        engine.registry.add_recognizer(PatternRecognizer(supported_entity="FINANCIAL_ID", patterns=fin_patterns, supported_language="en"))
        return engine
    def _check_money_threshold(self, text: str) -> list:
        hits = []
        for match in MONEY_PATTERN.finditer(text):
            raw = match.group()
            amount = _parse_amount(raw)
            if amount and amount >= ABS_THRESHOLD:
                hits.append(LexiconHit(rule="money_threshold", matched_text=raw, severity="high", detail=f"parsed={amount:.0f} >= threshold={ABS_THRESHOLD:.0f}"))
        return hits
    def _check_pct_threshold(self, text: str) -> list:
        hits = []
        for match in PCT_PATTERN.finditer(text):
            val = float(match.group(1))
            if val >= PCT_THRESHOLD:
                hits.append(LexiconHit(rule="pct_threshold", matched_text=match.group(), severity="high", detail=f"{val}% >= {PCT_THRESHOLD}%"))
        return hits
    def _check_restricted_list(self, text: str) -> tuple:
        hits, found = [], []
        text_lower = text.lower()
        for ent in self.restricted:
            name_match = ent["name"].lower() in text_lower
            ticker_match = re.search(r'\b' + re.escape(ent["ticker"]) + r'\b', text) # exact match for ticker
            isin_match = ent["isin"] in text
            if name_match or ticker_match or isin_match:
                matched = ent["name"] if name_match else (ent["ticker"] if ticker_match else ent["isin"])
                hits.append(LexiconHit(rule="restricted_list", matched_text=matched, severity="high", detail=f"entity={ent['name']} ticker={ent['ticker']}"))
                found.append(ent)
        return hits, found
    def _check_ner(self, text: str) -> list:
        hits = []
        doc = self.nlp(text)
        
        # Critical corporate event keywords
        critical_events = {
            "merger", "merge", "acquisition", "acquire", "buyout", "takeover",
            "bankruptcy", "bankrupt", "insolvent", "liquidate",
            "dividend", "earnings", "guidance", "scandal", "fraud",
            "resign", "resignation", "terminate", "layoff"
        }
        
        # Analyze entity interactions within sentence bounds
        for sent in doc.sents:
            sent_text_lower = sent.text.lower()
            found_events = [word for word in critical_events if word in sent_text_lower]
            
            orgs = [ent for ent in sent.ents if ent.label_ == "ORG"]
            people = [ent for ent in sent.ents if ent.label_ == "PERSON"]
            money = [ent for ent in sent.ents if ent.label_ == "MONEY"]
            
            # High risk: Critical event + Organization or Key Person
            if found_events and (orgs or people):
                entities_str = ", ".join([e.text for e in orgs + people])
                hits.append(LexiconHit(
                    rule="ner_event_entity_correlation",
                    matched_text=sent.text.strip(),
                    severity="high",
                    detail=f"events={found_events} entities=[{entities_str}]"
                ))
                
            # Info: Organization + Money mentioned together
            if orgs and money:
                org_str = ", ".join([e.text for e in orgs])
                money_str = ", ".join([e.text for e in money])
                hits.append(LexiconHit(
                    rule="ner_org_money_correlation",
                    matched_text=sent.text.strip(),
                    severity="info",
                    detail=f"orgs=[{org_str}] money=[{money_str}]"
                ))

        # Basic entity logging
        for ent in doc.ents:
            if ent.label_ in ("MONEY", "ORG", "PERSON", "GPE", "LAW"):
                hits.append(LexiconHit(rule=f"ner_{ent.label_.lower()}", matched_text=ent.text, severity="info", detail=f"spaCy label={ent.label_}"))
        return hits
    def _check_presidio(self, text: str) -> list:
        hits = []
        results = self.analyzer.analyze(text=text, language="en", entities=["CREDIT_CARD", "IBAN_CODE", "FINANCIAL_ID", "PHONE_NUMBER", "EMAIL_ADDRESS"])
        for r in results:
            hits.append(LexiconHit(rule=f"presidio_{r.entity_type.lower()}", matched_text=text[r.start:r.end], severity="high" if r.score >= 0.7 else "info", detail=f"score={r.score:.2f}"))
        return hits
    def run(self, text: str) -> LexiconResult:
        result = LexiconResult()
        result.hits.extend(self._check_money_threshold(text)) # financial figure threshold
        result.hits.extend(self._check_pct_threshold(text)) # percentage threshold
        restricted_hits, restricted_ents = self._check_restricted_list(text) # restricted list cross-ref
        result.hits.extend(restricted_hits)
        result.restricted_entities_found = restricted_ents
        result.hits.extend(self._check_ner(text)) # spaCy NER
        result.hits.extend(self._check_presidio(text)) # Presidio PII/financial
        
        total_score = 0.0
        for h in result.hits:
            h.score = get_rule_weight(h.rule, h.severity)
            total_score += h.score
            
        result.total_score = total_score
        
        high_hits = [h for h in result.hits if h.severity == "high"]
        result.flagged = len(high_hits) > 0

        # Deterministic short-circuit triggers align with documented policy.
        has_money_breach = any(h.rule == "money_threshold" and h.severity == "high" for h in high_hits)
        has_restricted_match = len(result.restricted_entities_found) > 0
        result.high_risk_short_circuit = has_restricted_match or has_money_breach
        return result
