import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup

SRC = Path("waybackup_snapshots")   # waybackup's output folder
OUT = Path("pages")                 # clean copies go here
SKIP = {"search", "system", "forum", "admin", "nav", "page-tags"}

def clean_name(slug):
    # "spell:fireball" -> "spell-fireball.html"
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") + ".html"

OUT.mkdir(exist_ok=True)
entries = {}   # slug -> info (dictionary, so duplicates overwrite cleanly)

for f in SRC.rglob("*"):
    if not f.is_file() or f.stat().st_size < 500:
        continue                      # skip folders and tiny/failed files

    html = f.read_text(encoding="utf-8", errors="ignore")
    if "<html" not in html.lower():
        continue                      # skip css, js, images

    match = re.search(r'pageUnixName\s*=\s*"([^"]+)"', html)
    slug = match.group(1) if match else unquote(f.name)

    category = slug.split(":")[0] if ":" in slug else "other"
    if category in SKIP:
        continue

    size = f.stat().st_size
    if slug in entries and size <= entries[slug]["size"]:
        continue                      # already have a bigger copy

    soup = BeautifulSoup(html, "lxml")
    title = soup.find(id="page-title")
    if title:
        name = title.get_text(strip=True)
    elif soup.title and soup.title.string:
        name = soup.title.string.split(" - ")[0].strip()
    else:
        name = slug

    filename = clean_name(slug)
    shutil.copy(f, OUT / filename)
    entries[slug] = {"name": name, "slug": slug, "category": category,
                     "file": filename, "size": size}

index = sorted(entries.values(), key=lambda e: e["name"].lower())
Path("index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
print(f"Done: {len(index)} pages")