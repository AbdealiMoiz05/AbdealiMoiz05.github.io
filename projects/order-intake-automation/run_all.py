"""Run the whole pipeline in order. Usage: python3 run_all.py [--method rules|ai|hybrid]"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
extra = sys.argv[1:]
for step in ["generate_data.py", "extract.py", "validate.py", "evaluate.py", "notify.py", "time_saved.py"]:
    print(f"\n== {step} ==")
    subprocess.run([sys.executable, str(HERE / step)] + (extra if step == "extract.py" else []), check=True)
