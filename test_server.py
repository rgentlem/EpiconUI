import json
import tempfile
import unittest
from pathlib import Path

from server import parse_multipart_form_data, project_payload


class ServerTests(unittest.TestCase):
    def test_project_payload_returns_empty_paper_list_for_new_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = project_payload("Backend Demo", base_dir=tmp_dir)
            self.assertEqual(payload["project"]["project_slug"], "backend-demo")
            self.assertEqual(payload["papers"], [])
            self.assertTrue(Path(payload["project"]["root_dir"]).exists())
            json.dumps(payload)

    def test_parse_multipart_form_data_extracts_text_and_file(self) -> None:
        boundary = "----Boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="project_name"\r\n\r\n'
            "Demo Project\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="paper.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + b"%PDF-1.4\r\n" + f"\r\n--{boundary}--\r\n".encode("utf-8")

        fields = parse_multipart_form_data(f"multipart/form-data; boundary={boundary}", body)

        self.assertEqual(fields["project_name"][0]["value"], "Demo Project")
        self.assertEqual(fields["file"][0]["filename"], "paper.pdf")
        self.assertEqual(fields["file"][0]["content"], b"%PDF-1.4\r\n")


if __name__ == "__main__":
    unittest.main()
