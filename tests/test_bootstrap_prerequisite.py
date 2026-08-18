import io
import unittest
from unittest import mock

from bootstrap import bootstrap_entry
from pipeline.env_manager import CondaPrerequisiteError


class BootstrapPrerequisiteTests(unittest.TestCase):
    def test_missing_conda_is_reported_without_traceback_contract(self):
        stream = io.StringIO()
        with mock.patch("bootstrap.bootstrap_core", side_effect=CondaPrerequisiteError("Conda missing; run conda --version then python Videoto3D.py gui")):
            code = bootstrap_entry("D:/Desktop/Videoto3D", ["gui"], stream=stream)
        text = stream.getvalue()
        self.assertEqual(code, 2)
        self.assertIn("[PREREQ][MISSING] Conda", text)
        self.assertIn("conda --version", text)
        self.assertNotIn("Traceback", text)


if __name__ == "__main__":
    unittest.main()
