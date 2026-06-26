# Shoob Card Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI script that downloads one random card image per run from shoob.gg/cards, tracking used random numbers in seen.json to avoid repeats.

**Architecture:** Single `scraper.py` file containing pure utility functions (testable) and async Playwright functions (browser-driven). The main orchestrator wires them together: fetch total → pick random number → navigate to card → download image → save filename with collision-safe suffix.

**Tech Stack:** Python 3.8+, Playwright (async API, Chromium), pytest, stdlib only (json, math, random, re, urllib)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `scraper.py` | Create | All logic: config, utilities, playwright scraper, orchestrator |
| `tests/test_scraper.py` | Create | Unit tests for all pure functions |
| `tests/__init__.py` | Create | Makes tests/ a Python package |
| `requirements.txt` | Create | Declares playwright + pytest |
| `.gitignore` | Create | Excludes cards/, seen.json, __pycache__, .playwright-mcp |

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `tests/__init__.py`
- Create: `scraper.py`

- [ ] **Step 1: Create `requirements.txt`**

```
playwright
pytest
```

- [ ] **Step 2: Create `.gitignore`**

```
cards/
seen.json
__pycache__/
.playwright-mcp/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create empty `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `scraper.py` with imports and config skeleton**

```python
import argparse
import asyncio
import json
import math
import random
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright, Page

BASE_URL = "https://shoob.gg/cards"
OUTPUT_DIR = "./cards"
SEEN_FILE = "./seen.json"
CARDS_PER_PAGE = 15
```

- [ ] **Step 5: Install dependencies**

Run:
```
pip install -r requirements.txt
playwright install chromium
```

Expected: No errors. `playwright` and `pytest` installed, Chromium browser binary downloaded.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt .gitignore tests/__init__.py scraper.py
git commit -m "chore: project scaffold"
```

---

### Task 2: Seen tracker (TDD)

**Files:**
- Modify: `scraper.py` — add `load_seen`, `save_seen`, `generate_unique_number`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write failing tests in `tests/test_scraper.py`**

```python
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scraper import load_seen, save_seen, generate_unique_number


def test_load_seen_missing_file(tmp_path):
    assert load_seen(str(tmp_path / "seen.json")) == []


def test_load_seen_existing_file(tmp_path):
    p = tmp_path / "seen.json"
    p.write_text("[1, 2, 3]")
    assert load_seen(str(p)) == [1, 2, 3]


def test_save_seen(tmp_path):
    p = tmp_path / "seen.json"
    save_seen([10, 20], str(p))
    assert json.loads(p.read_text()) == [10, 20]


def test_generate_unique_not_in_seen():
    seen = [1, 2, 3]
    result = generate_unique_number(seen, 100)
    assert result not in seen
    assert 1 <= result <= 100


def test_generate_unique_all_used_exits():
    with pytest.raises(SystemExit):
        generate_unique_number([1, 2, 3], 3)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `pytest tests/test_scraper.py -v`

Expected: `ImportError` — `load_seen` not yet defined.

- [ ] **Step 3: Add seen tracker functions to `scraper.py`** (append after config block)

```python
def load_seen(path: str = SEEN_FILE) -> list:
    p = Path(path)
    if not p.exists():
        return []
    return json.loads(p.read_text())


def save_seen(seen: list, path: str = SEEN_FILE) -> None:
    Path(path).write_text(json.dumps(seen))


def generate_unique_number(seen: list, total: int) -> int:
    seen_set = set(seen)
    if len(seen_set) >= total:
        print("All cards downloaded.")
        sys.exit(0)
    while True:
        n = random.randint(1, total)
        if n not in seen_set:
            return n
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/test_scraper.py -v`

Expected:
```
PASSED tests/test_scraper.py::test_load_seen_missing_file
PASSED tests/test_scraper.py::test_load_seen_existing_file
PASSED tests/test_scraper.py::test_save_seen
PASSED tests/test_scraper.py::test_generate_unique_not_in_seen
PASSED tests/test_scraper.py::test_generate_unique_all_used_exits
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add seen-number tracker"
```

---

### Task 3: Page/index calculator (TDD)

**Files:**
- Modify: `scraper.py` — add `calculate_page_and_index`
- Modify: `tests/test_scraper.py` — add tests

- [ ] **Step 1: Append failing tests to `tests/test_scraper.py`**

Add this import at the top of the test file (update existing import line):
```python
from scraper import load_seen, save_seen, generate_unique_number, calculate_page_and_index
```

