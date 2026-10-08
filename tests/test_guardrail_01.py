import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.services.policy import PolicyEngine
from apps.backend.routers.dashboard import PolicyConfigUpdate


class Regression(unittest.TestCase):
    def test_retry_limits(self):
        for value in [-1, 1.5, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                PolicyEngine(max_retries=value)
        self.assertEqual(PolicyEngine(max_retries=0).max_retries, 0)
    def test_dashboard_config_contract(self):
        for value in [-1, 1.5, True]:
            data = dict(max_retries=2, high_amount_threshold=50000., min_probability=.3)
            data["max_retries"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PolicyConfigUpdate(**data)
