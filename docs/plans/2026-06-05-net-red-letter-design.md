# NET Red-Letter (Words of Christ) — Design

**Date:** 2026-06-05
**Status:** Approved direction; pending spec review
**Scope:** `scripts/build_red_letter_data.py`, `scripts/latex_generator.py`, `data/red_letter_verses.json`

## Problem

The NET edition colors Words of Christ ineffectively. Today:

1. `build_red_letter_data.py` parses the WEB (World English Bible) USFM `\wj … \wj*`
   markers and records, per book/chapter, **which verses** contain any of Jesus's
   words: `{book: {chapter: [verse_nums]}}`.
2. For each flagged verse, `_apply_red_letter_quotes()` scans that verse **in
   isolation** for TeX double-quote pairs ``` ``…'' ``` and wraps them in
   `\redletteron … \redletteroff`.

This breaks on the most common case — a quotation that spans multiple verses.
NET (like normal English) opens the quote once and does not repeat it on
continuation verses. Example, Matthew 5 (Sermon on the Mount):

```
\vs{3} \redletteron ``Blessed are the poor in spirit…belongs to them.\redletteroff
\vs{4} Blessed are those who mourn, for they will be comforted.        ← NOT red
\vs{5} Blessed are the meek, for they will inherit the earth.          ← NOT red
```

Verses 4–22 are correctly **flagged** in the data, but have no opening quote, so
the per-verse scan colors nothing. Almost the entire discourse renders black.

## Constraints / data reality

- The free NET text (labs.bible.org API) and the local NET USFM (`data/engnet_usfm`)
  contain **no** red-letter markup (verified: 0 `\wj`).
- The **only** source of Words-of-Christ information is the WEB USFM `\wj` markers
  (`data/engweb_usfm`), a *different* translation.
- Word-by-word alignment between WEB and NET is unreliable (different wording) and
  is explicitly **out of scope** — it would introduce coloring errors.
- **NET's own quotation marks are ground truth for where the quote is in NET.**
  WEB's `\wj` tells us *which* of those quoted spans are Jesus, and whether a
  verse is entirely His words. Combining the two yields word-accurate red-letter
  for the NET text with no cross-translation guessing.

NET quotation conventions (verified, American style, distinct codepoints):

| Mark | Codepoint | TeX | Role |
|------|-----------|-----|------|
| `"`  | U+201C | ``` `` ``` | open double (primary speech) |
| `"`  | U+201D | `''` | close double |
| `'`  | U+2018 | `` ` `` | open single (nested quote) |
| `'`  | U+2019 | `'` | close single **and apostrophe** |

Nesting alternates double → single → double. Verified real cases:
- 2-level: `"It is written, 'Man does not live…'"` (Mt 4:4) — Jesus quoting Scripture.
- 3-level: `"‘The Lord said to my lord, "Sit at my right hand…"'?"` (Mt 22:44).
- Mixed speaker in one verse: `they answered, "We don't know." …he said, "Neither…"` (Mt 21:27).

## Design

### Key rule (nested quotes)

Track **double-quote nesting depth** only. Red turns **on** when a *top-level*
double quote that WEB flags as Jesus opens; red turns **off** only when the depth
returns to the level at which that quote opened. Consequences:

- Nested single quotes (`` ` ``…`'`) are always inside the outer double → stay red.
- Apostrophes are single (U+2019) → never affect double-depth → ignored, no
  apostrophe-vs-quote disambiguation needed.
- Inner (3rd-level) double quotes raise depth and lower it again without ever
  returning to the open level → stay red. Naive matching would break here.

### Component 1 — Enriched data builder (`build_red_letter_data.py`)

Replace the verse-number list with a per-verse descriptor derived from WEB by
tracking double-quote depth through each verse's `\wj`-aware text:

```json
{
  "matthew": {
    "5": {
      "3": {"opens": [true],  "starts_in_jesus": false},
      "4": {"opens": [],      "starts_in_jesus": true}
    }
  }
}
```

- `opens`: one boolean per **top-level** double-quote *open* in the verse, in
  order; `true` ⇔ that quote begins Jesus's words (the `"` lies inside a `\wj`
  span in WEB). Handles mixed-speaker verses (Mt 21:27 → `[false, true]`).
- `starts_in_jesus`: the verse text begins already inside an open `\wj` quote
  (a continuation verse such as Mt 5:4 → `opens: []`, `starts_in_jesus: true`).

