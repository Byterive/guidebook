# How to write the pages (read this first)

**Reader:** a smart adult with no background in the subject. They want to know what a thing is, why it matters, how to do it and how far to trust it.

## Rules

1. **Short plain sentences.** One idea each. No jargon without a definition. Prefer "price" to "quote".
2. **Link every technical word the first time it appears on a page** to the page that explains it. Write the link as a normal Markdown link with a relative path, for example `[drawdown](path-to-the-drawdown-page.md)`. The link carries that page's one-line summary as hover text (the builder does this).
3. **Say what a number means.** Never give a number without its unit and one sentence of meaning. Prefer "about 8 out of 10" to "80.1%" on first use, then give the exact figure in brackets.
4. **Every formula gets three things in this order:** the idea in words; the formula with each symbol explained in plain words; a worked example with numbers the reader can redo on a calculator. Label invented numbers "sample numbers, not real results".
5. **Be honest about doubt.** Use the same status words everywhere (PASSED, FAILED, DOUBTFUL, UNTESTED, UNKNOWN) and say once what each means. Say what a result does not show.
6. **Steps are numbered, one action each, with what the reader should see afterwards.** Give copy-paste commands in code blocks and say which folder to run them from.
7. **No page over 250 lines.** Split it and link the parts.
8. **Never invent facts.** If unsure, write "not known" and say what would settle it.
9. **Explain every key value with one real example** from your own data: what it means in words, the exact figure, where it comes from, and a sentence reading it aloud.

## Frontmatter (every page)

```
---
title: Short plain title (what the reader would search for)
summary: ONE sentence saying what this page tells you
keywords: [a, b, c]
---
```

## Folders

Top-level folders are the menu sections. Put a number in front to set the order (`1-start`, `2-guides`); the number is not shown. File names are lowercase words joined by hyphens.

## Page shapes

- **How-to:** goal in one line, what you need, numbered steps with what you should see, what can go wrong (table: what you see / why / what to do).
- **Term:** one-sentence meaning, why it matters, a worked example, related terms.
- **Result:** the question, the answer in one sentence with its status word, the numbers with units and meaning, what it does not show, how to repeat it.
- **Troubleshooting:** table of symptom, cause, fix.
