import json
import tempfile
import unittest
from pathlib import Path

from server import project_payload


class ServerTests(unittest.TestCase):
    def test_project_payload_returns_empty_paper_list_for_new_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = project_payload("Backend Demo", base_dir=tmp_dir)
            self.assertEqual(payload["project"]["project_slug"], "backend-demo")
            self.assertEqual(payload["papers"], [])
            self.assertTrue(Path(payload["project"]["root_dir"]).exists())
            json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
