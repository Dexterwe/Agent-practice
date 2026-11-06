import subprocess
import sys
from pathlib import Path
import json
from errors import ToolError

def run_tests(project_root: str) -> dict:
    
    try:
        res = subprocess.run([sys.executable,"-m","unittest","discover","-s","practice","-p","test_*.py","-v"],capture_output=True,
            text=True,timeout=30,cwd=project_root)
    except subprocess.TimeoutExpired as error:
        raise ToolError("测试执行超时：超过 30 秒") from error

    return {
        "returncode": res.returncode,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    result = run_tests(str(project_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))