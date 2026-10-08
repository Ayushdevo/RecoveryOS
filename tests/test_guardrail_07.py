import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.services.policy import PolicyEngine


class Regression(unittest.TestCase):
    def test_invalid_prediction(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        tx = SimpleNamespace(id="t", customer_id="c", amount=100., retry_count=0)
        cust = SimpleNamespace(id="c")
        for value in [-.1, 1.1, float("nan"), float("inf")]:
            with self.subTest(value=value):
                self.assertEqual(PolicyEngine().evaluate_intervention(db, tx, cust, "retry", value, 80.)[0], "rejected")
