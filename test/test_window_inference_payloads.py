import importlib.util
import unittest
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parent.parent


def load_module(module_name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBatch(dict):
    def pop(self, key, default=None):
        return super().pop(key, default)


class FakeTokenizer:
    def __call__(self, text, **kwargs):
        del text
        del kwargs
        return FakeBatch(
            {
                "input_ids": torch.tensor([[101, 102], [101, 103]]),
                "attention_mask": torch.tensor([[1, 1], [1, 1]]),
                "offset_mapping": torch.tensor(
                    [
                        [[0, 5], [6, 10]],
                        [[11, 15], [16, 21]],
                    ]
                ),
                "overflow_to_sample_mapping": torch.tensor([0, 0]),
            }
        )


class FakeModelOutput:
    def __init__(self):
        self.logits = torch.tensor([[0.1, 0.9], [0.8, 0.2]])


class FakeModel:
    def __init__(self):
        self.last_kwargs = None

    def to(self, device):
        del device
        return self

    def eval(self):
        return self

    def __call__(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeModelOutput()


class WindowInferencePayloadTests(unittest.TestCase):
    def _run_prediction_and_assert(self, module_name: str, relative_path: str, classifier_name: str):
        module = load_module(module_name, relative_path)
        fake_model = FakeModel()
        original_has_model_weights = module._has_model_weights
        original_tokenizer_loader = module.AutoTokenizer.from_pretrained
        original_model_loader = module.AutoModelForSequenceClassification.from_pretrained

        try:
            module._has_model_weights = lambda checkpoint_dir: True
            module.AutoTokenizer.from_pretrained = lambda *args, **kwargs: FakeTokenizer()
            module.AutoModelForSequenceClassification.from_pretrained = lambda *args, **kwargs: fake_model

            classifier = getattr(module, classifier_name)()
            classifier.predict("alpha beta gamma delta")

            self.assertIsNotNone(fake_model.last_kwargs)
            self.assertNotIn("overflow_to_sample_mapping", fake_model.last_kwargs)
            self.assertIn("input_ids", fake_model.last_kwargs)
            self.assertIn("attention_mask", fake_model.last_kwargs)
        finally:
            module._has_model_weights = original_has_model_weights
            module.AutoTokenizer.from_pretrained = original_tokenizer_loader
            module.AutoModelForSequenceClassification.from_pretrained = original_model_loader

    def test_model1_strips_overflow_mapping_before_forward(self):
        self._run_prediction_and_assert(
            "test_model1_inference",
            "layer4-classification/model-1/inference.py",
            "FinBERTClassifier",
        )

    def test_model2_strips_overflow_mapping_before_forward(self):
        self._run_prediction_and_assert(
            "test_model2_inference",
            "layer4-classification/model-2/inference.py",
            "BERTSeverityClassifier",
        )


class SlidingWindowAggregationTests(unittest.TestCase):
    def test_model1_predict_uses_highest_risk_window(self):
        module = load_module("test_model1_windows", "layer4-classification/model-1/inference.py")
        classifier = module.FinBERTClassifier.__new__(module.FinBERTClassifier)
        classifier._predict_windows = lambda text: (
            [0.12, 0.91, 0.63],
            [
                {
                    "start_char": 0,
                    "end_char": 18,
                    "text": text[0:18],
                    "risk_score": 0.12,
                    "window_index": 0,
                    "token_count": 4,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
                {
                    "start_char": 20,
                    "end_char": 52,
                    "text": text[20:52],
                    "risk_score": 0.91,
                    "window_index": 1,
                    "token_count": 8,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
                {
                    "start_char": 44,
                    "end_char": 73,
                    "text": text[44:73],
                    "risk_score": 0.63,
                    "window_index": 2,
                    "token_count": 7,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
            ],
        )

        text = "public intro boundary confidential window with merger plan and public outro"
        result = classifier.predict(text)

        self.assertEqual(result.label, "risk")
        self.assertEqual(result.risk_score, 0.91)
        self.assertEqual(result.window_count, 3)
        self.assertEqual(result.top_window["window_index"], 1)
        self.assertEqual(result.top_window["start_char"], 20)
        self.assertEqual(result.top_window["end_char"], 52)

    def test_model2_predict_uses_highest_high_risk_window(self):
        module = load_module("test_model2_windows", "layer4-classification/model-2/inference.py")
        classifier = module.BERTSeverityClassifier.__new__(module.BERTSeverityClassifier)
        classifier._predict_windows = lambda text: (
            [0.32, 0.48, 0.84],
            [
                {
                    "start_char": 0,
                    "end_char": 15,
                    "text": text[0:15],
                    "high_risk_score": 0.32,
                    "window_index": 0,
                    "token_count": 3,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
                {
                    "start_char": 14,
                    "end_char": 39,
                    "text": text[14:39],
                    "high_risk_score": 0.48,
                    "window_index": 1,
                    "token_count": 5,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
                {
                    "start_char": 38,
                    "end_char": 67,
                    "text": text[38:67],
                    "high_risk_score": 0.84,
                    "window_index": 2,
                    "token_count": 6,
                    "window_stride": module.WINDOW_STRIDE,
                    "max_seq_len": module.MAX_SEQ_LEN,
                },
            ],
        )

        text = "public intro overlap window contains the sensitive merger plan for the board"
        result = classifier.predict(text)

        self.assertEqual(result.label, "high_risk")
        self.assertEqual(result.high_risk_score, 0.84)
        self.assertEqual(result.window_count, 3)
        self.assertEqual(result.top_window["window_index"], 2)
        self.assertEqual(result.top_window["start_char"], 38)
        self.assertEqual(result.top_window["end_char"], 67)

    def test_window_bounds_ignore_padding_and_keep_last_real_offset(self):
        model1_module = load_module("test_model1_bounds", "layer4-classification/model-1/inference.py")
        model2_module = load_module("test_model2_bounds", "layer4-classification/model-2/inference.py")
        offsets = [[0, 0], [11, 19], [20, 27], [0, 0], [28, 33], [0, 0]]

        self.assertEqual(model1_module._window_bounds(offsets), (11, 33))
        self.assertEqual(model2_module._window_bounds(offsets), (11, 33))
        self.assertEqual(model1_module._count_window_tokens(offsets), 3)
        self.assertEqual(model2_module._count_window_tokens(offsets), 3)


if __name__ == "__main__":
    unittest.main()
