# geneve_1564 — typeset Bible editions

A LaTeX/Python toolkit that builds beautifully typeset PDF Bibles in the visual
tradition of the **Geneva Bible of 1564**, set in [EB Garamond](http://www.georgduffner.at/ebgaramond/)
with LuaLaTeX and the [`scripture`](https://github.com/dcpurton/scripture) package.

This is a fork of [raphink/geneve_1564](https://github.com/raphink/geneve_1564),
whose original goal was a faithful facsimile of the 17th-century French Geneva
Bible. It has been extended into a general pipeline that fetches modern English
translations (ESV and NET) from their APIs and renders them as several distinct,
print-ready editions — while preserving the Geneva aesthetic: centered chapter
headings, decorative drop-cap initials, running heads, and marginal/footnote
apparatus.

## Editions

Each edition is a top-level `<name>.tex` document that `\input`s generated
per-book files. All are two-column KOMA `scrbook` on a 179 × 239 mm page unless
noted.

| Edition | Build target | Text | Distinctive layout | Pages |
|---|---|---|---|---|
| **ESV** | `make esv` → `esv_bible.tex` | ESV | Red-letter (Words of Christ), drop-cap lettrines, footnotes in the outer margin | ~1340 |
| **NET reading** | `make net-reading` → `net_reading.tex` | NET | Clean two-column reading layout | ~1370 |
| **NET notes** | `make net-notes` → `net_notes.tex` | NET | Single column with a wide (55 mm) right gutter ruled for handwritten/digital notes | ~2250 |
| **Geneva** | `make geneva` → `geneva_bible.tex` | NET | NET text + the **1599 Geneva Study Bible** marginal annotations (~15.5k notes; overflow rendered as lettered footnotes), 13 pt | ~2410 |
| **Geneva 1564** | `make geneve-1564` → `geneve_1564.tex` | French (original) | The upstream French facsimile reproduction | — |

`geneve_1564_modern.tex` is a compact A6 modern-French variant carried over from
upstream.

## How it works

Text is fetched from external APIs, cached locally as JSON, converted to
`scripture`-package LaTeX, then compiled with LuaLaTeX.

- **Fetchers** — `esv_fetcher.py` (api.esv.org, token auth), `bible_fetcher.py`
  (labs.bible.org, for NET), `annotation_fetcher.py` (Geneva Study Bible notes
  from StudyLight), `build_red_letter_data.py` (Words-of-Christ spans derived
  from WEB USFM `\wj` markup, since NET has none).
- **Generators** — `esv_latex_generator.py` and `latex_generator.py` turn cached
  HTML/JSON into per-book `.tex`. `build_annotated.py` injects Geneva
  annotations and runs `overlap_detector.py`, an anchor-based pass that demotes
  margin notes to footnotes when the margin can't hold them (the Geneva density
  needs it — see `docs/plans/`).
- **Unified entry point** — `scripts/generate.py --edition esv|net|geneva|all`
  regenerates an edition's book files from the existing caches (offline).

Shared assets: hand-crafted per-edition `editions/<name>/cover.tex` and
`color_index.tex`; fonts in `fonts/`; a locally vendored `scripture.sty`.

## Daily Bible reading plan

The NET editions (**NET reading**, **NET notes**, and **Geneva**) embed a
**2-year, weekday-paced reading plan**, parsed from
`2-Year-Bible-Reading-Plan_LisaNotes.com_.pdf`
([LisaNotes.com](https://lisanotes.com/)) by `scripts/reading_plan_parser.py`.
Each reading is assigned to a calendar date, automatically skipping **weekends**
and **US federal holidays** (including the day after Thanksgiving).

It surfaces in two places:

- A dated **schedule table** (`reading_plan.tex`, generated per edition),
  reachable from the 📖 icon in the page footer.
- In the reading/notes editions, **inline day markers** — each day's reading
  ends at an `rp-<date>` anchor in the text, so you can jump from the schedule
  to exactly where a day's reading stops.

### Setting personal parameters

Two things are meant to be personalized before you generate:

- **Start date** — day 1 of the plan. Default `2026-03-02`. Set it with the
  standalone NET generator:

  ```sh
  python3 scripts/generate_bible.py --start-date 2026-09-01 --output-dir livres_net
  ```

  (The unified `scripts/generate.py` uses the default start date; change the
  `run_net(...)` call there, or use `generate_bible.py` directly, to override
  it.)

- **Personal skip dates** — recurring days to leave unscheduled (birthdays,
  anniversaries, travel). Edit the `_PERSONAL_SKIPS` set in
  `scripts/reading_plan_parser.py`; entries are `(month, day)` tuples applied
  every year:

  ```python
  _PERSONAL_SKIPS = {(2, 24), (2, 27), (3, 6), (6, 23)}
  ```

After changing either, regenerate the edition and recompile (`make net-reading`,
etc.) so the new dates flow into both the schedule table and the inline markers.

## Building

Requirements:

- **LuaLaTeX** (TeX Live / TinyTeX) — LuaLaTeX specifically; XeLaTeX's macOS AAT
  renderer breaks the EB Garamond Initials font.
- **Python 3** with `scripts/requirements.txt` (`requests`, `python-dotenv`,
  `pdfplumber`).
- For **ESV**: an [ESV API](https://api.esv.org/) key in a `.env` file at the
  project root as `ESV_API_KEY=...`. (NET via labs.bible.org needs no key.)

```sh
pip install -r scripts/requirements.txt

# regenerate book files for an edition (offline, from cache)
python3 scripts/generate.py --edition esv        # or net / geneva / all

# compile a single edition (two LuaLaTeX passes)
make esv                # esv / net-reading / net-notes / geneva / geneve-1564
make all-editions       # build every edition
```

Compiled PDFs land at `<name>.pdf` in the project root. `make clean` removes
build artifacts.

## Text sources & licensing

The ESV and NET translations are copyrighted; this repository contains tooling,
not the licensed text (generated `livres_*/` book files and the API caches carry
their respective publishers' terms). Respect the [ESV API](https://api.esv.org/)
and [labs.bible.org](https://labs.bible.org/) terms of use, and the Crossway /
NET Bible copyright and quotation limits, for any PDFs you produce or
distribute. EB Garamond is under the SIL Open Font License.

## Credits

Original project and French Geneva 1564 reproduction by
[Raphaël Pinson](https://github.com/raphink); typeset with Georg Duffner's
[EB Garamond](http://www.georgduffner.at/ebgaramond/) and David Purton's
[`scripture`](https://github.com/dcpurton/scripture) LaTeX package.
