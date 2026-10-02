# Tosca Q Hub

One page that pulls Tricentis Tosca questions from every public source into a single searchable feed, plus a curated interview question bank.

## What it does

**Community feed** fetches live, straight from the browser (no server, no API keys):

| Source | API | Notes |
|---|---|---|
| Stack Overflow | Stack Exchange API | 300 requests/day per visitor IP without a key |
| SQA Stack Exchange | Stack Exchange API | same quota as above |
| Reddit | `reddit.com/search.json` | Reddit may throttle anonymous requests |
| GitHub issues | GitHub search API | 10 searches/minute per visitor IP |
| Hacker News | Algolia HN API | |
| DEV | `dev.to/api/articles` (tags `tosca`, `tricentis`) | filtered by your words in the browser |

- Every search includes "tosca", so typing `xscan` searches for Tosca XScan everywhere.
- Results are merged, sorted (recent, best match, votes, answers) and filterable by source, time range and "unanswered only".
- The same question cross-posted on two sites shows once, with an "Also on …" link.
- Noise is dropped: Puccini's opera *Tosca* and the OASIS TOSCA cloud standard.
- Each source's results are cached in `localStorage` for 30 minutes; Refresh bypasses the cache. If a source fails, the last cached copy is shown, otherwise the chip turns red and the rest still load.
- Tricentis docs, Tricentis Community/Academy, YouTube, LinkedIn and Quora have no open API, so they're offered as one-click searches.

**Interview prep**: 30 common Tosca interview questions with short answers, grouped by topic and filterable.

**Saved**: bookmark any question or interview card; kept in this browser's `localStorage`.

## Run it

Open `tosca/index.html` in a browser, or serve the repo root (`python3 -m http.server`) and visit `/tosca/`. With GitHub Pages enabled on this repo it is live at `https://<user>.github.io/galla/tosca/`.

## Add a source

Add an entry to `TQH_SOURCES` in `sources.js` with an async `fetch(query)` that returns items shaped like the others (`id, title, url, author, created, activity, score, answers, answered, tags, excerpt`). The API must allow cross-origin requests (CORS); sites that don't need a small proxy or go in `TQH_ELSEWHERE` as a search link.

## Tests

```bash
pip install playwright
CHROMIUM_PATH=/path/to/chromium python tests/tosca.py   # CHROMIUM_PATH optional
```

29 checks with every API mocked: merging, cross-post de-duplication, noise filter, HTML decoding and injection safety, a failing source, filters and sorting, saved items, interview filters, search query wiring, caching, and no sideways scroll at phone and desktop widths in light and dark themes.
