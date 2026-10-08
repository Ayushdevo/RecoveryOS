import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from ml.inference.predictor import RecoveryPredictor


class Regression(unittest.TestCase):
    def test_unknown_intervention_cost(self):
        predictor = RecoveryPredictor.__new__(RecoveryPredictor)
        with self.assertRaises(ValueError):
            predictor.calculate_expected_values({"refund": .8}, 100.)
        self.assertIn("none", predictor.calculate_expected_values({"none": .8}, 100.))
