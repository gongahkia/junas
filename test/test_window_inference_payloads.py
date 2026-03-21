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


if __name__ == "__main__":
    unittest.main()
