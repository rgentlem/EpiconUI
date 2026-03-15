import unittest

from nhanes_agent.app.services.nhanes.validator import validate_cycles, validate_variables


class StubRepository:
    def validate_cycle(self, cycle: str) -> bool:
        return cycle == "2001-2002"

    def validate_variable(self, candidate: str, cycle: str | None = None, component: str | None = None):
        if candidate != "RIDAGEYR":
            return []

        class Candidate:
            variable_name = "RIDAGEYR"
            canonical_label = "Age in years at screening"
            table_name = "DEMO_B"
            component = "Demographics"
            cycle = "2001-2002"

        return [Candidate()]


class ValidationTests(unittest.TestCase):
    def test_exact_cycle_validation(self) -> None:
        rows = validate_cycles(
            [{"raw_mention": "2001-2002", "canonical_cycles": ["2001-2002"], "confidence": 0.9}],
            StubRepository(),
        )
        self.assertEqual(rows[0]["validation_status"], "validated")

    def test_exact_variable_validation(self) -> None:
        rows = validate_variables(
            [{"raw_mention": "RIDAGEYR", "candidate": "RIDAGEYR", "confidence": 0.95, "match_source": "exact_code"}],
            "2001-2002",
            "Demographics",
            StubRepository(),
            threshold=0.75,
        )
        self.assertEqual(rows[0]["canonical_variable_name"], "RIDAGEYR")
        self.assertEqual(rows[0]["validation_status"], "validated")

    def test_variable_threshold_behavior(self) -> None:
        rows = validate_variables(
            [{"raw_mention": "RIDAGEYR", "candidate": "RIDAGEYR", "confidence": 0.5, "match_source": "alias"}],
            "2001-2002",
            "Demographics",
            StubRepository(),
            threshold=0.75,
        )
        self.assertEqual(rows[0]["validation_status"], "ambiguous")


if __name__ == "__main__":
    unittest.main()
