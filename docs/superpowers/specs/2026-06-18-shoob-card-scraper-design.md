# Shoob Card Scraper — Design Spec
**Date:** 2026-06-18

## Overview

A Python CLI script that downloads one random card image per run from shoob.gg/cards. It tracks previously-used random numbers to avoid re-downloading the same card position, and saves images locally with a structured filename.

## Architecture

Single-file script: `scraper.py`
Supporting files (auto-generated at runtime):
- `seen.json` — tracks used random numbers
- `cards/` — output directory for downloaded images

## Run Flow

1. Launch Playwright headless Chromium browser
2. Navigate to `https://shoob.gg/cards`, wait for page to fully load
3. Parse the "TOTAL XXXXX" text to get the total card count
4. Load `seen.json` (create empty array if missing)
5. Generate a random integer between 1 and total (inclusive) not already in `seen.json`; if all numbers exhausted, print "All cards downloaded" and exit
6. Calculate target page: `page = ceil(number / 15)`, card index on page: `index = (number - 1) % 15`
7. Navigate to `https://shoob.gg/cards?page=<page>`, wait for cards to load
8. Click the card at position `index` (0-based) on the page
9. Wait for the card detail page to load; scrape: card name, anime name, tier
10. Find and download the high-resolution card image
11. Build filename: `CardName-AnimeName-Tier-<N>.ext` where N starts at 1 and increments if a file with that base already exists in `./cards/`
12. Save image to `./cards/`
13. Append the random number to `seen.json` (only on successful download)

## Data Storage

**`seen.json`** — flat JSON array of integers:
```json
[42, 1337, 8901]
```
Written only after a successful download so failed runs don't consume a number.

**`./cards/`** — flat directory of image files named:
```
Rem-ReZero-SSR-1.png
Rem-ReZero-SSR-2.png   ← collision increment
Naruto-Naruto-R-1.png
```

## Filename Sanitization

Before building the filename, each component (card name, anime name, tier) is sanitized:
- Spaces → hyphens
- Characters not in `[A-Za-z0-9\-]` → removed
- Multiple consecutive hyphens → collapsed to one

Example: `"Re:Zero"` → `"ReZero"`, `"No Game No Life"` → `"No-Game-No-Life"`

## Filename Collision Handling

Scan `./cards/` for files matching `CardName-AnimeName-Tier-*.ext`. Find the maximum numeric suffix, add 1. First file gets suffix `1`.

## Error Handling

| Scenario | Behavior |
|---|---|
| Total count unparseable | Exit with clear error message |
| All numbers already seen | Print "All cards downloaded" and exit cleanly |
| Card detail page fails to load | Exit with error; number not saved to seen.json |
| Image download fails | Exit with error; number not saved to seen.json |
| cards/ dir missing | Auto-created on first run |
| seen.json missing | Treated as empty array |

## Dependencies

- Python 3.8+
- `playwright` (`pip install playwright && playwright install chromium`)
- Stdlib only beyond playwright: `json`, `random`, `math`, `pathlib`, `re`, `urllib`

## Configuration (top of scraper.py)

```python
BASE_URL = "https://shoob.gg/cards"
OUTPUT_DIR = "./cards"
SEEN_FILE = "./seen.json"
CARDS_PER_PAGE = 15
```

## Usage

```bash
python scraper.py           # normal run (headless)
python scraper.py --headed  # show browser window (debug)
```
