import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.services.policy import PolicyEngine
from apps.backend.routers.dashboard import PolicyConfigUpdate


class Regression(unittest.TestCase):
    def test_amount_thresholds(self):
        for value in [0., -1., float("nan"), float("inf")]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                PolicyEngine(high_amount_threshold=value)
        self.assertEqual(PolicyEngine(high_amount_threshold=1.).high_amount_threshold, 1.)
    def test_dashboard_config_contract(self):
        for value in [0., -1., float("nan"), float("inf")]:
            data = dict(max_retries=2, high_amount_threshold=50000., min_probability=.3)
            data["high_amount_threshold"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PolicyConfigUpdate(**data)