Append these test functions:
```python
def test_first_card():
    assert calculate_page_and_index(1, 15) == (1, 0)


def test_last_card_on_page_one():
    assert calculate_page_and_index(15, 15) == (1, 14)


def test_first_card_on_page_two():
    assert calculate_page_and_index(16, 15) == (2, 0)


def test_card_thirty():
    assert calculate_page_and_index(30, 15) == (2, 14)


def test_card_forty_six():
    # page 4, first slot: cards 1-15=p1, 16-30=p2, 31-45=p3, 46-60=p4
    assert calculate_page_and_index(46, 15) == (4, 0)
```

- [ ] **Step 2: Run tests to confirm new ones fail**

Run: `pytest tests/test_scraper.py -v`

Expected: `ImportError` on `calculate_page_and_index`.

- [ ] **Step 3: Add `calculate_page_and_index` to `scraper.py`** (append after seen tracker functions)

```python
def calculate_page_and_index(number: int, cards_per_page: int = CARDS_PER_PAGE) -> tuple:
    page = math.ceil(number / cards_per_page)
    index = (number - 1) % cards_per_page
    return page, index
```

- [ ] **Step 4: Run all tests to confirm they pass**

Run: `pytest tests/test_scraper.py -v`

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add page/index calculator"
```

---

### Task 4: Filename utilities (TDD)

**Files:**
- Modify: `scraper.py` — add `sanitize_component`, `build_filename`
- Modify: `tests/test_scraper.py` — add tests

- [ ] **Step 1: Update import line in `tests/test_scraper.py`**

```python
from scraper import (
    load_seen, save_seen, generate_unique_number,
    calculate_page_and_index,
    sanitize_component, build_filename,
)
```

- [ ] **Step 2: Append failing tests to `tests/test_scraper.py`**

```python
def test_sanitize_spaces():
    assert sanitize_component("No Game No Life") == "No-Game-No-Life"


def test_sanitize_special_chars():
    assert sanitize_component("Re:Zero") == "ReZero"


def test_sanitize_ampersand():
    # & removed → double space → single hyphen
    assert sanitize_component("Chitoge & Raku") == "Chitoge-Raku"


def test_sanitize_multiple_spaces():
    assert sanitize_component("My   Hero") == "My-Hero"


def test_sanitize_leading_trailing():
    assert sanitize_component("  Naruto  ") == "Naruto"


def test_build_filename_first(tmp_path):
    result = build_filename("Rem", "ReZero", "T3", str(tmp_path), ".png")
    assert result == tmp_path / "Rem-ReZero-T3-1.png"


def test_build_filename_collision(tmp_path):
    (tmp_path / "Rem-ReZero-T3-1.png").touch()
    result = build_filename("Rem", "ReZero", "T3", str(tmp_path), ".png")
    assert result == tmp_path / "Rem-ReZero-T3-2.png"


def test_build_filename_multiple_collisions(tmp_path):
    (tmp_path / "Rem-ReZero-T3-1.png").touch()
    (tmp_path / "Rem-ReZero-T3-2.png").touch()
    result = build_filename("Rem", "ReZero", "T3", str(tmp_path), ".png")
    assert result == tmp_path / "Rem-ReZero-T3-3.png"


def test_build_filename_nonexistent_dir(tmp_path):
    subdir = tmp_path / "cards"
    result = build_filename("Rem", "ReZero", "T3", str(subdir), ".png")
    assert result == subdir / "Rem-ReZero-T3-1.png"
```

- [ ] **Step 3: Run tests to confirm new ones fail**

Run: `pytest tests/test_scraper.py -v`

Expected: `ImportError` on `sanitize_component`.

- [ ] **Step 4: Add filename utilities to `scraper.py`** (append after calculator function)

```python
def sanitize_component(name: str) -> str:
    name = re.sub(r'[^A-Za-z0-9 \-]', '', name)
    name = re.sub(r'\s+', '-', name.strip())
    name = re.sub(r'-+', '-', name)
    return name


