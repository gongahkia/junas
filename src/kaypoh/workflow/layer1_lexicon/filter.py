import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dataclasses import dataclass, field
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern, RecognizerRegistry
from presidio_analyzer.predefined_recognizers import CreditCardRecognizer, EmailRecognizer, IbanRecognizer, PhoneRecognizer
import spacy

from kaypoh.configs.runtime import get_runtime_settings

SETTINGS = get_runtime_settings()

RESTRICTED_LIST_PATH = os.path.join(os.path.dirname(__file__), "restricted_list.json")
ABS_THRESHOLD = SETTINGS.thresholds.mnpi_abs
PCT_THRESHOLD = SETTINGS.thresholds.mnpi_pct

LEXICON_SCORE_THRESHOLD = SETTINGS.lexicon.score_threshold
LEXICON_SCORE_THRESHOLD_MODE = SETTINGS.lexicon.score_threshold_mode
LEXICON_DYNAMIC_CHARS_PER_POINT = SETTINGS.lexicon.dynamic_chars_per_point
LEXICON_DYNAMIC_THRESHOLD_INCREMENT = SETTINGS.lexicon.dynamic_threshold_increment
LEXICON_WEIGHTS = dict(SETTINGS.lexicon_weights)
DEFAULT_HIGH_WEIGHT = float(LEXICON_WEIGHTS.get("default_high", 3.0))
DEFAULT_INFO_WEIGHT = float(LEXICON_WEIGHTS.get("default_info", 0.5))

def get_rule_weight(rule: str, severity: str) -> float:
    if rule in LEXICON_WEIGHTS:
        return float(LEXICON_WEIGHTS[rule])
    return DEFAULT_HIGH_WEIGHT if severity == "high" else DEFAULT_INFO_WEIGHT


def resolve_score_threshold(text: str) -> float:
    if LEXICON_SCORE_THRESHOLD_MODE != "dynamic":
        return LEXICON_SCORE_THRESHOLD

    chars_per_point = max(1.0, float(LEXICON_DYNAMIC_CHARS_PER_POINT))
    increment = max(0.0, float(LEXICON_DYNAMIC_THRESHOLD_INCREMENT))
    effective_threshold = LEXICON_SCORE_THRESHOLD + (len(text) / chars_per_point) * increment
    return round(effective_threshold, 3)

MONEY_PATTERN = re.compile( # matches $1,000,000 | €500K | £2.5M | ¥100B | 1.5 billion etc
    r'[\$€£¥]?\s*\d[\d,]*\.?\d*\s*(?:thousand|million|billion|trillion|[KMBT])\b'
    r'|[\$€£¥]\s*\d[\d,]*\.?\d*',
    re.IGNORECASE
)
PCT_PATTERN = re.compile(r'(\d+\.?\d*)\s*%') # matches N% values

MULTIPLIERS = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}


def _iter_literal_matches(text: str, needle: str, *, ignore_case: bool = False, word_boundary: bool = False):
    if not needle:
        return []

    escaped = re.escape(needle)
    pattern = rf"\b{escaped}\b" if word_boundary else escaped
    flags = re.IGNORECASE if ignore_case else 0
    return list(re.finditer(pattern, text, flags))

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
    start_char: Optional[int] = None
    end_char: Optional[int] = None

