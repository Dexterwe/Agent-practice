"""Local, read-only project tools. No model SDK or API key is needed."""

import json
from pathlib import Path
import shutil
import subprocess


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
IGNORED_FILES = {".DS_Store", "apikeys.js", "apikeys.py"}
MAX_FILE_BYTES = 1024 * 1024
MAX_READ_LINES = 200


class ToolError(Exception):
    """An expected tool failure that can be returned to the model."""


def excluded(relative_path: Path) -> bool:
    return (
        any(part in IGNORED_DIRS for part in relative_path.parts)
        or relative_path.name in IGNORED_FILES
        or relative_path.name == ".env"
        or relative_path.name.startswith(".env.")
        or relative_path.suffix in {".pem", ".key"}
    )


def validate_integer(value: int, name: str, maximum: int) -> None:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ToolError(f"{name} 必须是 1 到 {maximum} 之间的整数")


class ProjectTools:
    def __init__(self, project_root: str):
        self.root = Path(project_root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise ToolError("项目根路径必须是目录")

    def _resolve(self, path: str) -> Path:
        """Check the requested path and its resolved symlink destination."""
        if not isinstance(path, str) or not path.strip():
            raise ToolError("path 必须是非空字符串")
        requested = Path(path)
        if requested.is_absolute():
            raise ToolError("请使用相对项目根目录的路径")
        if excluded(requested):
            raise ToolError("该路径被工具排除")
        try:
            target = (self.root / requested).resolve(strict=True)
        except (OSError, RuntimeError):
            raise ToolError("路径不存在或无法解析")
        try:
            relative = target.relative_to(self.root)
        except ValueError:
            raise ToolError("路径超出项目根目录")
        if excluded(relative):
            raise ToolError("该路径被工具排除")
        return target

    def list_files(self, path: str = ".", max_entries: int = 100) -> dict:
        """List one directory level; the model can request a subdirectory next."""
        validate_integer(max_entries, "max_entries", 200)
        directory = self._resolve(path)
        if not directory.is_dir():
            raise ToolError("list_files 的 path 必须是目录")

        entries = []
        for child in sorted(directory.iterdir(), key=lambda item: item.name):
            try:
                target = self._resolve(child.relative_to(self.root).as_posix())
            except ToolError:
                continue
            if not target.is_dir() and not target.is_file():
                continue
            entries.append({
                "path": child.relative_to(self.root).as_posix(),
                "type": "directory" if target.is_dir() else "file",
            })
            if len(entries) > max_entries:
                break

        return {
            "path": directory.relative_to(self.root).as_posix(),
            "entries": entries[:max_entries],
            "truncated": len(entries) > max_entries,
        }

    def search_code(self, keyword: str, path: str = ".", max_results: int = 30) -> dict:
        """Search literal text with ripgrep; do not interpret it as regex or shell."""
        if not isinstance(keyword, str) or not keyword.strip() or "\n" in keyword:
            raise ToolError("keyword 必须是非空的单行字符串")
        validate_integer(max_results, "max_results", 100)
        target = self._resolve(path)
        executable = shutil.which("rg")
        if executable is None:
            raise ToolError("未找到 rg，请安装 ripgrep 并确保它位于 PATH 中")

        command = [
            executable, "--no-config", "--json", "--fixed-strings", "--hidden",
            "--max-filesize", str(MAX_FILE_BYTES), "--max-count", str(max_results),
        ]
        for directory in sorted(IGNORED_DIRS):
            command.extend(["--glob", f"!**/{directory}/**"])
        for filename in sorted(IGNORED_FILES | {".env", ".env.*", "*.pem", "*.key"}):
            command.extend(["--glob", f"!**/{filename}"])
        command.extend(["--", keyword, target.relative_to(self.root).as_posix()])

        try:
            completed = subprocess.run(
                command, cwd=self.root, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=10, check=False,
            )
        except subprocess.TimeoutExpired:
            raise ToolError("搜索超过 10 秒，请缩小 path 范围")
        # ripgrep: 0 = matches found; 1 = no matches; 2 = an error.
        if completed.returncode not in (0, 1):
            raise ToolError(f"搜索失败：{completed.stderr.strip()[:500]}")

        matches = []
        for line in completed.stdout.splitlines():
            event = json.loads(line)
            if event.get("type") != "match":
                continue
            data = event["data"]
            filename = data["path"].get("text")
            content = data["lines"].get("text")
            if filename is None or content is None:
                continue
            # Validate paths returned by the external search tool as well.
            try:
                matched_file = self._resolve(filename)
            except ToolError:
                continue
            matches.append({
                "path": matched_file.relative_to(self.root).as_posix(),
                "line": data["line_number"],
                "content": content.rstrip("\r\n")[:1000],
            })
            if len(matches) > max_results:
                break

        return {
            "keyword": keyword,
            "matches": matches[:max_results],
            # A full result budget may also mean rg stopped early in one file.
            "truncated": len(matches) >= max_results,
        }

    def read_file(self, path: str, start_line: int = 1, end_line: int = 200) -> dict:
        """Read a bounded line range from a UTF-8 text file."""
        validate_integer(start_line, "start_line", 1_000_000)
        validate_integer(end_line, "end_line", 1_000_000)
        if end_line < start_line or end_line - start_line + 1 > MAX_READ_LINES:
            raise ToolError("行范围无效，单次最多读取 200 行")
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError("read_file 的 path 必须是普通文件")
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ToolError("本练习仅支持读取不超过 1 MiB 的文件")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ToolError("本工具仅支持 UTF-8 文本文件")
        if "\x00" in text:
            raise ToolError("文件包含空字节，请使用文本文件")
        lines = text.splitlines()
        if lines and start_line > len(lines):
            raise ToolError(f"start_line 超出文件范围，文件共 {len(lines)} 行")
        selected = lines[start_line - 1:end_line]
        return {
            "path": target.relative_to(self.root).as_posix(),
            "total_lines": len(lines),
            "content": "\n".join(
                f"{number}: {line}"
                for number, line in enumerate(selected, start=start_line)
            ),
        }

    def execute(self, name: str, arguments: dict) -> dict:
        """A single entry point for both local demos and later model tool calls."""
        handlers = {
            "list_files": self.list_files,
            "search_code": self.search_code,
            "read_file": self.read_file,
        }
        if not isinstance(name, str) or name not in handlers:
            return {"ok": False, "error": "未知工具"}
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "工具参数必须是对象"}
        try:
            return {"ok": True, "data": handlers[name](**arguments)}
        except (ToolError, OSError, TypeError, ValueError) as error:
            return {"ok": False, "error": str(error)}
