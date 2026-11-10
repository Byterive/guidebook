# Dashboard layout

## Page anatomy (top to bottom)

1. **Header** (dark bar, set by `ui_style.css`): page names as tabs; a named group is a drop-down (see `app_navigation.py`). Always on top, never a left menu.
2. **Title** (`st.title`): short noun phrase in condensed bold type.
3. **Lede**: one sentence in `sg-lede` that says what the page shows. Max 60 characters per line.
4. **Metrics row**: 3 to 5 `st.metric` in columns. Numbers carry their unit.
5. **Main block**: one of
   - **Board** (`sg-board`): a dark table of split-flap cells for a live list where the status is the point (a service, a job, a check). Max about 12 rows.
   - **Matrix** (`sg-matrix`): counts per group and status, each count in its status colour.
   - **Table** (`st.dataframe` + `style_status`): detail rows the reader will sort and filter.
6. **Notes**: `st.caption` naming the data source and its age. Missing data is shown as missing, never as zero.

## Sidebar
App name, data-freshness dot (`dot`), short captions, at most one action button. Nothing else.

## Colour use
- Page grey, panel light grey, ink near-black (all in `config.toml`). The dark header and board use the board colours in `../tokens/design-tokens.json`.
- Status colours mean the same everywhere: PASSED green, DOUBTFUL amber, FAILED red, UNKNOWN slate, UNTESTED blue. The word always stays on the cell.
- Amber text on the board marks "running".

## Type
Archivo (variable width) from Google Fonts, set in `config.toml`; headings use the condensed width (62 to 75 percent) from `ui_style.css`. Offline it falls back to the system sans.

## Motion
One flip-in of the board cells on load (0.38 s). Switched off for users who ask for reduced motion.

## Width and spacing
Wide layout (`layout="wide"`). Board table scrolls sideways inside its box on a phone (minimum width 760 px) so the page itself never scrolls sideways.

## Checks before you ship a page
Phone width 375 px (no sideways page scroll), contrast of every status cell, keyboard focus visible, no colour-only meaning.
