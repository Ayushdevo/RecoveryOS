import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.services.policy import PolicyEngine


class Regression(unittest.TestCase):
    def test_invalid_transaction_amount(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        tx = SimpleNamespace(id="t", customer_id="c", amount=100., retry_count=0)
        cust = SimpleNamespace(id="c")
        for amount in [0., -1., float("nan"), float("inf")]:
            tx.amount = amount
            with self.subTest(amount=amount):
                self.assertEqual(PolicyEngine().evaluate_intervention(db, tx, cust, "retry", .8, 80.)[0], "rejected")
