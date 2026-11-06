"""用临时项目验证路径边界与工具入口，不读取业务项目。"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from errors import ToolError
from executor import exexute_tool
from paths import resolve_project_path


class ProjectPathTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "project"
        (self.root / "src").mkdir(parents=True)
        self.sample = self.root / "src" / "main.py"
        self.sample.write_text("def login():\n    return True\n# end\n", encoding="utf-8")
        self.outside = self.base / "outside.txt"
        self.outside.write_text("outside marker", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def execute(self, tool, arguments):
        return exexute_tool(str(self.root), tool, arguments)

    def test_root_relative_and_internal_absolute_paths(self):
        self.assertEqual(resolve_project_path(str(self.root)), self.root)
        self.assertEqual(resolve_project_path(str(self.root), "src/main.py"), self.sample)
        self.assertEqual(resolve_project_path(str(self.root), str(self.sample)), self.sample)

    def test_external_paths_and_similar_prefix_are_rejected(self):
        sibling = self.base / "project_backup"
        sibling.mkdir()
        other = sibling / "main.py"
        other.write_text("outside", encoding="utf-8")
        for path in ["../outside.txt", str(self.outside), str(other)]:
            with self.subTest(path=path), self.assertRaises(ToolError):
                resolve_project_path(str(self.root), path)

    def test_symlink_destinations_are_checked(self):
        (self.root / "external.py").symlink_to(self.outside)
        (self.root / "internal.py").symlink_to(self.sample)
        with self.assertRaises(ToolError):
            resolve_project_path(str(self.root), "external.py")
        self.assertEqual(resolve_project_path(str(self.root), "internal.py"), self.sample)

    def test_invalid_roots_and_paths(self):
        for root, path in [
            ("", "."), (None, "."), (str(self.outside), "."),
            (str(self.base / "missing"), "."),
            (str(self.root), ""), (str(self.root), None),
            (str(self.root), "missing.py"),
        ]:
            with self.subTest(root=root, path=path), self.assertRaises(ToolError):
                resolve_project_path(root, path)

    def test_directory_default_and_nested_directory(self):
        result = self.execute("list_files", {})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["entries"], [{"path": "src", "type": "directory"}])
        nested = self.execute("list_files", {"path": "src"})
        self.assertTrue(nested["ok"], nested)
        self.assertEqual(nested["data"]["entries"], [{"path": "main.py", "type": "file"}])

    def test_read_file_and_input_arguments_are_preserved(self):
        arguments = {"path": "src/main.py", "max_lines": 20, "start_line": 1, "end_line": 3}
        original = arguments.copy()
        result = self.execute("read_file", arguments)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["lines"], 3)
        self.assertEqual(result["data"]["total_lines"], 3)
        self.assertEqual(arguments, original)
        arguments["path"] = str(self.sample)
        self.assertTrue(self.execute("read_file", arguments)["ok"])

    @unittest.skipUnless(shutil.which("rg"), "需要 rg")
    def test_search_defaults_to_root_and_can_feed_read_file(self):
        result = self.execute("search_code", {"keyword": "login"})
        self.assertTrue(result["ok"], result)
        matches = result["data"]["results"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(Path(matches[0]["file"]), self.sample)
        read = self.execute("read_file", {
            "path": matches[0]["file"], "max_lines": 20,
            "start_line": matches[0]["line"], "end_line": matches[0]["line"],
        })
        self.assertTrue(read["ok"], read)
        self.assertEqual(read["data"]["content"], "1:def login():")

    def test_all_tools_reject_external_directory(self):
        outside_dir = self.base / "outside"
        outside_dir.mkdir()
        for tool, arguments in [
            ("list_files", {"path": "../outside"}),
            ("search_code", {"path": str(outside_dir), "keyword": "marker"}),
            ("read_file", {"path": "../outside.txt", "max_lines": 200}),
        ]:
            with self.subTest(tool=tool):
                result = self.execute(tool, arguments)
                self.assertFalse(result["ok"])
                self.assertIn("超出项目根目录", result["error"])

    def test_invalid_requests_remain_structured(self):
        for tool, arguments in [
            ("unknown", {}), ("list_files", []),
            ("read_file", {"max_lines": 200}),
            ("read_file", {"path": "src/main.py"}),
            ("read_file", {"path": "src/main.py", "max_lines": 0}),
            ("read_file", {"path": "missing.py", "max_lines": 200}),
            ("list_files", {"path": "src/main.py"}),
        ]:
            with self.subTest(tool=tool, arguments=arguments):
                result = self.execute(tool, arguments)
                self.assertFalse(result["ok"])
                self.assertIsInstance(result["error"], str)

    @unittest.skipUnless(shutil.which("rg"), "需要 rg")
    def test_tool_error_is_still_caught(self):
        result = self.execute("search_code", {"keyword": ""})
        self.assertEqual(result, {"ok": False, "error": "关键词不能为空"})

    def test_cli_uses_project_root_from_a_different_working_directory(self):
        caller = self.base / "caller"
        caller.mkdir()
        (caller / "outside.txt").write_text("caller marker", encoding="utf-8")
        completed = subprocess.run([
            sys.executable, "-B", str(Path(__file__).with_name("executor.py")),
            str(self.root), "list_files", "{}",
        ], cwd=caller, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["data"]["entries"], [{"path": "src", "type": "directory"}])


if __name__ == "__main__":
    unittest.main()
