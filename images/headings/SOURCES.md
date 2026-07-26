# Book-heading artwork — sources & provenance

Per-book headpieces, assigned by canonical division (books in a section share a
headpiece, as early Bibles reused a section-level stock of woodcut bands). Each
is a public-domain source, vectorized with `potrace` (see
`scripts/build_hyphenation.py`'s sibling workflow in `artwork_src/`). All source
works are out of copyright (PD-Old); the vector traces are released the same.

| File | Section (books) | Source |
|------|-----------------|--------|
| `law.pdf` | Law (Genesis–Deuteronomy) | Tetragrammaton woodcut band — existing project asset (`genese_heading`) |
| `history.pdf` | History (Joshua–Esther) | Œuvres de Rabelais, ed. Marty-Laveaux — [Commons](https://commons.wikimedia.org/wiki/File:Abelais_marty-laveaux_02_(page_13_crop).jpg) |
| `wisdom.pdf` | Wisdom (Job–Song of Songs) | Albini, *Il figlio di Grazia*, Milano: Vallardi, 1898 — [Commons](https://commons.wikimedia.org/wiki/File:Albini_-_Il_figlio_di_Grazia,_Milano,_Vallardi,_1898_(page_29_crop).jpg) |
| `prophets.pdf` | Prophets (Isaiah–Malachi) | *Art Treasures and their Preservation* — [Commons](https://commons.wikimedia.org/wiki/File:Art_treasures_and_their_preservation_-_Headpiece.png) |
| `gospels.pdf` | Gospels + Acts | Printer's ornament used by **Richard Field, c.1590s**, from *Shakespeare's Venus and Adonis* (facsimile, Oxford: Clarendon, 1905) — [Commons](https://commons.wikimedia.org/wiki/File:Headpiece_Ornament_Number_8.jpg) |
| `epistles.pdf` | Epistles (Romans–Jude) | *A Study in Colour* headpiece — [Commons](https://commons.wikimedia.org/wiki/File:A_Study_in_Colour_-_A_Study_in_Colour_Headpiece_Chap_2.png) |
| `revelation.pdf` | Revelation | *An Elizabethan Garland* decoration — [Commons](https://commons.wikimedia.org/wiki/File:An_Elizabethan_garland_-_Decoration.png) |

Wiring: `_HEADING_IMAGES` (built from `_SECTION_BOOKS` × `_SECTION_HEADINGS`) in
both `scripts/esv_latex_generator.py` and `scripts/latex_generator.py`.
Regenerate + recompile after any change; the geneva edition must re-converge
(headpieces add opener height → margin-note reflow).
