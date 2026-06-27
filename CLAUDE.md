# shoob-scraper

A Windows desktop app that scrapes random anime cards from shoob.gg and displays them in a gacha-style UI. Built with Playwright (scraping), Flask (local HTTP server), and pywebview (native window).

## Architecture

```
main.py          Entry point — starts Flask in a background thread, opens pywebview window
app.py           Flask app — routes, job queue, card API, filename parsing
scraper.py       Playwright scraper — fetches card data and image from shoob.gg
templates/       Jinja2 HTML (index.html = gacha draw UI, collection.html = card browser)
static/          CSS and card-back SVG
cards/           Downloaded card images (user data, not in git)
seen.json        Tracks scraped card numbers to avoid duplicates (user data, not in git)
shoob.spec       PyInstaller spec — bundles everything into a single .exe
build.bat        Windows build script
```

### How a draw works

1. User clicks "Draw Card" → `POST /draw` starts a background thread
2. Thread calls `scraper.py` in-process (`asyncio.run(_scraper.run())`) when frozen as .exe
3. Scraper: fetches total card count → picks a random unseen number → navigates to that card → downloads image to `cards/`
4. UI polls `GET /status/<job_id>` every second until done, then flips to reveal the card

### Card filename format

`{CardName}-{AnimeName}-{Tier}-{N}.png`

Example: `Rem-ReZero-T2-1.png`. The trailing `-N` is a collision counter (increments if the same card is drawn again). `parse_filename()` in `app.py` reverses this back to structured data.

### Tier system

T1 (lowest) → T2 → T3 → T4 → T5 → T6 → S (highest). Legacy aliases `R=T1`, `SR=T2`, `SSR=T3` are also recognised.

## Running locally (dev mode)

```bash
pip install -r requirements.txt
playwright install chromium

# Run full app (Flask + pywebview window)
python main.py

# Run scraper only (CLI, downloads one card)
python scraper.py
python scraper.py --headed   # show browser window
```

Flask runs on a random free port. The pywebview window connects to it at `http://127.0.0.1:<port>/`.

## Running tests

```bash
pytest
```

Tests are in `tests/`. They cover `scraper.py` pure functions and all Flask routes in `app.py`. No browser or network required — scraper Playwright calls are not tested here.

## Building the exe

```
build.bat
```

Outputs `shoob.exe` to the repo root. Requires PyInstaller and pywebview installed. The `--distpath .` flag in the spec command puts the exe at root instead of `dist/`.

When frozen (`sys.frozen == True`), the app switches to in-process scraping instead of subprocess, and sets `PLAYWRIGHT_BROWSERS_PATH` to the bundled browsers inside `_MEIPASS`.

## API routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Gacha draw UI |
| POST | `/draw` | Start a card draw job |
| GET | `/status/<job_id>` | Poll job status |
| GET | `/cards/<filename>` | Serve a card image from `cards/` |
| GET | `/api/cards` | Paginated card list (`?q=`, `?tier=`, `?offset=`, `?limit=`) |
| GET | `/collection` | Collection browser UI |

## Cleanup after completing tasks

After finishing any task, delete all Claude-generated artifacts before committing:

```powershell
# Claude workflow artifacts
Remove-Item -Recurse -Force ".playwright-mcp"  -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".superpowers"      -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "docs\superpowers"  -ErrorAction SilentlyContinue

# Build and Python caches
Remove-Item -Recurse -Force "build"             -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist"              -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "__pycache__"       -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".pytest_cache"     -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter "__pycache__" -Directory | Remove-Item -Recurse -Force
```

These paths are already covered by `.gitignore` so they will not be committed even if left behind, but clean them up anyway to keep the working directory tidy.

Do not commit: `shoob.exe`, `build/`, `dist/`, `__pycache__/`, `.pytest_cache/`, `.playwright-mcp/`, `.superpowers/`, `docs/superpowers/`, `cards/`, `seen.json`.
