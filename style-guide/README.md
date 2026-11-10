# Style guide - a portable dashboard and documentation-site look

Original work by Junaid Iqbal (Byterive), copied into this repo from the project where the first guidebook was built; no third-party code beyond public packages and Google Fonts. Everything needed to recreate one visual style in another project: colours, type, CSS, HTML templates, a Streamlit dashboard kit and a Markdown-to-website builder. **This folder needs nothing from any other project.** Every link inside it points to a file inside it. Only public packages and Google Fonts are used from outside.

## What is inside

| Path | What it is |
|---|---|
| `PROMPT.md` | the prompt to give your AI assistant in the new project |
| `components.md` | every component: class names, when to use it, a snippet |
| `tokens/` | colours, fonts, sizes as JSON and as CSS custom properties |
| `dashboard/` | Streamlit kit: `config.toml` (theme), `ui_style.css`, `ui_helpers.py`, `app_navigation.py`, `page_pattern.py`, `layout.md`, `requirements.txt` |
| `site/` | static site kit: `style.css`, `search.template.js`, `templates/*.html`, `build_site.py`, `content-rules.md`, `sample-content/` |
| `preview/` | open `preview/index.html` in a browser to see the look (dashboard board sample and a built sample site) |

## Reuse in 3 steps

1. Copy this whole folder into the new project (any location).
2. Open your AI assistant in that project and paste the contents of `PROMPT.md`.
3. Answer its one question (brand name, optional accent colour, pages), then check the result at phone width and in dark mode.

## Run the samples (optional)

```
pip install -r dashboard/requirements.txt markdown
# static site from the sample pages
python site/build_site.py --src site/sample-content --out preview/site --brand "Acme Docs"
# dashboard sample (start from the dashboard/ folder so .streamlit/config.toml is found)
cd dashboard && mkdir -p .streamlit && cp config.toml .streamlit/ && python -m streamlit run app_navigation.py
```

## What to replace

The brand name (a build argument), the accent colour if wanted (`tokens/design-tokens.json` and the `--acc` variable in `site/style.css`), the sample pages, the status words if your project uses others (`--status-words`, and the keys in `STATUS_COLOR`). Keep class names and spacing.

## Requirements

Python 3.10 or newer. Packages: `streamlit` and `pandas` (dashboard kit), `markdown` (site builder). Internet access only for the Google Fonts file (Archivo); offline the system sans-serif is used.
