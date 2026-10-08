import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.services.policy import PolicyEngine
from apps.backend.routers.dashboard import PolicyConfigUpdate


class Regression(unittest.TestCase):
    def test_probability_thresholds(self):
        for value in [-0.1, 1.1, float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                PolicyEngine(min_probability=value)
        for value in [0.,1.]:
            self.assertEqual(PolicyEngine(min_probability=value).min_probability, value)
    def test_dashboard_config_contract(self):
        for value in [-.1, 1.1, float("nan"), float("inf")]:
            data = dict(max_retries=2, high_amount_threshold=50000., min_probability=.3)
            data["min_probability"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PolicyConfigUpdate(**data)
