"""Optional browser quality check for a built site (NOT part of `unittest`; needs the dev-only `playwright` package and Chrome or Edge).

usage: python tests/browser_check.py <built site folder> [--max-pages N]
Checks every page at phone width (375 px) and in dark mode:
  no sideways page scroll | burger menu shown, menu collapsed | text contrast (>= 4.5) for body, muted text, links, badges
  visible focus after Tab | `/` focuses search | title and summary present
Exit code 1 if any check fails. Prints one line per failure and a summary."""
import argparse
import sys
from pathlib import Path

JS_CONTRAST = """
() => {
  const parse = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); const p = m[1].split(',').map(Number); return {r:p[0], g:p[1], b:p[2], a:p.length>3?p[3]:1}; };
  const lum = c => { const f = v => { v/=255; return v<=0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }; return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const bgOf = el => { let e = el; while (e) { const c = parse(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; e = e.parentElement; } return {r:255,g:255,b:255,a:1}; };
  const ratio = el => { const fg = parse(getComputedStyle(el).color), bg = bgOf(el); const a = lum(fg), b = lum(bg); return (Math.max(a,b)+0.05)/(Math.min(a,b)+0.05); };
  const out = [];
  const probe = (name, sel) => { const el = document.querySelector(sel); if (el) out.push([name, Math.round(ratio(el)*100)/100]); };
  probe('body text', 'main p, main li');
  probe('muted text', '.crumb');
  probe('link', 'main a');
  probe('card summary', '.card span');
  document.querySelectorAll('.badge').forEach(b => out.push(['badge ' + b.textContent, Math.round(ratio(b)*100)/100]));
  return out;
}
"""


def pages(root: Path, limit):
    out = sorted(p for p in root.rglob("*.html"))
    return out[:limit] if limit else out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--max-pages", type=int, default=0)
    ap.add_argument("--engine", choices=("chromium", "firefox"), default="chromium")
    a = ap.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed: browser check skipped", file=sys.stderr)
        return 3
    root = Path(a.site).resolve()
    fails, checked = [], 0
    with sync_playwright() as pw:
        browser = None
        if a.engine == "firefox":
            try:
                browser = pw.firefox.launch()
            except Exception:
                print("Firefox is not installed for playwright (python -m playwright install firefox): browser check skipped", file=sys.stderr)
                return 3
        else:
            for ch in ("chrome", "msedge"):
                try:
                    browser = pw.chromium.launch(channel=ch)
                    break
                except Exception:
                    continue
        if browser is None:
            print("no Chrome or Edge found: browser check skipped", file=sys.stderr)
            return 3
        for scheme in ("light", "dark"):
            ctx = browser.new_context(viewport={"width": 375, "height": 800}, color_scheme=scheme)
            for f in pages(root, a.max_pages):
                page = ctx.new_page()
                page.goto(f.as_uri())
                rel = f.relative_to(root).as_posix()
                checked += 1
                tag = f"[{scheme} 375px] {rel}"
                if page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
                    fails.append(f"{tag}: sideways page scroll (scrollWidth {page.evaluate('document.documentElement.scrollWidth')})")
                if not page.is_visible("#burger") or page.is_visible("nav.menu"):
                    fails.append(f"{tag}: menu not collapsed behind the burger button")
                if not (page.title() or "").strip():
                    fails.append(f"{tag}: no <title>")
                if scheme == "dark" and page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(251, 251, 253)":
                    fails.append(f"{tag}: dark mode did not change the page background")
                for name, ratio in page.evaluate(JS_CONTRAST):
                    if ratio < 4.5:
                        fails.append(f"{tag}: contrast {ratio} < 4.5 for {name}")
                page.keyboard.press("Tab")
                if not page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== 'none'; })()"):
                    fails.append(f"{tag}: first Tab stop has no visible focus")
                page.mouse.click(5, 790)
                page.keyboard.press("/")
                if page.evaluate("document.activeElement && document.activeElement.id") != "q":
                    fails.append(f"{tag}: '/' does not focus search")
                page.close()
            ctx.close()
        browser.close()
    for line in fails:
        print("FAIL " + line)
    print(f"{checked} page checks, {len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
