"""Copy synthetic fixture funds into raw/2025-12-31 so `make demo` can run the pipeline offline."""
import shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for f in ["examplesuper", "examplecsv", "examplepdf"]:
    d = ROOT / "raw" / "2025-12-31-demo" / f
    d.mkdir(parents=True, exist_ok=True)
    for p in (ROOT / "tests" / "fixtures" / f).iterdir():
        shutil.copy(p, d / p.name)
print("fixtures staged into raw/2025-12-31-demo")
