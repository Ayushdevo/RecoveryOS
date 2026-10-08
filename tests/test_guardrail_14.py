import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
from pydantic import ValidationError
import numpy as np
import pandas as pd
from apps.backend.agents.planner import PlannerResult


class Regression(unittest.TestCase):
    def test_planner_action_contract(self):
        values = dict(decision="refund", confidence=.8, reason_codes=[], expected_recovery_value=10., requires_human=False, justification="example")
        with self.assertRaises(ValidationError):
            PlannerResult(**values)
        values["decision"] = "retry"
        self.assertEqual(PlannerResult(**values).decision, "retry")
        for changes in [dict(confidence=1.1), dict(confidence=float("nan")), dict(expected_recovery_value=float("inf"))]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                PlannerResult(**(values | changes))
