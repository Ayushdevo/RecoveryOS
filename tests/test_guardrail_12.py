import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.schemas.payments import PaymentCreate


class Regression(unittest.TestCase):
    def test_payment_amount_contract(self):
        for amount in [0., -1., float("nan"), float("inf")]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                PaymentCreate(amount=amount, payment_method="card", merchant_category="SaaS", customer_id="c")
        self.assertEqual(PaymentCreate(amount=1., payment_method="card", merchant_category="SaaS", customer_id="c").amount, 1.)
