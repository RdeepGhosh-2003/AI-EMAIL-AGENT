import unittest
from pathlib import Path
import create_share_package


class SharePackageTests(unittest.TestCase):
    def test_private_and_runtime_files_are_excluded(self):
        for name in (".env","outlook/token_cache.json","data/drafts.json",".venv/pyvenv.cfg"):
            self.assertFalse(create_share_package.should_include(create_share_package.ROOT / Path(name)),name)

    def test_outlook_app_files_are_included(self):
        for name in ("AI_Email_Agent_Setup_Guide.docx","Open_Dashboard.vbs","requirements.txt","outlook/auth.py","openrouter_client.py"):
            self.assertTrue(create_share_package.should_include(create_share_package.ROOT / name),name)


if __name__ == "__main__":
    unittest.main()
