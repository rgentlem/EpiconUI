import unittest

from nhanes_metadata_index import build_searchable_text, infer_cycle, plan_metadata_sync


class NhanesMetadataIndexTests(unittest.TestCase):
    def test_infer_cycle_from_table_suffix(self) -> None:
        self.assertEqual(infer_cycle("DEMO_I"), "2015-2016")
        self.assertEqual(infer_cycle("BPX_J"), "2017-2018")

    def test_build_searchable_text_contains_key_fields(self) -> None:
        text = build_searchable_text(
            {
                "variable_name": "RIDAGEYR",
                "table_name": "DEMO_I",
                "canonical_label": "Age in years at screening",
                "component": "Demographics",
                "cycle": "2015-2016",
            }
        )
        self.assertIn("Variable=RIDAGEYR", text)
        self.assertIn("Table=DEMO_I", text)
        self.assertIn("Cycle=2015-2016", text)

    def test_plan_metadata_sync_separates_unchanged_changed_and_stale(self) -> None:
        source_rows = [
            {
                "variable_name": "RIDAGEYR",
                "table_name": "DEMO_I",
                "canonical_label": "Age in years at screening",
                "component": "Demographics",
                "cycle": "2015-2016",
                "searchable_text": "same",
            },
            {
                "variable_name": "LBXBCD",
                "table_name": "LAB_I",
                "canonical_label": "Cobalt",
                "component": "Laboratory",
                "cycle": "2015-2016",
                "searchable_text": "new-value",
            },
        ]
        existing_rows = {
            ("RIDAGEYR", "DEMO_I"): {
                "variable_name": "RIDAGEYR",
                "table_name": "DEMO_I",
                "canonical_label": "Age in years at screening",
                "component": "Demographics",
                "cycle": "2015-2016",
                "searchable_text": "same",
            },
            ("LBXBCD", "LAB_I"): {
                "variable_name": "LBXBCD",
                "table_name": "LAB_I",
                "canonical_label": "Cobalt",
                "component": "Laboratory",
                "cycle": "2015-2016",
                "searchable_text": "old-value",
            },
            ("OLDVAR", "OLD_I"): {
                "variable_name": "OLDVAR",
                "table_name": "OLD_I",
                "canonical_label": "Old",
                "component": "Old",
                "cycle": "2015-2016",
                "searchable_text": "stale",
            },
        }

        unchanged, to_embed, stale = plan_metadata_sync(source_rows, existing_rows)

        self.assertEqual(len(unchanged), 1)
        self.assertEqual(unchanged[0]["variable_name"], "RIDAGEYR")
        self.assertEqual(len(to_embed), 1)
        self.assertEqual(to_embed[0]["variable_name"], "LBXBCD")
        self.assertEqual(stale, [("OLDVAR", "OLD_I")])


if __name__ == "__main__":
    unittest.main()
