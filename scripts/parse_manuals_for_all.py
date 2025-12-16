from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[1]     # .../kran-tools
INPUT = BASE / "input"
MODELS = [d.name for d in INPUT.iterdir() if d.is_dir()]

for model in MODELS:
    print(f"\n=== PARSE MANUALS FOR MODEL: {model} ===")
    cmd = [
        "python",
        "-m",
        "scripts.manual_parser",
        "--model",
        model
    ]
    subprocess.run(cmd)
