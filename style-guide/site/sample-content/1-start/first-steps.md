---
title: First steps
summary: A short sample page that shows headings, a list, a table and a code block.
keywords: [start, steps, sample]
---
Read this page in two minutes.

## What you need

1. A computer with Python.
2. This folder.

## What each status means

| Status | Meaning |
|---|---|
| PASSED | the check ran and the result held |
| FAILED | the check ran and the result did not hold |
| DOUBTFUL | the result is not clear either way |
| UNTESTED | no check has been run yet |
| UNKNOWN | there is not enough information to say |

## Run it

```
python build_site.py --src sample-content --out out
```

You should see a line saying how many pages were written. Next: [how a page is written](../2-guides/writing-pages.md).