def build_filename(card_name: str, anime_name: str, tier: str, output_dir: str, ext: str) -> Path:
    output_dir = Path(output_dir)
    base = f"{card_name}-{anime_name}-{tier}"
    pattern = re.compile(rf"^{re.escape(base)}-(\d+){re.escape(ext)}$")
    max_n = 0
    if output_dir.exists():
        for f in output_dir.iterdir():
            m = pattern.match(f.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
    return output_dir / f"{base}-{max_n + 1}{ext}"
```

- [ ] **Step 5: Run all tests to confirm they pass**

Run: `pytest tests/test_scraper.py -v`

Expected: `19 passed`

- [ ] **Step 6: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add filename sanitizer and collision-safe builder"
```

---

### Task 5: Playwright scraper + image downloader

**Files:**
- Modify: `scraper.py` — add `fetch_total`, `get_card_info`, `download_image`

Note: These functions require a live browser — no unit tests. Verify manually in Task 6.

- [ ] **Step 1: Append `fetch_total` to `scraper.py`**

```python
async def fetch_total(page: Page) -> int:
    await page.goto(BASE_URL)
    total_el = page.locator("text=/Total \\d+/").first()
    await total_el.wait_for()
    text = await total_el.inner_text()
    m = re.search(r'Total (\d+)', text)
    if not m:
        print("Error: could not parse total card count from page.")
        sys.exit(1)
    return int(m.group(1))
```

- [ ] **Step 2: Append `get_card_info` to `scraper.py`**

Breadcrumb structure on detail page: `ol li` list —
- index 0: "Cards" (ignored)
- index 1: "Tier 3" → tier formatted as "T3"
- index 2: anime name (plain text, e.g. "Nisekoi")
- index 3: card name (e.g. "Chitoge & Raku")

Card image selector: `img.img-fluid` (first match on page)

```python
async def get_card_info(page: Page, card_page: int, card_index: int) -> dict:
    await page.goto(f"{BASE_URL}?page={card_page}")
    await page.locator('a[href^="/cards/info/"]').first().wait_for()
    links = page.locator('a[href^="/cards/info/"]')
    await links.nth(card_index).click()
    await page.locator('ol li').nth(3).wait_for()
    items = page.locator('ol li')
    tier_text = await items.nth(1).inner_text()
    anime_name = await items.nth(2).inner_text()
    card_name = await items.nth(3).inner_text()
    tier_num = re.search(r'\d+', tier_text)
    tier = f"T{tier_num.group()}" if tier_num else sanitize_component(tier_text)
    img = page.locator('img.img-fluid').first()
    await img.wait_for()
    image_url = await img.get_attribute('src')
    return {
        'card_name': card_name.strip(),
        'anime_name': anime_name.strip(),
        'tier': tier,
        'image_url': image_url,
    }
```

- [ ] **Step 3: Append `download_image` to `scraper.py`**

```python
def download_image(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(dest))
```

- [ ] **Step 4: Run unit tests to confirm nothing is broken**

Run: `pytest tests/test_scraper.py -v`

Expected: `19 passed` (same as before — no new tests, just verifying no regressions)

- [ ] **Step 5: Commit**

```bash
git add scraper.py
git commit -m "feat: add playwright scraper and image downloader"
```

---

### Task 6: Main orchestrator + end-to-end verification

**Files:**
- Modify: `scraper.py` — add `main()` and `__main__` block

- [ ] **Step 1: Append `main()` and entry point to `scraper.py`**

```python
async def main() -> None:
    parser = argparse.ArgumentParser(description="Download a random shoob.gg card.")
    parser.add_argument('--headed', action='store_true', help='Show browser window')
    args = parser.parse_args()

    seen = load_seen()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed)
        page = await browser.new_page()
        try:
            total = await fetch_total(page)
            number = generate_unique_number(seen, total)
            card_page, card_index = calculate_page_and_index(number)

            info = await get_card_info(page, card_page, card_index)

            card_name = sanitize_component(info['card_name'])
            anime_name = sanitize_component(info['anime_name'])
            tier = info['tier']

            ext = Path(urllib.parse.urlparse(info['image_url']).path).suffix or '.png'
            dest = build_filename(card_name, anime_name, tier, OUTPUT_DIR, ext)

            download_image(info['image_url'], dest)

            seen.append(number)
            save_seen(seen)

            print(f"Downloaded: {dest.name}")
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
```

- [ ] **Step 2: Run a smoke test with headed mode**

Run: `python scraper.py --headed`

Expected:
- Browser window opens
- Navigates to shoob.gg/cards, fetches total
- Navigates to a random page, clicks a card
- Downloads the image into `./cards/`
- Prints e.g. `Downloaded: Rem-ReZero-T3-1.png`
- Browser closes

Verify:
- `cards/` directory created with one `.png` file
- `seen.json` contains one integer
- Filename matches format `{CardName}-{AnimeName}-T{N}-1.{ext}`

- [ ] **Step 3: Run a second time to verify collision-increment and seen tracking**

Run: `python scraper.py --headed`

Expected:
- A different card is picked (different random number)
- If by chance same card name, filename suffix increments to `-2`
- `seen.json` now has two integers

- [ ] **Step 4: Run unit tests one final time**

Run: `pytest tests/test_scraper.py -v`

Expected: `19 passed`

- [ ] **Step 5: Commit**

```bash
git add scraper.py
git commit -m "feat: add main orchestrator — scraper complete"
```
