import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent   # the DMify folder
PAGES = ROOT / "pages"


def key(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


# name -> file, but only for names that belong to exactly one page
index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
by_name = {}
for e in index:
    by_name.setdefault(key(e["name"]), set()).add(e["file"])
unique = {k: next(iter(v)) for k, v in by_name.items() if len(v) == 1}

existing = {p.name for p in PAGES.glob("*.html")}

pages_changed = links_restored = separators_removed = 0

for f in PAGES.glob("*.html"):
    soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="ignore"), "lxml")
    changed = False

    # 1. remove the hidden separator divs (their style attribute has a typo)
    for d in soup.select(".content-separator"):
        d.decompose()
        separators_removed += 1
        changed = True

    # 2. turn grayed-out "missing" links back into real links when the page now exists
    for span in soup.select("span.missing"):
        target = span.get("data-target")                 # exact, if build_site saved it
        if target not in existing:
            target = unique.get(key(span.get_text()))    # otherwise guess from the text
        if not target or target not in existing or target == f.name:
            continue
        span.name = "a"
        span["href"] = target
        classes = [c for c in span.get("class", []) if c != "missing"]
        if classes:
            span["class"] = classes
        else:
            del span["class"]
        if "data-target" in span.attrs:
            del span["data-target"]
        links_restored += 1
        changed = True

    if changed:
        f.write_text(str(soup), encoding="utf-8")
        pages_changed += 1

print(f"Updated {pages_changed} pages: restored {links_restored} links, "
      f"removed {separators_removed} separator divs")