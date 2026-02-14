import re
import os
import json
import spacy
from dataclasses import dataclass, field
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from typing import Optional

RESTRICTED_LIST_PATH = os.path.join(os.path.dirname(__file__), "restricted_list.json")
ABS_THRESHOLD = float(os.getenv("MNPI_ABS_THRESHOLD", "1000000")) # $1M default
PCT_THRESHOLD = float(os.getenv("MNPI_PCT_THRESHOLD", "5.0")) # 5% default

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

@dataclass
class LexiconResult:
    flagged: bool = False
    high_risk_short_circuit: bool = False # if true, skip downstream models
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
        for ent in doc.ents:
            if ent.label_ in ("MONEY", "ORG", "PERSON"):
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
        high_hits = [h for h in result.hits if h.severity == "high"]
        result.flagged = len(high_hits) > 0
        result.high_risk_short_circuit = len(restricted_ents) > 0 or any(h.rule == "money_threshold" for h in high_hits) # short-circuit if restricted entity or large financial figure
        return result