@dataclass
class LexiconResult:
    flagged: bool = False
    high_risk_short_circuit: bool = False # if true, skip downstream models
    total_score: float = 0.0
    score_threshold: float = LEXICON_SCORE_THRESHOLD
    score_threshold_exceeded: bool = False
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
        # Keep startup lean: only load recognizers we actually query.
        logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)
        registry = RecognizerRegistry()
        registry.add_recognizer(CreditCardRecognizer(supported_language="en"))
        registry.add_recognizer(IbanRecognizer(supported_language="en"))
        registry.add_recognizer(PhoneRecognizer(supported_language="en"))
        registry.add_recognizer(EmailRecognizer(supported_language="en"))
        engine = AnalyzerEngine(registry=registry, supported_languages=["en"])
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
                hits.append(
                    LexiconHit(
                        rule="money_threshold",
                        matched_text=raw,
                        severity="high",
                        detail=f"parsed={amount:.0f} >= threshold={ABS_THRESHOLD:.0f}",
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
        return hits
    def _check_pct_threshold(self, text: str) -> list:
        hits = []
        for match in PCT_PATTERN.finditer(text):
            val = float(match.group(1))
            if val >= PCT_THRESHOLD:
                hits.append(
                    LexiconHit(
                        rule="pct_threshold",
                        matched_text=match.group(),
                        severity="high",
                        detail=f"{val}% >= {PCT_THRESHOLD}%",
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
        return hits
    def _check_restricted_list(self, text: str) -> tuple:
        hits, found = [], []
        for ent in self.restricted:
            entity_found = False

            for match in _iter_literal_matches(text, ent.get("name", ""), ignore_case=True):
                hits.append(
                    LexiconHit(
                        rule="restricted_list",
                        matched_text=match.group(),
                        severity="high",
                        detail=f"entity={ent['name']} ticker={ent['ticker']}",
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
                entity_found = True

            for match in _iter_literal_matches(text, ent.get("ticker", ""), word_boundary=True):
                hits.append(
                    LexiconHit(
                        rule="restricted_list",
                        matched_text=match.group(),
                        severity="high",
                        detail=f"entity={ent['name']} ticker={ent['ticker']}",
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
                entity_found = True

            for match in _iter_literal_matches(text, ent.get("isin", ""), word_boundary=True):
                hits.append(
                    LexiconHit(
                        rule="restricted_list",
                        matched_text=match.group(),
                        severity="high",
                        detail=f"entity={ent['name']} ticker={ent['ticker']}",
                        start_char=match.start(),
                        end_char=match.end(),
                    )
                )
                entity_found = True

            if entity_found:
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
                sent_text = text[sent.start_char:sent.end_char]
                hits.append(LexiconHit(
                    rule="ner_event_entity_correlation",
                    matched_text=sent_text,
                    severity="high",
                    detail=f"events={found_events} entities=[{entities_str}]",
                    start_char=sent.start_char,
                    end_char=sent.end_char,
                ))
                
            # Info: Organization + Money mentioned together
            if orgs and money:
                org_str = ", ".join([e.text for e in orgs])
                money_str = ", ".join([e.text for e in money])
                sent_text = text[sent.start_char:sent.end_char]
                hits.append(LexiconHit(
                    rule="ner_org_money_correlation",
                    matched_text=sent_text,
                    severity="info",
                    detail=f"orgs=[{org_str}] money=[{money_str}]",
                    start_char=sent.start_char,
                    end_char=sent.end_char,
                ))

        # Basic entity logging
        for ent in doc.ents:
            if ent.label_ in ("MONEY", "ORG", "PERSON", "GPE", "LAW"):
                hits.append(
                    LexiconHit(
                        rule=f"ner_{ent.label_.lower()}",
                        matched_text=ent.text,
                        severity="info",
                        detail=f"spaCy label={ent.label_}",
                        start_char=ent.start_char,
                        end_char=ent.end_char,
                    )
                )
        return hits
    def _check_presidio(self, text: str) -> list:
        hits = []
        results = self.analyzer.analyze(text=text, language="en", entities=["CREDIT_CARD", "IBAN_CODE", "FINANCIAL_ID", "PHONE_NUMBER", "EMAIL_ADDRESS"])
        for r in results:
            hits.append(
                LexiconHit(
                    rule=f"presidio_{r.entity_type.lower()}",
                    matched_text=text[r.start:r.end],
                    severity="high" if r.score >= 0.7 else "info",
                    detail=f"score={r.score:.2f}",
                    start_char=r.start,
                    end_char=r.end,
                )
            )
        return hits
    def run(self, text: str) -> LexiconResult:
        result = LexiconResult()
        result.score_threshold = resolve_score_threshold(text)
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
        result.score_threshold_exceeded = result.total_score >= result.score_threshold
        result.flagged = len(high_hits) > 0 or result.score_threshold_exceeded

        # Deterministic short-circuit triggers align with documented policy.
        has_money_breach = any(h.rule == "money_threshold" and h.severity == "high" for h in high_hits)
        has_restricted_match = len(result.restricted_entities_found) > 0
        result.high_risk_short_circuit = has_restricted_match or has_money_breach
        return result
