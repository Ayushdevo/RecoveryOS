import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.agents.verifier import fallback_verify


class Regression(unittest.TestCase):
    def test_invalid_settlement(self):
        for amount in [None, "invalid", 0., -1., float("nan"), float("inf")]:
            with self.subTest(amount=amount):
                result = fallback_verify({"status":"captured", "amount":amount})
                self.assertFalse(result.is_settled)
                self.assertEqual(result.recovered_amount, 0.)
        self.assertTrue(fallback_verify({"status":"captured", "amount":"100"}).is_settled)
        self.assertFalse(fallback_verify({"status":"notified", "amount":100.}).is_settled)
