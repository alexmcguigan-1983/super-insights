"""Print the number of funds/options needing attention for a snapshot (used by the refresh workflow)."""
import json
import sys
from pathlib import Path

snap = sys.argv[1]
n = 0
q = Path(f"quarantine/{snap}/reasons.json")
if q.exists():
    n += len(json.loads(q.read_text()))
m = Path(f"raw/{snap}/manifest.json")
if m.exists():
    n += sum(1 for v in json.loads(m.read_text())["funds"].values() if v.get("errors"))
print(n)
