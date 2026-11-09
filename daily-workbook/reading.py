#!/usr/bin/env python3
"""Saved Substack articles for the daily workbook.

Paste links into reading_links.txt (one per line), or use `add`. During your
online time run `fetch` to download each new article into reading/ as plain
text. The workbook itself never goes online: it prints one downloaded
article a day, plus reflection questions from your local model.

    python3 reading.py add https://example.substack.com/p/some-post [more urls]
    python3 reading.py fetch      # online: download any links not saved yet
    python3 reading.py list       # what's saved, what's been printed
    python3 reading.py today      # which article today's workbook will use

Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINKS_FILE = HERE / "reading_links.txt"
ARTICLE_DIR = HERE / "reading"
PROGRESS_FILE = HERE / "reading_progress.json"

LINKS_HEADER = """# Substack links to read, one per line. Run `python3 reading.py fetch`
# during your online time to download new ones. Lines starting with # are ignored.
"""
USER_AGENT = "Mozilla/5.0 (Macintosh) DailyWorkbook/1.0 (personal reading list)"

# The five lenses the writing prompts cover, in order. The local model writes
# one article-specific prompt per lens; these generic ones are the fallback.
PROMPT_LENSES = [
    # (lens, required opening for the model, fallback prompt, follow-up printed under it)
    ("In your own words", "In your own words, explain",
     "In your own words, explain the author's central argument as if to a friend who hasn't read it.",
     "Then name the single strongest piece of support the author gives."),
    ("Assumptions", "The author takes for granted that",
     "The author takes for granted that some things are true without proving them. Pick one.",
     "Is it actually true? Write what would change about the argument if it weren't."),
    ("Push back", "Make the strongest case against",
     "Make the strongest case against the article's main claim.",
     "Argue it as if you believed it. Then say where the article answers you well, or doesn't."),
    ("Go deeper", "To understand this topic better, find out",
     "To understand this topic better, find out what context, data or history is missing here.",
     "Write what you expect to find, and add the questions to your online list."),
    ("Connect", "Think of a time",
     "Think of a time you saw this play out in your own life or community.",
     "Has this article changed what you think, or what you'll do?"),
]


# ── Links and storage ─────────────────────────────────────────────────────────

def load_links() -> list[str]:
    try:
        lines = LINKS_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    seen, out = set(), []
    for l in lines:
        u = l.strip()
        if u and not u.startswith("#") and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def clean_url(url: str) -> str:
    """Drop share/tracking query strings (utm_*, r=<referral code>)."""
    return url.strip().split("?", 1)[0].split("#", 1)[0]


def add_links(urls: list[str]) -> int:
    existing = load_links()
    new = []
    for u in map(clean_url, urls):
        if u.startswith("http") and u not in existing and u not in new:
            new.append(u)
    body = "".join(f"{u}\n" for u in existing + new)
    LINKS_FILE.write_text(LINKS_HEADER + "\n" + body, encoding="utf-8")
    return len(new)


def slug_for(url: str) -> str:
    # Note-share links (substack.com/@name/note/p-12345) point at post 12345.
    m = re.search(r"/note/p-(\d+)", url) or re.search(r"/p/([^/?#]+)", url)
    if m and m.group(0).startswith("/note/"):
        base = f"post-{m.group(1)}"
    else:
        base = m.group(1) if m else re.sub(r"\W+", "-", url)[-40:]
    return f"{base[:60]}-{hashlib.sha1(url.encode()).hexdigest()[:6]}"


def article_path(url: str) -> Path:
    return ARTICLE_DIR / f"{slug_for(url)}.json"


def load_article(url: str) -> dict | None:
    try:
        return json.loads(article_path(url).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_article(article: dict) -> None:
    ARTICLE_DIR.mkdir(exist_ok=True)
    article_path(article["url"]).write_text(
        json.dumps(article, indent=2, ensure_ascii=False), encoding="utf-8")


def load_progress() -> dict:
    try:
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"by_date": {}}


def save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, indent=2), encoding="utf-8")


# ── Fetching (online only) ────────────────────────────────────────────────────

class _SubstackParser(HTMLParser):
    """Pulls the title, author and body text out of a Substack post page."""

    SKIP_TAGS = {"script", "style", "figcaption", "button", "svg", "form"}
    SKIP_CLASSES = ("subscription-widget", "subscribe-widget", "button-wrapper", "footnote-anchor")
    BLOCKS = {"p": "p", "h1": "h", "h2": "h", "h3": "h", "h4": "h", "blockquote": "quote", "li": "li", "pre": "p"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.blocks: list[dict] = []
        self.paywalled = False
        self._body_depth = 0      # >0 while inside the post body
        self._depth = 0
        self._cur: list[str] | None = None
        self._cur_type = ""
        self._quote = 0
        self._skip_at = 0         # depth of a skipped element (script, caption, subscribe box); 0 = not skipping
        self._ld: list[str] | None = None   # collecting a JSON-LD script

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "meta":
            key = a.get("property") or a.get("name")
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"])
            return
        if tag in ("br", "img", "hr", "input", "source", "link"):
            return
        self._depth += 1
        if tag == "script" and a.get("type") == "application/ld+json":
            self._ld = []
        if "paywall" in cls:
            self.paywalled = True
        if self._body_depth == 0 and "body" in cls.split() and "markup" in cls.split():
            self._body_depth = self._depth
            return
        if not self._body_depth:
            return
        if not self._skip_at and (tag in self.SKIP_TAGS or any(k in cls for k in self.SKIP_CLASSES)):
            self._skip_at = self._depth
        if tag == "blockquote":
            self._quote += 1
        if tag in self.BLOCKS and self._cur is None and not self._skip_at:
            self._cur, self._cur_type = [], ("quote" if self._quote else self.BLOCKS[tag])

    def handle_endtag(self, tag):
        if tag in ("br", "img", "hr", "input", "source", "link", "meta"):
            return
        if tag == "script" and self._ld is not None:
            try:
                ld = json.loads("".join(self._ld))
                ld = ld[0] if isinstance(ld, list) and ld else ld
                if isinstance(ld, dict):
                    self.meta.setdefault("ld:published", str(ld.get("datePublished", "")))
                    pub = ld.get("publisher")
                    if isinstance(pub, dict) and pub.get("name"):
                        self.meta.setdefault("ld:publisher", pub["name"])
                    auth = ld.get("author")
                    auth = auth[0] if isinstance(auth, list) and auth else auth
                    if isinstance(auth, dict) and auth.get("name"):
                        self.meta.setdefault("ld:author", auth["name"])
            except (json.JSONDecodeError, TypeError):
                pass
            self._ld = None
        if self._body_depth:
            if tag == "blockquote" and self._quote:
                self._quote -= 1
            if tag in self.BLOCKS and self._cur is not None:
                text = re.sub(r"\s+", " ", "".join(self._cur)).strip()
                if text:
                    self.blocks.append({"type": self._cur_type, "text": text})
                self._cur = None
            if self._skip_at and self._depth == self._skip_at:
                self._skip_at = 0
            if self._depth == self._body_depth:
                self._body_depth = 0
        self._depth -= 1

    def handle_data(self, data):
        if self._ld is not None:
            self._ld.append(data)
        if self._cur is not None and not self._skip_at:
            self._cur.append(data)


def fetch_article(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode(resp.headers.get_content_charset() or "utf-8", "replace")
        final_url = resp.geturl()
    p = _SubstackParser()
    p.feed(html)
    if not p.blocks:
        raise ValueError("no article text found (not a Substack post, or fully paywalled)")
    m = p.meta
    return {
        "url": url,
        "post_url": clean_url(final_url),
        "title": m.get("og:title") or m.get("twitter:title") or "Untitled",
        "subtitle": m.get("og:description") or m.get("description") or "",
        "author": m.get("ld:author") or m.get("author") or m.get("article:author") or "",
        "publication": m.get("og:site_name") or m.get("ld:publisher") or "",
        "published": (m.get("article:published_time") or m.get("ld:published") or "")[:10],
        "fetched": datetime.now().isoformat(timespec="seconds"),
        "paywalled": p.paywalled,
        "blocks": p.blocks,
        "words": sum(len(b["text"].split()) for b in p.blocks),
    }


def _api_url(article: dict) -> str | None:
    m = re.search(r"/note/p-(\d+)", article["url"])
    if m:
        return f"https://substack.com/api/v1/posts/by-id/{m.group(1)}"
    u = urllib.parse.urlparse(article.get("post_url") or article["url"])
    m = re.search(r"/p/([^/?#]+)", u.path)
    return f"https://{u.netloc}/api/v1/posts/{m.group(1)}" if m else None


def check_access(article: dict) -> None:
    """Ask Substack who can read the post and compare against what we saved.

    Marks the article paywalled if it's for paid subscribers only, or if the
    saved text is much shorter than Substack's own word count.
    """
    url = _api_url(article)
    if not url:
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        post = json.loads(urllib.request.urlopen(req, timeout=20).read())
        post = post.get("post", post)
    except Exception as e:
        article["access_note"] = f"couldn't check with Substack: {e}"
        return
    article["audience"] = post.get("audience")
    full = post.get("wordcount") or 0
    article["substack_wordcount"] = full
    if post.get("audience") not in (None, "everyone"):
        article["paywalled"] = True
    if full and article["words"] < 0.85 * full:
        article["paywalled"] = True
        article["access_note"] = f"saved {article['words']} of about {full} words"


def fetch_all(refetch: bool = False) -> None:
    links = load_links()
    if not links:
        print(f"No links yet. Add some to {LINKS_FILE.name} or run: python3 reading.py add <url>")
        return
    fetched_any = False
    for url in links:
        if load_article(url) and not refetch:
            continue
        if fetched_any:
            time.sleep(1.5)  # be polite to Substack
        fetched_any = True
        try:
            a = fetch_article(url)
            check_access(a)
            save_article(a)
            note = "  (preview only: paywalled)" if a["paywalled"] else ""
            print(f"✓ {a['title'][:60]}  [{a['words']} words]{note}")
        except Exception as e:
            print(f"⚠ {url}\n   {e}")


# ── Picking today's article (offline) ─────────────────────────────────────────

def saved_articles() -> list[dict]:
    """Downloaded articles, in the order the links are listed."""
    out = []
    for url in load_links():
        a = load_article(url)
        if a:
            out.append(a)
    return out


def article_for(day: date | None = None, mark: bool = True) -> dict | None:
    """Today's article, picked at random from the ones not printed this round.

    No article repeats until every printable article has had its turn; then a
    new round starts. The pick is saved, so rerunning the workbook on the same
    day gives the same article.
    """
    day = day or date.today()
    key = day.isoformat()
    progress = load_progress()
    by_date = progress.setdefault("by_date", {})
    # Never print a paywalled preview; only full, free articles.
    articles = [a for a in saved_articles() if not a.get("paywalled")]
    if not articles:
        return None
    by_url = {a["url"]: a for a in articles}
    if key in by_date and by_date[key] in by_url:
        return by_url[by_date[key]]

    round_start = progress.get("round_start", "")
    used = {u for d, u in by_date.items() if d >= round_start}
    fresh = [a for a in articles if a["url"] not in used]
    if not fresh:  # everyone has had a turn: start a new round
        round_start = key
        yesterday = by_date.get(max(by_date)) if by_date else None
        fresh = [a for a in articles if a["url"] != yesterday] or articles
    pick = random.Random(f"reading-{key}").choice(fresh)
    if mark:
        progress["round_start"] = round_start
        by_date[key] = pick["url"]
        save_progress(progress)
    return pick


def save_prompts(article: dict, prompts: list[str]) -> None:
    article["prompts"] = prompts
    save_article(article)


def article_excerpt(article: dict, max_words: int = 1800) -> str:
    """Plain text for the model prompt, trimmed to keep generation fast."""
    words, out = 0, []
    for b in article.get("blocks", []):
        n = len(b["text"].split())
        if words + n > max_words:
            break
        out.append(b["text"])
        words += n
    return "\n\n".join(out)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "list"
    if cmd == "add":
        n = add_links(argv[1:])
        print(f"✓ Added {n} new link(s). Run `python3 reading.py fetch` during your online time.")
    elif cmd == "fetch":
        fetch_all(refetch="--refetch" in argv)
    elif cmd == "today":
        a = article_for(mark=False)
        print(f"{a['title']} ({a['words']} words)" if a else "No saved articles yet.")
    elif cmd == "list":
        used = set(load_progress().get("by_date", {}).values())
        links = load_links()
        if not links:
            print("No links yet.")
        for u in links:
            a = load_article(u)
            state = "printed" if u in used else ("saved" if a else "not downloaded")
            title = a["title"][:55] if a else u[:55]
            print(f"  [{state:>14}]  {title}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
