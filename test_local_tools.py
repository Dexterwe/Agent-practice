"""Boundary and integration checks using temporary projects, not business code."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from local_tools import ProjectTools


class LocalToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "login.py").write_text(
            "def login():\n    return 'a+b'\n# login again\n", encoding="utf-8"
        )
        for directory in ["node_modules", ".git", ".venv"]:
            folder = self.root / directory
            folder.mkdir()
            (folder / "hidden.txt").write_text("login SECRET", encoding="utf-8")
        (self.root / ".env").write_text("login SECRET", encoding="utf-8")
        (self.root / ".env.local").write_text("login SECRET", encoding="utf-8")
        (self.root / "apikeys.js").write_text("login SECRET", encoding="utf-8")
        (self.base / "outside.txt").write_text("login OUTSIDE", encoding="utf-8")
        (self.root / "outside-link.txt").symlink_to(self.base / "outside.txt")
        self.tools = ProjectTools(str(self.root))

    def tearDown(self):
        self.temporary.cleanup()

    def test_listing_excludes_private_files_and_external_symlinks(self):
        result = self.tools.execute("list_files", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["entries"], [{"path": "src", "type": "directory"}])

    def test_escape_and_excluded_paths_are_rejected(self):
        paths = ["../outside.txt", "outside-link.txt", ".env", ".env.local", "apikeys.js",
                 "node_modules/hidden.txt", str(self.base / "outside.txt")]
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(self.tools.execute("read_file", {"path": path})["ok"])

    def test_line_range_and_error_results(self):
        result = self.tools.execute("read_file", {"path": "src/login.py", "start_line": 2, "end_line": 2})
        self.assertEqual(result["data"]["content"], "2:     return 'a+b'")
        self.assertEqual(result["data"]["total_lines"], 3)
        for arguments in [
            {"path": "missing.py"}, {"path": "src"},
            {"path": "src/login.py", "start_line": 0},
            {"path": "src/login.py", "end_line": 201},
            {"path": "src/login.py", "start_line": True},
            {"path": "src/login.py", "start_line": 5},
        ]:
            self.assertFalse(self.tools.execute("read_file", arguments)["ok"])

    def test_binary_and_oversized_files_are_rejected(self):
        (self.root / "binary.bin").write_bytes(b"\xff\x00")
        (self.root / "large.txt").write_bytes(b"x" * (1024 * 1024 + 1))
        for filename in ["binary.bin", "large.txt"]:
            self.assertFalse(self.tools.execute("read_file", {"path": filename})["ok"])

    @unittest.skipUnless(shutil.which("rg"), "ripgrep is required for search integration")
    def test_search_is_literal_and_excludes_private_paths(self):
        result = self.tools.execute("search_code", {"keyword": "login"})
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(result["data"]["matches"]), 2)
        self.assertEqual({item["path"] for item in result["data"]["matches"]}, {"src/login.py"})
        literal = self.tools.execute("search_code", {"keyword": "a+b"})
        self.assertEqual(len(literal["data"]["matches"]), 1)
        empty = self.tools.execute("search_code", {"keyword": "no_such_word"})
        self.assertTrue(empty["ok"])
        self.assertEqual(empty["data"]["matches"], [])

    @unittest.skipUnless(shutil.which("rg"), "ripgrep is required for search integration")
    def test_search_result_budget(self):
        result = self.tools.execute("search_code", {"keyword": "login", "max_results": 1})
        self.assertEqual(len(result["data"]["matches"]), 1)
        self.assertTrue(result["data"]["truncated"])

    def test_unknown_tool_and_invalid_parameters(self):
        self.assertFalse(self.tools.execute("delete_file", {})["ok"])
        self.assertFalse(self.tools.execute("read_file", {"unknown": "value"})["ok"])
        self.assertFalse(self.tools.execute("list_files", [])["ok"])

    def test_cli_returns_failure_for_a_file_used_as_project_root(self):
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("demo.py")),
             str(self.base / "outside.txt"), "list_files"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn('"ok": false', completed.stdout)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
