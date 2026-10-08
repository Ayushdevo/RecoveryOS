import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from ml.inference.predictor import RecoveryPredictor


class Regression(unittest.TestCase):
    def test_reversed_class_order(self):
        predictor = RecoveryPredictor.__new__(RecoveryPredictor)
        predictor.pipeline = MagicMock()
        predictor.pipeline.classes_ = np.array([1, 0])
        predictor.pipeline.predict_proba.return_value = np.array([[.8, .2]])
        np.testing.assert_array_equal(predictor.predict_probs(pd.DataFrame()), [.8])
        predictor.pipeline.classes_ = np.array([0])
        with self.assertRaises(ValueError):
            predictor.predict_probs(pd.DataFrame())
