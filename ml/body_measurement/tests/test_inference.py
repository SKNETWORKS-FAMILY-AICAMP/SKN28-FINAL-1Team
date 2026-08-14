from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from body_measurement.src import inference


class BasicInferenceModelCompositionTests(unittest.TestCase):
    def test_exact_length_model_overrides_legacy_proxy_lengths(self) -> None:
        legacy = Mock()
        legacy.predict.return_value = [[
            85.0, 70.0, 95.0, 55.0, 35.0, 28.0, 37.0,
            30.0, 42.0, 45.0, 69.0, 9.0,
        ]]
        exact = Mock()
        exact.predict.return_value = [[31.0, 36.0, 44.0, 80.0, 6.5]]
        circumference = Mock()
        circumference.predict.return_value = [[54.0, 34.0, 27.0]]

        with (
            patch.object(inference, "load_model", return_value=legacy),
            patch.object(inference, "load_exact_length_model", return_value=exact),
            patch.object(inference, "load_circumference_model", return_value=circumference),
        ):
            result = inference.estimate_from_basic("female", 165, 55)

        self.assertEqual(result["leg_length"], 80.0)
        self.assertEqual(result["torso_leg_ratio"], 0.55)
        self.assertEqual(result["thigh_calf_ratio"], 0.861)
        self.assertEqual(result["chest"], 85.0)
        self.assertEqual(result["thigh"], 54.0)


if __name__ == "__main__":
    unittest.main()
