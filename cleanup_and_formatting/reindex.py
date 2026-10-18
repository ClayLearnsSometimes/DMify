import json
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent   # the DMify folder
PAGES = ROOT / "pages"

index = []
for f in sorted(PAGES.glob("*.html")):
    soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="ignore"), "lxml")
    if soup.title and soup.title.string:
        name = soup.title.string.split(" - ")[0].strip()   # works for raw and cleaned pages
    else:
        name = f.stem
    category = f.stem.split("-")[0]                        # 'spell-fireball' -> 'spell'
    index.append({"name": name, "slug": f.stem, "category": category, "file": f.name})

index.sort(key=lambda e: e["name"].lower())
(ROOT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(f"Indexed {len(index)} pages from {PAGES}")