import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.schemas.payments import InterventionRequest


class Regression(unittest.TestCase):
    def test_intervention_contract(self):
        cases = [dict(action_type="refund"), dict(attempt=0), dict(attempt=True), dict(idempotency_key=" "), dict(idempotency_key="x" * 257)]
        for changes in cases:
            data = dict(action_type="retry", attempt=1, idempotency_key="recovery:t:retry:1")
            data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                InterventionRequest(**data)
        self.assertEqual(InterventionRequest(action_type="link", attempt=1, idempotency_key="k").action_type, "link")
