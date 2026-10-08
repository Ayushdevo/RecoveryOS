import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from ml.inference.predictor import RecoveryPredictor


class Regression(unittest.TestCase):
    def test_invalid_expected_value_amount(self):
        predictor = RecoveryPredictor.__new__(RecoveryPredictor)
        for amount in [0., -1., float("nan"), float("inf")]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                predictor.calculate_expected_values({"retry": .8}, amount)
        self.assertEqual(predictor.calculate_expected_values({"retry": .8}, 100.)["retry"], (75., .8))
