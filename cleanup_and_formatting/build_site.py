import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent    # the DMify folder

SRC = ROOT / "waybackup_snapshots"
OUT = ROOT / "testDump"
STYLE = ROOT / "style.css"
SKIP = {"search", "system", "forum", "admin", "nav", "page-tags"}
MIN_SIZE = 500                      # smaller files are usually failed captures


def clean_name(slug):
    """'spell:fireball' -> 'spell-fireball.html' (safe on Windows)."""
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") + ".html"


def link_to_slug(href):
    """Turn any wikidot/wayback link into a slug like 'spell:fireball'."""
    href = re.sub(r"^(https?:)?//web\.archive\.org", "", href)
    href = re.sub(r"^/web/\d+[a-z_]*/", "", href)
    path = urlparse(href).path          # drops #anchor and ?query
    return unquote(re.sub(r"^/", "", path))


# ---------- PASS 1: find every page and pick the best copy of each ----------
best = {}       # slug -> {"path": Path, "size": int}
skipped = []    # (file, reason) so you can see what got left out

for f in SRC.rglob("*"):
    if not f.is_file():
        continue
    size = f.stat().st_size
    if size < MIN_SIZE:
        skipped.append((str(f), f"too small ({size} bytes)"))
        continue

    html = f.read_text(encoding="utf-8", errors="ignore")
    if "<html" not in html.lower():
        continue                        # css, js, etc. (not worth listing)

    m = re.search(r'pageUnixName\s*=\s*"([^"]+)"', html)
    slug = m.group(1) if m else unquote(f.name)

    category = slug.split(":")[0] if ":" in slug else "other"
    if category in SKIP:
        skipped.append((str(f), f"skipped category '{category}'"))
        continue

    if slug in best and size <= best[slug]["size"]:
        continue                        # already have a bigger copy
    best[slug] = {"path": f, "size": size}

print(f"Pass 1: found {len(best)} unique pages")

# which pages exist locally (used to decide if a link is usable)
existing = {clean_name(slug) for slug in best} | {p.name for p in OUT.glob("*.html")}

# ---------- PASS 2: clean each page and write it out ----------
TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="style.css"></head>
<body><main>
<h1>{title}</h1>
{content}
</main></body></html>"""

OUT.mkdir(exist_ok=True)
if STYLE.exists():
    shutil.copy(STYLE, OUT / "style.css")

index = []
for slug, info in best.items():
    soup = BeautifulSoup(
        info["path"].read_text(encoding="utf-8", errors="ignore"), "lxml")

    content = soup.find(id="page-content")
    if content is None:
        skipped.append((str(info["path"]), "no #page-content found"))
        continue

    t = soup.find(class_="page-title")
    if t and t.get_text(strip=True):
        name = t.get_text(strip=True)
    elif soup.title and soup.title.string:
        name = soup.title.string.split(" - ")[0].strip()
    else:
        name = slug

    for tag in content.select(".content-separator"):
        tag.decompose()

    for tag in content.find_all(["script", "iframe", "form"]):
        tag.decompose()

    for a in content.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            continue
        target = clean_name(link_to_slug(href))
        if target in existing:
            a["href"] = target
        else:
            a.name = "span"             # page wasn't archived: plain text
            a["class"] = a.get("class", []) + ["missing"]
            a["data-target"] = target   
            del a["href"]

    filename = clean_name(slug)
    (OUT / filename).write_text(
        TEMPLATE.format(title=name, content=content.decode_contents()),
        encoding="utf-8")

    category = slug.split(":")[0] if ":" in slug else "other"
    index.append({"name": name, "slug": slug,
                  "category": category, "file": filename})

index.sort(key=lambda e: e["name"].lower())
Path("index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
Path("skipped.txt").write_text(
    "\n".join(f"{reason}\t{path}" for path, reason in skipped), encoding="utf-8")

print(f"Pass 2: wrote {len(index)} pages to {OUT}/")
print(f"Skipped {len(skipped)} files (see skipped.txt)")