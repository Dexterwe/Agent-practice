import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from replace_text import replace_text


class ReplaceTextTests(unittest.TestCase):

    def test_replaces_unique_text(self):
        with TemporaryDirectory() as directory:
            # 1. 准备：创建一个包含原文的临时文件
            file_path = Path(directory) / "sample.txt"
            file_path.write_text("hello\n", encoding="utf-8")

            # 2. 执行：调用需要测试的函数
            result = replace_text(
                path=str(file_path),
                old_text="hello",
                new_text="你好",
            )

            # 3. 检查：重新读取文件，确认实际写入的内容
            actual = file_path.read_text(encoding="utf-8")
            self.assertEqual(actual, "你好\n")

            # 检查函数返回的替换次数
            self.assertEqual(result["replacements"], 1)


if __name__ == "__main__":
    unittest.main()