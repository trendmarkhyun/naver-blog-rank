import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "test_run.log"

def run(cmd):
    LOG.write_text("", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, text=True)
        f.write(f"\nexit_code={result.returncode}\n")
    return result.returncode

python = ROOT / ".venv" / "Scripts" / "python.exe"
if not python.exists():
    run([sys.executable, "-m", "venv", str(ROOT / ".venv")])
    run([str(python), "-m", "pip", "install", "-r", "requirements.txt"])
    run([str(ROOT / ".venv" / "Scripts" / "playwright.exe"), "install", "chromium"])

code = run([str(python), "-m", "unittest", "discover", "-s", "tests", "-v"])
print(LOG.read_text(encoding="utf-8"))
raise SystemExit(code)
