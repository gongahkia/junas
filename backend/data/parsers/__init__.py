"""Dataset parsers."""

from data.parsers.conll_parser import LABEL_LIST, build_dataset, parse_conll_file
from data.parsers.contract_segmenter import segment_contract, split_sentences
from data.parsers.glossary_parser import GlossaryEntry, parse_glossary_file
from data.parsers.lecard_parser import (
    build_corpus as build_lecard_corpus,
    discover_lecard_data_root,
    load_labels as load_lecard_labels,
    load_queries as load_lecard_queries,
)
from data.parsers.statute_parser import StatuteSection, parse_ors_line

__all__ = [
    "LABEL_LIST",
    "build_dataset",
    "parse_conll_file",
    "segment_contract",
    "split_sentences",
    "build_lecard_corpus",
    "discover_lecard_data_root",
    "load_lecard_labels",
    "load_lecard_queries",
    "GlossaryEntry",
    "parse_glossary_file",
    "StatuteSection",
    "parse_ors_line",
]
