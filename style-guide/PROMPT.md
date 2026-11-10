# Prompt for the AI assistant in the new project

Copy everything below the line into your assistant.

---

ROLE
You build a dashboard and/or documentation website for this project in the visual style stored in the folder `style-guide/` (it is inside this project's folder; if it is somewhere else, I will tell you the path). Use ONLY the files in that folder as your source for colours, fonts, CSS, HTML templates and patterns. Do not look for style information anywhere else, and do not invent colours, fonts or spacing.

READ FIRST (in this order)
1. `style-guide/README.md`
2. `style-guide/components.md`
3. `style-guide/tokens/design-tokens.json` and `tokens/tokens.css`
4. For a Streamlit dashboard: `style-guide/dashboard/layout.md`, then the files in `dashboard/`.
5. For a documentation website: `style-guide/site/content-rules.md`, then the files in `site/`.
6. Open `style-guide/preview/index.html` to see the intended look (or read the HTML).

DECIDE
- Which of the two do I need? If I said "dashboard", use `dashboard/`; if "site", "docs" or "help pages", use `site/`; if both, do both. If my project uses another framework (React, Flask, plain HTML), keep the tokens, class names, spacing and component shapes and port the CSS and templates by hand.
- Ask me ONE question, only if I have not already told you: the brand name, an accent colour (optional; default is the one in the tokens), and the list of pages or sections. Then continue without more questions; list your assumptions.

BUILD
- Streamlit: copy `dashboard/config.toml` to `.streamlit/config.toml` in the app folder, copy `ui_style.css` and `ui_helpers.py` next to your pages, build the navigation like `app_navigation.py` (tabs in the top header, a named group becomes a drop-down), and write each page like `page_pattern.py` (title, one-sentence lede, metrics row, then a board, matrix or table, then a source caption). Use `status_tag`, `status_chip`, `flap` and `style_status` for status words.
- Site: write the pages as Markdown with a frontmatter block (title, summary, keywords) following `site/content-rules.md`, put them in sub-folders (each top-level folder becomes a drop-down), then run `python style-guide/site/build_site.py --src <pages folder> --out <output folder> --brand "<name>"`. Open the output `index.html`.
- Use my real data and wording. Keep sample text only where I gave you nothing. Never show a missing value as zero.

RULES
- Status colours keep their meaning (PASSED green, DOUBTFUL amber, FAILED red, UNKNOWN slate, UNTESTED blue), and the status word always stays on the colour: colour is never the only signal. If my project has other status names, map them onto these five and say how.
- Keep every link relative and inside the files you generate. Do not edit `style-guide/` itself; put changes in my project's own files.
- Do not add dependencies beyond `streamlit`, `pandas` (dashboard) and `markdown` (site) without asking.

CHECK BEFORE YOU REPORT
1. Phone width 375 px: no sideways page scroll; the header menu collapses; tables scroll inside their box.
2. Dark mode (site) and the board contrast (dashboard) are readable.
3. Keyboard: tab order is sensible, focus is visible, `/` focuses search on the site.
4. Every page has a title and a one-sentence summary; every number has a unit and a meaning.
5. Run the project's tests if there are any; for Streamlit, render each page once and confirm no exception.

REPORT
List which `style-guide/` files you used, what you replaced (brand, accent, pages, status names), what you could not do and why, and the exact command to start the dashboard or rebuild the site.
