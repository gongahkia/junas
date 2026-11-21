"""Versioned annotation-agreement measurements; legacy regression math lives elsewhere."""

from __future__ import annotations

import hashlib
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.candidate_review import assess_annotation_provenance

Unit = tuple[str, str, str]  # split, document, annotator
COVERAGE = frozenset({'unknown', 'partial', 'exhaustive'})


@dataclass(frozen=True, order=True)
class Span:
    unit: Unit
    start: int
    end: int
    category: str
    label: str


def _assignment(gold: list[Span], predictions: list[Span], mode: str) -> dict[int, int]:
    groups: dict[tuple, list[int]] = defaultdict(list)
    for index, g in enumerate(gold):
        groups[(g.unit, g.category, g.label)].append(index)
    edges = []
    for p in predictions:
        edges.append([i for i in groups[(p.unit, p.category, p.label)] if (
            (p.start == gold[i].start and p.end == gold[i].end) if mode == 'exact'
            else p.start < gold[i].end and gold[i].start < p.end
        )])
    owners: dict[int, int] = {}
    matches: dict[int, int] = {}
    # iterative augmenting paths yield maximum cardinality without recursion;
    # canonical input order makes ambiguous assignments reproducible too.
    for root in range(len(predictions)):
        queue = deque([root])
        seen = {root}
        parent: dict[int, int] = {}
        free = None
        while queue and free is None:
            p = queue.popleft()
            for g in edges[p]:
                if g in parent:
                    continue
                parent[g] = p
                if g not in owners:
                    free = g
                    break
                owner = owners[g]
                if owner not in seen:
                    seen.add(owner)
                    queue.append(owner)
        while free is not None:
            p = parent[free]
            previous = matches.get(p)
            matches[p] = free
            owners[free] = p
            free = previous
    return matches


def occurrence_scores(
    gold: Iterable[Span], predictions: Iterable[Span], *, texts: Mapping[Unit, str],
    coverage: Mapping[Unit, str], categories: set[str] | None = None,
) -> dict[str, Any]:
    if set(coverage) - set(texts) or any(c not in COVERAGE for c in coverage.values()):
        raise ValueError('invalid annotation coverage declaration')
    g, p = list(gold), list(predictions)
    for unit, text in texts.items():
        if not isinstance(unit, tuple) or len(unit) != 3 or any(not isinstance(x, str) or not x for x in unit):
            raise ValueError('unit must identify split, document and annotator')
        if not isinstance(text, str):
            raise ValueError('source text must be a string')
    for s in g + p:
        if s.unit not in texts or type(s.start) is not int or type(s.end) is not int:
            raise ValueError('span requires a known unit and integer offsets')
        if not 0 <= s.start < s.end <= len(texts[s.unit]) or not s.category or not s.label:
            raise ValueError('invalid span bounds, category or label')
    if len(set(g)) != len(g):
        raise ValueError('duplicate gold annotation within the same unit/category/label')
    g = sorted(s for s in g if categories is None or s.category in categories)
    p = sorted(s for s in p if categories is None or s.category in categories)
    if not texts:
        return {'schema_version': 'junas.occurrence.v1', 'status': 'unavailable', 'reason': 'no evaluation units'}
    exhaustive = all(coverage.get(u, 'unknown') == 'exhaustive' for u in texts)
    output: dict[str, Any] = {'schema_version': 'junas.occurrence.v1', 'status': 'available',
        'unit': 'split/document/annotator observations; half-open character offsets',
        'matching': 'maximum-cardinality one-to-one, equal category and label; canonical tie order',
        'coverage': dict(sorted(Counter(coverage.get(u,'unknown') for u in texts).items()))}
    for mode in ('exact', 'overlap'):
        matches = _assignment(g, p, mode)
        tp = len(matches)
        precision = tp / len(p) if p and exhaustive else None
        recall = tp / len(g) if g else None
        f2 = None
        if precision is not None and recall is not None:
            f2 = 5 * precision * recall / (4 * precision + recall) if precision or recall else 0.0
        matched_g = set(matches.values())
        output[mode] = {'gold':len(g), 'predictions':len(p), 'matched':tp,
            'false_negatives':len(g)-tp, 'unmatched_predictions':len(p)-tp,
            'false_positives':len(p)-tp if exhaustive else None,
            'precision_if_exhaustive':precision, 'labeled_span_recall':recall, 'f2_if_exhaustive':f2,
            'precision_note':'conditional on caller-declared exhaustive target annotation; otherwise unavailable',
            'matched_gold':[{'unit':list(s.unit),'start':s.start,'end':s.end,'category':s.category,'label':s.label}
                            for i,s in enumerate(g) if i in matched_g]}
    return output


def input_identity(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def reproducibility(runner: Path) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    paths = sorted(list((root/'src/junas').rglob('*.py')) + list((root/'src/junas').rglob('*.toml'))
                   + list((root/'src/junas').rglob('*.csv')))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes() + b'\0')
    return {'python':sys.version.split()[0], 'classifier_sha256':digest.hexdigest(),
            'evaluator_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (runner, Path(__file__), root/'scripts/candidate_review.py')}}


def internal_annotation_audit(labels: dict[str, Any]) -> dict[str, Any]:
    sections = {}
    for section in ('must_detect','ideal_must_detect','must_not_detect','uncertain'):
        items = labels.get(section, [])
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ValueError(f'{section} must be an array of annotation objects')
        categories: Counter[str] = Counter()
        independence: Counter[str] = Counter()
        offsets = 0
        for item in items:
            assessment = assess_annotation_provenance(labels,item)
            categories.update(assessment['categories'])
            independence.update([assessment['independence_status']])
            offsets += type(item.get('start_char')) is int and type(item.get('end_char')) is int
        sections[section] = {'labels':len(items), 'items_with_offset_fields':offsets,
                             'provenance_categories':dict(sorted(categories.items())),
                             'independence_status':dict(sorted(independence.items()))}
    return {'schema_version':'junas.internal_annotation_audit.v1', 'sections':sections,
        'annotation_coverage':labels.get('_annotation_coverage','unknown'),
        'split':labels.get('_split','unspecified'),
        'occurrence_metrics':{'status':'unavailable','reason':
            'Legacy internal rule/text labels lack a qualified occurrence annotation protocol; offsets are never inferred.'},
        'independently_established_accuracy':{'status':'unavailable','reason':
            'Owner approval and absence of detector-marker phrases do not establish independent blind annotation.'},
        'document_classification_accuracy':{'status':'unavailable','reason':
            'No qualified adjudicated document-risk ground truth is supplied by this evaluation path.'}}


def aggregate_internal_audits(audits: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items=list(audits)
    totals: dict[str, Any] = {}
    for section in ('must_detect','ideal_must_detect','must_not_detect','uncertain'):
        rows=[a['sections'][section] for a in items]
        cats: Counter[str]=Counter(); independence: Counter[str]=Counter()
        for row in rows:
            cats.update(row['provenance_categories']); independence.update(row['independence_status'])
        totals[section]={'labels':sum(r['labels'] for r in rows),
                         'items_with_offset_fields':sum(r['items_with_offset_fields'] for r in rows),
                         'provenance_categories':dict(sorted(cats.items())),
                         'independence_status':dict(sorted(independence.items()))}
    return {'schema_version':'junas.internal_annotation_audit.v1','documents':len(items),'sections':totals,
            'splits':dict(sorted(Counter(str(a['split']) for a in items).items())),
            'occurrence_metrics':{'status':'unavailable','reason':'No qualified occurrence-level internal ground truth.'},
            'independently_established_accuracy':{'status':'unavailable','reason':'Independent blind annotation not established.'}}
