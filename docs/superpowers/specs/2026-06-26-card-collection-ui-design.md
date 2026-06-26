# Card Collection UI — Design Spec
Date: 2026-06-26

## Overview

A separate `/collection` page that displays every card the user has pulled (images in `cards/`), with real-time search, tier filtering, newest-first ordering, infinite scroll pagination, and a click-to-preview modal. Visually consistent with the existing Shoob Gacha dark/gold TCG theme.

---

## Backend

### New API endpoint: `GET /api/cards`

**Query parameters:**

| Param  | Type   | Default | Description |
|--------|--------|---------|-------------|
| q      | string | ""      | Search string — matched against character name and anime (case-insensitive substring) |
| tier   | string | ""      | Filter to a single tier (e.g. `T1`, `T2`, `T3`, `SSR`, `SR`, `R`); omit or empty for all |
| offset | int    | 0       | Pagination offset |
| limit  | int    | 20      | Page size |

**Logic:**
1. `Path("cards/").iterdir()` — list all `.png` files
2. Parse each with the existing `parse_filename()` function
3. Sort by the numeric suffix (last `-N` token in filename) descending — newest pull first
4. Apply `q` filter: `q.lower()` must appear in `name.lower()` or `anime.lower()`
5. Apply `tier` filter: exact case-insensitive match against parsed tier
6. Slice `[offset : offset + limit]`
7. Return JSON:
```json
{
  "cards": [
    { "name": "Yuna", "anime": "Yuusha ga Shinda", "tier": "T2", "image": "Yuna-..." }
  ],
  "total": 42,
  "has_more": true
}
```

### New route: `GET /collection`

Renders `templates/collection.html`. No data passed — the page fetches via `/api/cards`.

### Home page change

Add a "Collection" button to `templates/index.html` that navigates to `/collection`. Styled consistently with the existing draw button (gold border, Cinzel font, dark background).

---

## Frontend (`templates/collection.html`)

### Layout (top to bottom)

1. **Header** — "✦ COLLECTION ✦" in Cinzel Decorative gold, with a "← Back" link to `/`
2. **Controls bar** — search `<input>` on the left, tier toggle buttons on the right: `ALL · T1 · T2 · T3`
3. **Card grid** — responsive CSS grid, `~150px` wide cards at the standard TCG 5:7 aspect ratio, tier badge overlaid top-right
4. **Sentinel element** — invisible `<div id="sentinel">` at the bottom watched by `IntersectionObserver`
5. **Empty state** — "No cards found" centered message in muted-gold style, shown when `total === 0`

### Search & filter behaviour

- Search input: debounced 300ms, triggers a fresh fetch (reset offset to 0, clear grid)
- Tier toggle: instant on click, triggers fresh fetch (reset offset to 0, clear grid)
- Active tier toggle is highlighted with gold background + dark text
- Only one tier active at a time; clicking the active tier deselects back to ALL

### Infinite scroll

- `IntersectionObserver` watches `#sentinel`
- When sentinel enters viewport and `has_more === true` and no fetch is already in progress: fetch next page (offset += limit), append new cards to grid
- When `has_more === false`: observer disconnects (or sentinel hidden)

### Modal

- Clicking any card thumbnail opens a full-screen overlay
- Overlay: semi-transparent dark backdrop, centred card at ~300px wide (same proportions as draw card front), gold border, `box-shadow` glow
- Card shows: image, character name, anime, tier badge
- Close: click backdrop, press `Escape`
- Modal is built in plain DOM (no library)

### Styling

- All existing classes reused: `title`, `tier-badge`, `tier-t1/t2/t3`, Cinzel font, `#c9a84c` gold palette
- New classes added to `static/style.css`: `.collection-grid`, `.collection-card`, `.collection-controls`, `.tier-toggle`, `.tier-toggle.active`, `.collection-modal`, `.collection-modal-inner`, `.collection-empty`
- No new CSS files — everything added to the existing `style.css`

---

## File changes summary

| File | Change |
|------|--------|
| `app.py` | Add `GET /api/cards` route and `GET /collection` route |
| `templates/index.html` | Add "Collection" button linking to `/collection` |
| `templates/collection.html` | New file — full collection page |
| `static/style.css` | Append collection-specific CSS classes |

---

## Out of scope

- Persistent "owned" tracking separate from the filesystem — collection = whatever is in `cards/`
- Sorting options other than newest-first
- Multi-tier filter (only one tier active at a time)
- Animations on card grid cards (the modal inherits the existing card-front styling)
