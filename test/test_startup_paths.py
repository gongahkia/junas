import asyncio
import os
import unittest
from unittest.mock import patch

import backend.main as main


class StartupPathTests(unittest.TestCase):
    def tearDown(self):
        main._state.clear()

    def test_degraded_startup_allows_missing_required_layer_when_strict_mode_disabled(self):
        async def scenario():
            with (
                patch.object(main, "configure_determinism", return_value={"seed": 7}),
                patch.object(main, "load_config", return_value=["model1"]),
                patch.object(main, "get_optional_layers", return_value=set()),
                patch.object(main, "has_model_weights", return_value=False),
                patch.dict(
                    os.environ,
                    {"NOUPE_FAIL_ON_LAYER_LOAD_ERROR": "0", "NOUPE_LAZY_LOAD_HEAVY": "0"},
                    clear=False,
                ),
            ):
                async with main.lifespan(main.app):
                    ready_state = main.build_ready_snapshot()
                    self.assertFalse(ready_state["ready"])
                    self.assertEqual(ready_state["missing_layers"], ["model1"])
                    latest_error = main._get_latest_load_error("model1")
                    self.assertIsNotNone(latest_error)
                    self.assertEqual(latest_error["phase"], "startup")
                    self.assertIn("model1", main._state["missing_required_layers"])

            self.assertEqual(main._state, {})

        asyncio.run(scenario())

    def test_strict_startup_raises_when_required_layer_artifact_is_missing(self):
        async def scenario():
            with (
                patch.object(main, "configure_determinism", return_value={"seed": 7}),
                patch.object(main, "load_config", return_value=["model1"]),
                patch.object(main, "get_optional_layers", return_value=set()),
                patch.object(main, "has_model_weights", return_value=False),
                patch.dict(
                    os.environ,
                    {"NOUPE_FAIL_ON_LAYER_LOAD_ERROR": "1", "NOUPE_LAZY_LOAD_HEAVY": "0"},
                    clear=False,
                ),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    async with main.lifespan(main.app):
                        pass

            self.assertIn("required layers failed to load", str(ctx.exception))

        asyncio.run(scenario())

    def test_optional_layer_startup_failure_does_not_block_readiness(self):
        async def scenario():
            with (
                patch.object(main, "configure_determinism", return_value={"seed": 7}),
                patch.object(main, "load_config", return_value=["mosaic"]),
                patch.object(main, "get_optional_layers", return_value={"mosaic"}),
                patch.object(main, "load_module_from_path", side_effect=FileNotFoundError("redis module missing")),
                patch.dict(
                    os.environ,
                    {"NOUPE_FAIL_ON_LAYER_LOAD_ERROR": "1", "NOUPE_LAZY_LOAD_HEAVY": "0"},
                    clear=False,
                ),
            ):
                async with main.lifespan(main.app):
                    ready_state = main.build_ready_snapshot()
                    self.assertTrue(ready_state["ready"])
                    self.assertEqual(ready_state["missing_layers"], [])
                    dependency_status = main.get_dependency_status()
                    self.assertEqual(dependency_status["redis"].status, "unknown")
                    self.assertIsNone(dependency_status["redis"].healthy)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
