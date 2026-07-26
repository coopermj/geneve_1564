"""Fetch King James Version (public domain) text with local JSON caching.

Source: aruljohn/Bible-kjv (per-book JSON, one file per book). Returns the same
{chapter_num: [verse_dicts]} shape as bible_fetcher.fetch_book so the shared
generate_book_tex pipeline can be reused unchanged. verse_dicts have keys
'verse' and 'text' (plain text; KJV carries no HTML markup)."""
import json
import os
import time
import urllib.request

_RAW = "https://raw.githubusercontent.com/aruljohn/Bible-kjv/master/{file}.json"
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kjv_cache")


def _aruljohn_file(book_name: str) -> str:
    """Map a BookInfo.name ('1 Samuel', 'Song of Solomon') to the repo filename."""
    return book_name.replace(" ", "")


def _fetch_raw(book_name: str, cache_dir: str) -> dict:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, _aruljohn_file(book_name) + ".json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    url = _RAW.format(file=_aruljohn_file(book_name))
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geneve1564-kjv/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"unreachable: {url}")


def fetch_book(book_name: str, num_chapters: int, cache_dir: str = DEFAULT_CACHE_DIR) -> dict[int, list[dict]]:
    """Return {chapter_num: [{'verse': int, 'text': str}, ...]} for a KJV book."""
    raw = _fetch_raw(book_name, cache_dir)
    chapters: dict[int, list[dict]] = {}
    for ch in raw.get("chapters", []):
        n = int(ch["chapter"])
        chapters[n] = [{"verse": int(v["verse"]), "text": v["text"].strip()}
                       for v in ch.get("verses", [])]
    if len(chapters) != num_chapters:
        print(f"  warning: {book_name} expected {num_chapters} chapters, got {len(chapters)}")
    return chapters


if __name__ == "__main__":
    import sys
    name = " ".join(sys.argv[1:]) or "Jude"
    d = fetch_book(name, 0)
    print(f"{name}: {len(d)} chapters; 1:1 = {d[1][0]}")
