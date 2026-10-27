import re
from pathlib import Path
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup

SRC = Path("pages")          # raw copies from build_pages.py
OUT = Path("clean_pages")    # tidy versions the app will display
OUT.mkdir(exist_ok=True)

def clean_name(slug):
    return re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") + ".html"

def link_to_slug(href):
    """Turn any wikidot/wayback link into a slug like 'spell:fireball'."""
    href = re.sub(r"^(https?:)?//web\.archive\.org", "", href)   # wayback host
    href = re.sub(r"^/web/\d+[a-z_]*/", "", href)                # wayback prefix
    path = urlparse(href).path                                   # drops #anchor and ?query
    path = re.sub(r"^/", "", path)
    return unquote(path)

existing = {f.name for f in SRC.glob("*.html")}

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<link rel="stylesheet" href="style.css"></head>
<body><main>
<h1>{title}</h1>
{content}
</main></body></html>"""

for f in SRC.glob("*.html"):
    soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="ignore"), "lxml")

    content = soup.find(id="page-content")
    if content is None:
        continue

    # title: wikidot uses <div class="page-title">, fall back to <title>
    t = soup.find(class_="page-title")
    if t:
        title = t.get_text(strip=True)
    elif soup.title and soup.title.string:
        title = soup.title.string.split(" - ")[0].strip()
    else:
        title = f.stem

    # remove scripts and anything interactive inside the content
    for tag in content.find_all(["script", "iframe", "form"]):
        tag.decompose()

    # fix links
    for a in content.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            continue                          # same-page anchor, leave alone
        target = clean_name(link_to_slug(href))
        if target in existing:
            a["href"] = target
        else:
            a.name = "span"                   # page wasn't archived: plain text
            a["class"] = a.get("class", []) + ["missing"]
            del a["href"]

    (OUT / f.name).write_text(
        TEMPLATE.format(title=title, content=content.decode_contents()),
        encoding="utf-8")

print("done")