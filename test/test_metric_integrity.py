"""Independent small examples for versioned occurrence metrics and provenance."""

from itertools import permutations

import pytest

from scripts.span_metrics import Span, occurrence_scores
from scripts.candidate_review import assess_annotation_provenance

UNIT = ('test', 'd', 'a')
TEXTS = {UNIT: 'same same more'}


def span(start, end, *, category='PII', label='token', unit=UNIT):
    return Span(unit, start, end, category, label)


def measure(gold, predictions, *, coverage='exhaustive', categories=None, texts=TEXTS):
    return occurrence_scores(gold, predictions, texts=texts, coverage={u: coverage for u in texts}, categories=categories)


def test_exact_occurrences_preserve_repetition_and_prediction_multiplicity():
    result = measure([span(0,4), span(5,9)], [span(0,4), span(0,4)])['exact']
    assert result['matched'] == 1
    assert result['false_positives'] == 1
    assert result['false_negatives'] == 1
    assert result['precision_if_exhaustive'] == 0.5
    assert result['labeled_span_recall'] == 0.5


def test_broad_prediction_receives_at_most_one_credit():
    result = measure([span(0,4), span(5,9)], [span(0,9)])
    assert result['overlap']['matched'] == 1
    assert result['overlap']['labeled_span_recall'] == 0.5
    assert result['exact']['matched'] == 0


def test_maximum_matching_is_independent_of_both_orders():
    gold = [span(0,4), span(5,9)]
    predictions = [span(0,9), span(0,4)]
    baseline = measure(gold, predictions)
    assert baseline['overlap']['matched'] == 2
    for g in permutations(gold):
        for p in permutations(predictions):
            assert measure(g,p) == baseline


def test_nested_crossing_spans_and_label_identity():
    g = [span(0,9,label='outer'), span(2,6,label='inner')]
    p = [span(1,8,label='outer'), span(3,7,label='inner'), span(0,9,label='wrong')]
    scores = measure(g,p)
    assert scores['overlap']['matched'] == 2
    assert scores['exact']['matched'] == 0


def test_category_filter_applies_to_gold_and_predictions():
    result = measure([span(0,4),span(5,9,category='MNPI')], [span(0,4),span(5,9,category='MNPI')], categories={'PII'})
    assert result['exact']['gold'] == 1
    assert result['exact']['predictions'] == 1
    assert result['exact']['precision_if_exhaustive'] == 1


@pytest.mark.parametrize('coverage', ['partial','unknown'])
def test_incomplete_annotation_does_not_manufacture_false_positives(coverage):
    score = measure([span(0,4)], [span(0,4),span(5,9)],coverage=coverage)['exact']
    assert score['matched'] == 1 and score['unmatched_predictions'] == 1
    assert score['false_positives'] is None
    assert score['precision_if_exhaustive'] is None
    assert score['f2_if_exhaustive'] is None


def test_exhaustively_annotated_negative_document_has_false_positives():
    score = measure([], [span(0,4)])['exact']
    assert score['false_positives'] == 1
    assert score['precision_if_exhaustive'] == 0
    assert score['labeled_span_recall'] is None


def test_empty_dataset_is_unavailable_not_perfect():
    assert occurrence_scores([],[],texts={},coverage={})['status'] == 'unavailable'
    score=measure([],[])['exact']
    assert score['precision_if_exhaustive'] is None and score['labeled_span_recall'] is None


def test_annotators_are_distinct_observations():
    second=('test','d','b')
    score = measure([span(0,4),span(0,4,unit=second)], [span(0,4),span(0,4,unit=second)],texts={UNIT:'same',second:'same'})['exact']
    assert score['matched'] == 2 and score['predictions'] == 2


@pytest.mark.parametrize('start,end', [(-1,3),(0,0),(0,99),(True,4),(0,4.0)])
def test_malformed_offsets_refuse(start,end):
    with pytest.raises(ValueError): measure([span(start,end)],[])


def test_duplicate_gold_observations_are_not_silently_counted_twice():
    with pytest.raises(ValueError, match='duplicate'):
        measure([span(0,4),span(0,4)],[span(0,4)])


def test_unknown_document_is_invalid():
    with pytest.raises(ValueError):measure([], [span(0,4,unit=('test','other','a'))])


def test_unknown_provenance_is_not_independence():
    result = assess_annotation_provenance({}, {'reason':'ordinary label'})
    assert result['independence_status'] == 'not_established'
    assert 'unknown_or_insufficient' in result['categories']


def test_owner_approval_does_not_establish_blind_independence():
    result = assess_annotation_provenance({'_human_review_status':'approved','_human_review':{'reviewer':'owner'}})
    assert result['independence_status'] == 'not_established'


def test_reconciliation_metadata_dominates_ordinary_item_reason():
    result = assess_annotation_provenance({'_strict_runtime_reconciliation':{'source':'detector'},'_label_model':'model','_human_review_status':'approved','_human_review':{'reviewer':'owner'}},{'reason':'normal annotation'})
    assert 'reconciled_against_detector_output' in result['categories']
    assert 'human_reviewed_model_proposals' in result['categories']
    assert result['independence_status'] == 'not_established'


def test_declared_blind_annotation_remains_a_declaration():
    result = assess_annotation_provenance({'_annotation_provenance':{'origin':'independent_human','author':'human-a','protocol_id':'blind-protocol','blinded_to_detector':True}})
    assert result['independence_status'] == 'declared_not_verified'