Builder algorithm per verse: strip WEB `\w …\w*` / `\+w …\+w*` word markup, walk
the text tracking double-quote depth and `\wj` membership; for each depth `0→1`
open, append `(inside \wj)` to `opens`; set `starts_in_jesus` if the first content
character is inside `\wj` with no preceding top-level open. Versification maps WEB
verse *n* → NET verse *n* (unchanged from today).

Backward-compat: bump an explicit `"_format": 2` key; the loader handles both.

### Component 2 — Chapter-level state machine (`latex_generator.py`)

Replace `_apply_red_letter_quotes(text)` with a renderer that threads state across
a chapter's verses (the verse loop in `generate_book_tex` already iterates a
chapter at a time). State carried across verses:

- `in_jesus: bool` — currently inside Jesus's words
- `double_depth: int` — current double-quote nesting depth
- `jesus_open_depth: int|None` — depth at which the active Jesus quote opened

Per verse (`desc` = descriptor, or `None` if unflagged):

1. **Boundary reconcile.** If `desc is None`: if `in_jesus`, emit `\redletteroff`,
   clear `in_jesus`; render plain. (Trust the flag: Jesus stopped.) Reset
   `double_depth` to 0 at chapter end.
2. If `in_jesus` carried in (continuation) **or** `desc.starts_in_jesus`: emit
   `\redletteron` at verse start and set `in_jesus=True` (so the verse number
   stays black and the body is red).
3. Walk the verse's TeX text:
   - on ``` `` ``` (open double): if `not in_jesus`, consult `opens[k]` (k-th
     top-level open); if Jesus, emit `\redletteron`, `in_jesus=True`,
     `jesus_open_depth=double_depth`. Then `double_depth += 1`.
   - on `''` (close double): `double_depth -= 1`; if `in_jesus and
     double_depth == jesus_open_depth`, emit `\redletteroff`, clear `in_jesus`.
4. **Verse end.** If `in_jesus` still true, emit `\redletteroff` (keeps the next
   verse number black); the carried `in_jesus` re-opens it at the next verse.

This reproduces the proven ESV per-verse `\redletteron … \redletteroff` pattern:
words red, verse numbers black, red flowing across verse and paragraph boundaries.
`\redletteron`/`\redletteroff` are the scripture package's declarative color
switch, so repeated toggling is safe.

Integration point: keep the existing call sites (verse 1 / lettrine path and the
normal verse path), but pass a per-chapter state object instead of calling the
stateless helper. `_is_red_letter` is replaced by descriptor lookup.

### Edge cases

- **Apostrophes** (`it's`, `Jesus'`): single U+2019, ignored. No effect on color.
- **3rd-level inner double**: depth tracking keeps it red (validated: Mt 22:44, 26:18).
- **Mixed-speaker verse**: `opens` flags disambiguate (Mt 21:27 → `[false,true]`).
- **Flagged verse, no marks, not continuation** (shouldn't occur): `opens` empty,
  `in_jesus` false → renders black. Safe fallback; emit a build-time warning.
- **WEB/NET versification mismatch**: colors what aligns; never crashes.
- **Unbalanced double quotes within a chapter** (data error): clamp `double_depth`
  at 0 on close; force `\redletteroff` at chapter end if still `in_jesus`.

## Testing

- **Builder unit tests**: feed synthetic WEB USFM snippets (full verse, leading
  frame, trailing frame, mixed speaker, nested) → assert descriptor output.
- **Renderer unit tests** (pure string, no LaTeX): drive the state machine over
  crafted chapter verse lists; assert `\redletteron`/`\redletteroff` placement for:
  Sermon continuation (Mt 5:3–6), leading frame (Mt 4:10), Scripture nesting
  (Mt 4:4), 3rd-level nesting (Mt 22:44), mixed speaker (Mt 21:27), and
  balanced toggles overall.
- **Integration**: regenerate NET Matthew/John from cache; assert every flagged
  verse contributes red and toggles are balanced per chapter.
- **Visual**: compile a Matthew 5 / John 14 snippet, render to PNG, eyeball.

## Migration

- Regenerate `data/red_letter_verses.json` via `build_red_letter_data.py`
  (force-add; `data/` is gitignored).
- Regenerate affected NET books and recompile on the NET branches
  (`feature/net-notes`, `feature/geneva-annotations`) — not on master.

## Out of scope

- Word-level WEB→NET alignment.
- Red-letter for books beyond Matthew, Mark, Luke, John, Acts, Revelation.
- Changing the ESV path (already correct).
