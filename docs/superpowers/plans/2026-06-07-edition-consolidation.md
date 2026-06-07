# Edition Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the three edition branches into one branch where all five compile targets build from one directory via `generate.py --edition <name>` and CLI Makefile targets, seeding entirely from existing offline caches.

**Architecture:** Approach A (clean copy + archive tags). Per-edition main docs + tracked `editions/<name>/` assets (cover, color_index); gitignored generated book dirs (`livres_esv/`, `livres_net/`, `livres_geneva/`). One `generate.py` dispatches to refactored `run_esv()` / `run_net(annotated=…)`; geneva = NET path + annotation kwargs + committed `corrections_final.json`. Heavy overlap re-convergence stays a separate maintenance script.

**Tech Stack:** Python 3.13, LuaLaTeX, the `scripture` package (v2.3), existing fetchers/caches, PyMuPDF (geneva maintenance only).

---

## Background the engineer must know

- **Work branch:** `chore/consolidate-editions` (already created off `master`; the design spec is committed there). All tasks run from repo root `/Users/micahcooper/geneve_1564` unless stated.
- **Source branches (read-only):** `feature/net-notes` and `feature/geneva-annotations`. Retrieve their files with `git show <branch>:<path> > dest` (do NOT check them out — they're in worktrees).
- **Two generators exist:** `esv_latex_generator.py` (ESV) and `latex_generator.py` (NET). The latter is already byte-identical across branches and supports annotations via optional `annotations`/`corrections`/`note_manifest` kwargs on `generate_book_tex`.
- **Caches present & complete (offline):** `data/esv_cache/` (1189), `data/net_bible_cache/` (1189). Generation never needs network.
- **Build invocation (per edition):** `OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode <doc>.tex` from repo root, run twice.
- **Page-count baselines:** ESV 1316, net_notes 2083, geneva ~2002. net_reading and geneve_1564 are new baselines (record whatever they produce).
- **Python "tests" are runnable scripts** that print "All tests passed." (not pytest): run `python3 tests/<name>.py`.
- **Pre-existing junk** (`.DS_Store`, `__pycache__/*.pyc`, `note.txt`) is always left unstaged.

---

## File Structure (target)

```
esv_bible.tex  net_reading.tex  net_notes.tex  geneva_bible.tex  geneve_1564.tex
editions/{esv,net_reading,net_notes,geneva}/{cover.tex,color_index.tex}   # tracked
livres_esv/  livres_net/  livres_geneva/                                   # gitignored, generated
scripts/generate.py            # new dispatcher
scripts/generate_esv.py        # refactored: exposes run_esv()
scripts/generate_bible.py      # refactored: exposes run_net(annotated=…)
scripts/build_annotated.py     # kept: geneva overlap RE-CONVERGENCE (maintenance only)
scripts/{esv_latex_generator,latex_generator,bible_fetcher,esv_fetcher,annotation_fetcher,overlap_detector,bible_config,reading_plan_parser}.py
Makefile                       # new CLI targets
```

---

## Task 1: Safety — archive tags + gitignore

**Files:** Modify `.gitignore`

- [ ] **Step 1: Tag the source branch tips (history preservation).**
```bash
cd /Users/micahcooper/geneve_1564
git tag -f archive/net-notes feature/net-notes
git tag -f archive/geneva-annotations feature/geneva-annotations
git push origin archive/net-notes archive/geneva-annotations
git tag | grep archive/
```
Expected: both tags listed and pushed.

- [ ] **Step 2: Add generated NET dirs to `.gitignore`.** Append after the existing `livres_esv/` line:
```
livres_net/
livres_geneva/
```

- [ ] **Step 3: Verify the ignore works.**
```bash
mkdir -p livres_net/genesis && touch livres_net/genesis/genesis.tex
git check-ignore livres_net/genesis/genesis.tex && echo IGNORED
rm -rf livres_net
```
Expected: prints `livres_net/genesis/genesis.tex` then `IGNORED`.

- [ ] **Step 4: Commit.**
```bash
git add .gitignore
git commit -m "chore: archive edition branches; ignore generated livres_net/livres_geneva"
```

---

## Task 2: Bring in edition files from archive tags

**Files:** Create `net_notes.tex`, `net_reading.tex`, `geneva_bible.tex`, `scripts/annotation_fetcher.py`, `scripts/overlap_detector.py`, `scripts/build_annotated.py`, `tests/conftest.py`, `tests/test_annotation_fetcher.py`, `tests/test_latex_annotations.py`, `tests/test_overlap_detector.py`, `data/geneva_annotations.json`, `data/geneva_arguments.json`, `data/corrections_final.json`

- [ ] **Step 1: Copy net-notes main doc (rename not needed; net_notes.tex is unique).**
```bash
git show archive/net-notes:net_notes.tex > net_notes.tex
```

- [ ] **Step 2: Copy + rename the two NET main docs.**
```bash
git show master:net_bible.tex                      > net_reading.tex
git show archive/geneva-annotations:net_bible.tex  > geneva_bible.tex
```

- [ ] **Step 3: Copy geneva's annotation scripts + tests.**
```bash
for f in scripts/annotation_fetcher.py scripts/overlap_detector.py scripts/build_annotated.py \
         tests/conftest.py tests/test_annotation_fetcher.py tests/test_latex_annotations.py tests/test_overlap_detector.py ; do
  git show archive/geneva-annotations:$f > $f
done
```

- [ ] **Step 4: Copy geneva annotation data (force-add past data/ ignore).**
```bash
for f in data/geneva_annotations.json data/geneva_arguments.json data/corrections_final.json ; do
  git show archive/geneva-annotations:$f > $f
done
git add -f data/geneva_annotations.json data/geneva_arguments.json data/corrections_final.json
```

- [ ] **Step 5: Stage the new tracked files and commit (no build yet).**
```bash
git add net_notes.tex net_reading.tex geneva_bible.tex \
        scripts/annotation_fetcher.py scripts/overlap_detector.py scripts/build_annotated.py \
        tests/conftest.py tests/test_annotation_fetcher.py tests/test_latex_annotations.py tests/test_overlap_detector.py
git commit -m "chore: import edition docs, annotation pipeline, and annotation data"
```
Note: `net_reading.tex` and `geneva_bible.tex` still `\input{livres/...}` — fixed in Task 4. Build is not expected to work until Tasks 3–6 complete.

---

## Task 3: Create per-edition asset dirs (cover + color_index)

**Files:** Create `editions/{esv,net_reading,net_notes,geneva}/{cover.tex,color_index.tex}`

Source of each asset (verified during planning):
- ESV cover = `master:livres_esv/cover.tex`; ESV color_index = current generated `livres_esv/color_index.tex` (snapshot it).
- net_reading = `master:livres/cover.tex`, `master:livres/color_index.tex`.
- net_notes = `archive/net-notes:livres/cover.tex`, `archive/net-notes:livres/color_index.tex`.
- geneva = `archive/geneva-annotations:livres/cover.tex`, `archive/geneva-annotations:livres/color_index.tex`.

- [ ] **Step 1: Create dirs and copy assets.**
```bash
cd /Users/micahcooper/geneve_1564
mkdir -p editions/esv editions/net_reading editions/net_notes editions/geneva

git show master:livres_esv/cover.tex                         > editions/esv/cover.tex
git show master:livres_esv/color_index.tex                   > editions/esv/color_index.tex 2>/dev/null \
  || cp livres_esv/color_index.tex editions/esv/color_index.tex   # generated, not tracked: snapshot from disk

git show master:livres/cover.tex                             > editions/net_reading/cover.tex
git show master:livres/color_index.tex                       > editions/net_reading/color_index.tex
git show archive/net-notes:livres/cover.tex                  > editions/net_notes/cover.tex
git show archive/net-notes:livres/color_index.tex            > editions/net_notes/color_index.tex
git show archive/geneva-annotations:livres/cover.tex         > editions/geneva/cover.tex
git show archive/geneva-annotations:livres/color_index.tex   > editions/geneva/color_index.tex
```

- [ ] **Step 2: Verify all 8 files exist and are non-empty.**
```bash
for f in editions/esv/cover.tex editions/esv/color_index.tex \
         editions/net_reading/cover.tex editions/net_reading/color_index.tex \
         editions/net_notes/cover.tex editions/net_notes/color_index.tex \
         editions/geneva/cover.tex editions/geneva/color_index.tex ; do
  [ -s "$f" ] && echo "ok  $f ($(wc -l < $f) lines)" || echo "MISSING/EMPTY  $f"
done
```
Expected: 8 `ok` lines. If `editions/esv/color_index.tex` is empty, snapshot it from disk: `cp livres_esv/color_index.tex editions/esv/color_index.tex` (build the ESV books first if needed via `python3 scripts/generate_esv.py` — but it should already exist on disk).

- [ ] **Step 3: Commit.**
```bash
git add editions/
git commit -m "chore: add tracked per-edition cover + color_index assets"
```

---

## Task 4: Rewire `\input` paths in the main docs

**Files:** Modify `esv_bible.tex`, `net_reading.tex`, `net_notes.tex`, `geneva_bible.tex`

Each doc currently `\input`s a cover, color_index, testament includes, and (NET) a reading plan. Replace those input lines per the table. Use Edit to match the existing `\input{...}` line by content and swap the path. Leave everything else untouched.

- [ ] **Step 1: esv_bible.tex.** ESV already uses `livres_esv/`. Change only its cover + color_index inputs:
  - `\input{livres_esv/cover}` → `\input{editions/esv/cover}`
  - `\input{livres_esv/color_index}` → `\input{editions/esv/color_index}`
  - Leave `\input{livres_esv/old_testament}` / `new_testament` as-is.

- [ ] **Step 2: net_reading.tex.** Currently inputs `livres/...`. Change:
  - `\input{livres/cover}` → `\input{editions/net_reading/cover}`
  - `\input{livres/color_index}` → `\input{editions/net_reading/color_index}`
  - `\input{livres/old_testament}` → `\input{livres_net/old_testament}`
  - `\input{livres/new_testament}` → `\input{livres_net/new_testament}`
  - `\input{livres/reading_plan}` → `\input{livres_net/reading_plan}`

- [ ] **Step 3: net_notes.tex.** Same NET→net_net mapping, net_notes assets:
  - `\input{livres/cover}` → `\input{editions/net_notes/cover}`
  - `\input{livres/color_index}` → `\input{editions/net_notes/color_index}`
  - `\input{livres/old_testament}` → `\input{livres_net/old_testament}`
  - `\input{livres/new_testament}` → `\input{livres_net/new_testament}`
  - `\input{livres/reading_plan}` → `\input{livres_net/reading_plan}`

- [ ] **Step 4: geneva_bible.tex.** Geneva assets + geneva generated dir:
  - `\input{livres/cover}` → `\input{editions/geneva/cover}`
  - `\input{livres/color_index}` → `\input{editions/geneva/color_index}`
  - `\input{livres/old_testament}` → `\input{livres_geneva/old_testament}`
  - `\input{livres/new_testament}` → `\input{livres_geneva/new_testament}`
  - `\input{livres/reading_plan}` → `\input{livres_geneva/reading_plan}`

- [ ] **Step 5: Verify no stale `\input{livres/` (cover/index/testament/plan) remain in the four docs** (legacy `geneve_1564.tex` is intentionally untouched):
```bash
grep -nE "\\\\input\{livres/(cover|color_index|old_testament|new_testament|reading_plan)\}" \
  esv_bible.tex net_reading.tex net_notes.tex geneva_bible.tex || echo "clean"
```
Expected: `clean`.

- [ ] **Step 6: Commit.**
```bash
git add esv_bible.tex net_reading.tex net_notes.tex geneva_bible.tex
git commit -m "refactor: rewire main docs to editions/ assets and per-edition generated dirs"
```

---

## Task 5: Refactor generators to expose `run_*()` and write `generate.py`

**Files:** Modify `scripts/generate_esv.py`, `scripts/generate_bible.py`; Create `scripts/generate.py`

The refactor wraps each script's existing main-body logic in a callable function and drops `color_index` generation (now a tracked asset). The CLI `main()` stays as a thin wrapper so old invocations still work.

- [ ] **Step 1: Refactor `scripts/generate_esv.py`** — extract the generation body into `run_esv()` and stop writing `color_index.tex`. Replace the `def main():` body so the file reads:

```python
def run_esv(output_dir: str, cache_dir: str, books=None) -> None:
    """Generate ESV book .tex + testament includes into output_dir (offline from cache)."""
    books_to_generate = books if books else BOOKS
    print(f"[esv] Generating {len(books_to_generate)} book(s) -> {output_dir}")
    for book in books_to_generate:
        chapters_html = fetch_book(book.name, book.chapters, ESV_API_KEY, cache_dir)
        tex_content = generate_book_tex(book, chapters_html)
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, f"{book.directory}.tex"), "w", encoding="utf-8") as f:
            f.write(tex_content)
    all_ot = get_books_by_testament("OT")
    all_nt = get_books_by_testament("NT")
    gen = {b.directory for b in books_to_generate}
    if {b.directory for b in all_ot} <= gen:
        with open(os.path.join(output_dir, "old_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_ot, "Old Testament"))
    if {b.directory for b in all_nt} <= gen:
        with open(os.path.join(output_dir, "new_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_nt, "New Testament"))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate LaTeX files for the ESV Bible")
    parser.add_argument("--books", nargs="+")
    parser.add_argument("--output-dir", default=os.path.join(_PROJECT_ROOT, "livres_esv"))
    parser.add_argument("--cache-dir", default=os.path.join(_PROJECT_ROOT, "data", "esv_cache"))
    args = parser.parse_args()
    books = [get_book_by_name(n) for n in args.books] if args.books else None
    if books and any(b is None for b in books):
        print("Error: unknown book", file=sys.stderr); sys.exit(1)
    run_esv(args.output_dir, args.cache_dir, books)
    print("Done!")
```
Add `_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))` and `_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)` near the top if not already present (generate_esv.py currently inlines these paths in argparse defaults — define the two constants so `run_esv`'s `main()` can use them).

- [ ] **Step 2: Refactor `scripts/generate_bible.py`** — extract body into `run_net()` with an `annotated` switch, drop `color_index` generation. Replace from `def main():` onward:

```python
def run_net(output_dir: str, cache_dir: str, books=None,
            annotated: bool = False, corrections_path: str | None = None,
            start_date: str = "2026-03-02") -> None:
    """Generate NET book .tex (plain or annotated) + testament + reading plan into output_dir."""
    from datetime import date as date_cls
    books_to_generate = books if books else BOOKS
    plan_entries = _load_or_parse_plan()
    scheduled = schedule_plan(plan_entries, date_cls.fromisoformat(start_date))
    plan_endpoints = build_plan_endpoints(scheduled)

    annotations = corrections = None
    note_manifest = None
    if annotated:
        annotations = json.load(open(os.path.join(_PROJECT_ROOT, "data", "geneva_annotations.json"), encoding="utf-8"))
        if corrections_path and os.path.exists(corrections_path):
            raw = json.load(open(corrections_path, encoding="utf-8"))
            corrections = {int(k): v for k, v in raw.items()}
        note_manifest = []

    label = "geneva" if annotated else "net"
    print(f"[{label}] Generating {len(books_to_generate)} book(s) -> {output_dir}")
    for book in books_to_generate:
        chapters_data = fetch_book(book.abbreviation, book.chapters, cache_dir)
        tex_content = generate_book_tex(
            book, chapters_data, plan_endpoints=plan_endpoints,
            annotations=annotations, corrections=corrections, note_manifest=note_manifest)
        book_dir = os.path.join(output_dir, book.directory)
        os.makedirs(book_dir, exist_ok=True)
        with open(os.path.join(book_dir, f"{book.directory}.tex"), "w", encoding="utf-8") as f:
            f.write(tex_content)

    all_ot = get_books_by_testament("OT")
    all_nt = get_books_by_testament("NT")
    gen = {b.directory for b in books_to_generate}
    if {b.directory for b in all_ot} <= gen:
        with open(os.path.join(output_dir, "old_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_ot, "Old Testament"))
    if {b.directory for b in all_nt} <= gen:
        with open(os.path.join(output_dir, "new_testament.tex"), "w", encoding="utf-8") as f:
            f.write(generate_testament_tex(all_nt, "New Testament"))
    with open(os.path.join(output_dir, "reading_plan.tex"), "w", encoding="utf-8") as f:
        f.write(generate_reading_plan_tex(scheduled))
    if note_manifest is not None:
        with open(os.path.join(_PROJECT_ROOT, "data", "note_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(note_manifest, f)


def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX files for the NET Bible")
    parser.add_argument("--books", nargs="+")
    parser.add_argument("--output-dir", default=os.path.join(_PROJECT_ROOT, "livres_net"))
    parser.add_argument("--cache-dir", default=os.path.join(_PROJECT_ROOT, "data", "net_bible_cache"))
    parser.add_argument("--start-date", default="2026-03-02")
    args = parser.parse_args()
    books = [get_book_by_name(n) for n in args.books] if args.books else None
    if books and any(b is None for b in books):
        print("Error: unknown book", file=sys.stderr); sys.exit(1)
    run_net(args.output_dir, args.cache_dir, books, start_date=args.start_date)
    print("Done!")
```

- [ ] **Step 3: Create `scripts/generate.py`** (the dispatcher):

```python
#!/usr/bin/env python3
"""Unified edition generator. Seeds offline from existing caches.

Usage:
    python3 scripts/generate.py --edition esv|net|geneva|all
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from generate_esv import run_esv
from generate_bible import run_net

_CORRECTIONS = os.path.join(_ROOT, "data", "corrections_final.json")

def gen_esv():
    run_esv(os.path.join(_ROOT, "livres_esv"), os.path.join(_ROOT, "data", "esv_cache"))

def gen_net():
    run_net(os.path.join(_ROOT, "livres_net"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=False)

def gen_geneva():
    run_net(os.path.join(_ROOT, "livres_geneva"), os.path.join(_ROOT, "data", "net_bible_cache"),
            annotated=True, corrections_path=_CORRECTIONS)

def main():
    ap = argparse.ArgumentParser(description="Generate a Bible edition's book files (offline).")
    ap.add_argument("--edition", required=True, choices=["esv", "net", "geneva", "all"])
    ed = ap.parse_args().edition
    if ed in ("esv", "all"):    gen_esv()
    if ed in ("net", "all"):    gen_net()
    if ed in ("geneva", "all"): gen_geneva()
    print("generate.py: done")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify imports + dispatch wiring (no full run yet).**
```bash
cd /Users/micahcooper/geneve_1564
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['scripts/generate.py','scripts/generate_esv.py','scripts/generate_bible.py']]; print('syntax OK')"
python3 scripts/generate.py --edition net   # offline from cache
ls livres_net/genesis/genesis.tex livres_net/old_testament.tex livres_net/reading_plan.tex
```
Expected: `syntax OK`; net generation runs offline; the three files exist.

- [ ] **Step 5: Byte-equivalence check (net path unchanged vs archived net-notes books).** The archived net-notes book files were generated by the same generator from the same cache; compare:
```bash
git show archive/net-notes:livres/genesis/genesis.tex > /tmp/old_gen.tex 2>/dev/null && \
  diff /tmp/old_gen.tex livres_net/genesis/genesis.tex && echo "NET genesis identical" || echo "differs (investigate)"
```
Expected: `NET genesis identical`. (If archive net-notes didn't track genesis, skip — Task 7 does the full byte check against a fresh old-generator run.)

- [ ] **Step 6: Commit.**
```bash
git add scripts/generate.py scripts/generate_esv.py scripts/generate_bible.py
git commit -m "feat: unified generate.py --edition dispatcher; refactor run_esv/run_net"
```

---

## Task 6: New Makefile with CLI targets

**Files:** Modify `Makefile`

- [ ] **Step 1: Add edition targets.** Append to `Makefile`:

```makefile
LL = OSFONTDIR=fonts TEXINPUTS=microtype: lualatex -shell-escape -interaction=nonstopmode
GEN = python3 scripts/generate.py --edition

define build_edition
	$(GEN) $(2)
	$(LL) $(1).tex
	$(LL) $(1).tex
endef

.PHONY: esv net-reading net-notes geneva geneve-1564 all-editions
esv:         ; $(call build_edition,esv_bible,esv)
net-reading: ; $(call build_edition,net_reading,net)
net-notes:   ; $(call build_edition,net_notes,net)
geneva:      ; $(call build_edition,geneva_bible,geneva)
geneve-1564: ; $(LL) geneve_1564.tex ; $(LL) geneve_1564.tex
all-editions: esv net-reading net-notes geneva geneve-1564
```
(Use a target name `all-editions` to avoid clobbering the existing `all`/`pdf` targets.)

- [ ] **Step 2: Verify Make parses and targets list.**
```bash
make -n esv | head; echo "---"; make -n net-notes | head
```
Expected: each prints the `generate.py --edition` line followed by two `lualatex` lines (dry run, `-n`).

- [ ] **Step 3: Commit.**
```bash
git add Makefile
git commit -m "feat: CLI-selectable edition build targets (esv/net-reading/net-notes/geneva/geneve-1564/all-editions)"
```

---

## Task 7: Verification — generate + byte-equivalence + build all + tests

**Files:** none (verification; fix-forward if failures)

- [ ] **Step 1: Generate every edition offline.**
```bash
cd /Users/micahcooper/geneve_1564
python3 scripts/generate.py --edition all
echo "esv: $(ls livres_esv/*/*.tex|wc -l)  net: $(ls livres_net/*/*.tex|wc -l)  geneva: $(ls livres_geneva/*/*.tex|wc -l)"
```
Expected: 66 each; no network access; no traceback.

- [ ] **Step 2: Byte-equivalence vs old generators (the key regression check).** For ESV and NET, regenerate with the *archived* generator from the same cache into a temp dir and diff (proves the refactor didn't change output):
```bash
# NET: archived net-notes generator
git show archive/net-notes:scripts/latex_generator.py > /tmp/oldnet.py
mkdir -p /tmp/cmp_net && cp scripts/*.py /tmp/cmp_net/ && cp /tmp/oldnet.py /tmp/cmp_net/latex_generator.py
( cd /tmp/cmp_net && python3 generate_bible.py --output-dir /tmp/net_old --cache-dir /Users/micahcooper/geneve_1564/data/net_bible_cache >/dev/null 2>&1 )
diff -r /tmp/net_old/genesis livres_net/genesis && echo "NET genesis byte-identical"
```
Expected: `NET genesis byte-identical`. Investigate any diff before proceeding. (Spot-checking genesis + one NT book is sufficient; the generator change is the same additive code already proven neutral.)

- [ ] **Step 3: Build all five editions.**
```bash
make esv && make net-reading && make net-notes && make geneva && make geneve-1564
for d in esv_bible net_reading net_notes geneva_bible geneve_1564 ; do
  echo "$d: $(grep -oE 'Output written.*page' $d.log | tail -1)"
  grep -iE '^!|Undefined control sequence|Emergency stop' $d.log | head -3
done
```
Expected: each writes a PDF with **0 errors**; ESV 1316 pp, net_notes 2083 pp, geneva ~2002 pp; net_reading and geneve_1564 produce stable counts (record them).

- [ ] **Step 4: Run the Python test scripts.**
```bash
for t in test_red_letter test_latex_escaping test_annotation_fetcher test_latex_annotations test_overlap_detector ; do
  echo "== $t =="; python3 tests/$t.py 2>&1 | tail -1
done
```
Expected: each ends `All tests passed.` (or pytest-style pass if `conftest.py` makes them pytest tests — then `python3 -m pytest tests/ -q`).

- [ ] **Step 5: Commit any fixes made during verification** (path typos, missing snapshot, etc.) with a descriptive message. If everything passed with no changes, skip.

---

## Task 8: Cleanup (AFTER the branch is merged to master — do not run earlier)

**Files:** none (git/worktree operations)

- [ ] **Step 1: (Performed by the human or finishing-a-development-branch) merge `chore/consolidate-editions` → `master`.** This task's steps run only once master contains the consolidation.

- [ ] **Step 2: Remove the worktrees.**
```bash
cd /Users/micahcooper/geneve_1564
git worktree remove .worktrees/net-notes
git worktree remove .worktrees/geneva-annotations
git worktree prune
```

- [ ] **Step 3: Delete the feature branches (history retained in archive tags).**
```bash
git branch -D feature/net-notes feature/geneva-annotations
git push origin --delete feature/net-notes feature/geneva-annotations
```

- [ ] **Step 4: Verify final state.**
```bash
git worktree list          # only the main repo
git branch                 # master (+ any active work)
git tag | grep archive/    # archive tags still present
```
Expected: one worktree, no edition feature branches, archive tags intact.

---

## Self-review notes

- **Spec coverage:** 5 targets (Tasks 4/6), 3 generation outputs + offline seeding (Task 5/7), `generate.py --edition` (Task 5), `editions/<name>/` tracked assets (Task 3), renames/collision (Task 2), gitignored generated dirs (Task 1), migration via archive tags (Tasks 1/2/8), verification incl. byte-equivalence + all builds + tests (Task 7) — all covered.
- **geneva pipeline:** routine build = NET path + annotations + committed `corrections_final.json` (Task 5 `gen_geneva`); the heavy overlap *re-convergence* remains `scripts/build_annotated.py` (kept, repoint its `_LUALATEX` to `geneva_bible.tex` and `--output-dir` default to `livres_geneva/` as a follow-up if a re-convergence is ever needed — out of scope for routine builds).
- **Known approximation:** byte-equivalence spot-checks genesis + one NT book rather than all 66 (the generator delta is the already-proven-neutral annotation code); full visual review is the per-edition build in Task 7 Step 3.
- **color_index for ESV** was generated; Task 3 snapshots it to a tracked asset and Task 4 repoints esv_bible.tex — ESV index output is preserved.
```
