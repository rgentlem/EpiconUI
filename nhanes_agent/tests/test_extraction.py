import unittest

from nhanes_agent.app.services.nhanes.component_extractor import extract_component_mentions
from nhanes_agent.app.services.nhanes.cycle_extractor import extract_cycle_mentions
from nhanes_agent.app.services.nhanes.variable_extractor import extract_variable_mentions


class ExtractionTests(unittest.TestCase):
    def test_cycle_regex_catches_common_patterns(self) -> None:
        rows = extract_cycle_mentions("NHANES 2001-2002 and 2001 through 2006 were used.")
        self.assertTrue(any(item["canonical_cycles"] == ["2001-2002"] for item in rows))
        self.assertTrue(any("2001 through 2006" in item["raw_mention"] or len(item["canonical_cycles"]) > 1 for item in rows))

    def test_variable_extraction_catches_exact_codes_and_aliases(self) -> None:
        rows = extract_variable_mentions("RIDAGEYR and BMI were used.")
        self.assertTrue(any(item["candidate"] == "RIDAGEYR" for item in rows))
        self.assertTrue(any(item["candidate"] == "BMXBMI" for item in rows))

    def test_component_alias_normalization_works(self) -> None:
        rows = extract_component_mentions("The demographics and blood pressure domains were reviewed.")
        self.assertTrue(any(item["canonical_component"] == "Demographics" for item in rows))
        self.assertTrue(any(item["canonical_component"] == "Blood Pressure" for item in rows))


if __name__ == "__main__":
    unittest.main()
