# Components

Every class is a plain name inside the site stylesheet. Colours come from `tokens/`. Nothing here needs anything outside this folder.

Status meanings (keep them everywhere): PASSED green, DOUBTFUL amber, FAILED red, UNKNOWN slate, UNTESTED blue, n/a grey outline. The word always stays on the colour.

## Site (static documentation) - files in `site/`

| Component | Class / template | Use it for |
|---|---|---|
| Sticky header | `header.top`, `templates/header.html` | brand, menu, search, theme switch |
| Drop-down | `details.dd`, `.dd-menu`, `templates/dropdown.html` | one per top-level folder; opens on hover on wide screens |
| Search | `#q`, `#res`, `search.template.js` | client-side; press `/` to focus, `Esc` to clear |
| Theme switch | `#theme` | light, dark; remembers the choice; follows the system by default |
| Card | `.card`, `templates/card.html` | a page in a section list: title and one-line summary |
| Breadcrumb | `.crumb` | Home / Section / Page |
| On this page | `aside.toc` | shown when a page has three or more second-level headings, hidden under 980 px |
| Pager | `.pager`, `templates/pager.html` | previous and next page |
| Badge | `.badge .b-passed` ... `.b-unknown` | status words in text become coloured badges (outside code) |
| Quote | `blockquote` | a rule or a warning worth pausing on |
| Table | `table` | scrolls sideways inside its box on a phone |

## Breakpoints
900 px: the menu collapses to a burger button. 980 px: the "on this page" list is hidden. Test at 375 px.

## Accessibility
Colour is never the only signal (the status word stays). Focus stays visible. Motion off under `prefers-reduced-motion`. Body text 18 px on the site, line height 1.7, line length about 70 characters.
