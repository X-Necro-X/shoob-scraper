# TCG Card UI — Design Spec
**Date:** 2026-06-25

## Overview

A Flask web application that provides a TCG-themed browser UI for the existing `scraper.py` CLI tool. The user clicks a "Draw Card" button, the server spawns the scraper as a subprocess, and the browser polls for completion. When the scraper finishes, the card image is revealed via a 3D flip animation.

The scraper (`scraper.py`) is left completely untouched — Flask drives it as a black box and parses its stdout.

---

## Architecture

```
Browser (HTML/CSS/JS)
    │
    ├─ POST /draw          → Flask spawns scraper.py subprocess, returns {job_id}
    ├─ GET  /status/<id>   → returns {status: "running"|"done"|"error", card: {...}}
    └─ GET  /cards/<file>  → serves downloaded card images from ./cards/
    
Flask app (app.py)
    ├─ In-memory job store: {job_id: {status, card_name, anime_name, tier, image_file}}
    └─ Runs scraper.py via subprocess.Popen, captures stdout to get filename

scraper.py (unchanged)
    └─ Prints "Downloaded: <filename>" on success — Flask parses this line
```

### Job lifecycle

1. `POST /draw` — Flask generates a UUID job ID, spawns `scraper.py` in a background thread (which captures stdout/stderr), stores job as `{status: "running"}`, returns `{job_id}`.
2. Background thread waits for subprocess to finish. On success it parses `"Downloaded: <filename>"` from stdout, extracts card metadata from the filename (name, anime, tier), sets job to `{status: "done", card: {...}}`. On failure sets `{status: "error", message: "..."}`.
3. `GET /status/<job_id>` — Returns current job dict as JSON.
4. `GET /cards/<filename>` — Flask serves the `./cards/` directory statically.

### Card metadata extraction from filename

Filenames follow the pattern `CardName-AnimeName-Tier-N.ext` (e.g. `Yuna-Yunis-Yuusha-ga-Shinda-T2-1.png`). The server parses: tier = last hyphen-separated token before the numeric suffix (matches `T\d+` or `SSR`/`SR`/`R`), image_file = full filename. Card name and anime name are derived from the filename for display (hyphens → spaces).

---

## File Layout

```
shoob/
├── app.py                  ← new: Flask server (job store, /draw, /status, /cards)
├── scraper.py              ← unchanged
├── templates/
│   └── index.html          ← new: single-page UI (HTML + inline JS)
├── static/
│   ├── style.css           ← new: TCG styles + CSS animations
│   └── card-back.svg       ← new: decorative card back graphic
├── cards/                  ← existing image output dir
├── seen.json               ← existing
└── requirements.txt        ← add: flask
```

---

## UI/UX Design

### Visual theme
- **Background**: Deep dark gradient (near-black with subtle purple/blue hues), faint repeating card-suit texture overlay
- **Typography**: Serif or fantasy-adjacent font for card names; monospace for tier badges
- **Color palette**: Dark background (#0d0d1a), gold accents (#c9a84c), tier badge colors (see below)

### Page layout (single screen, centered)
```
┌─────────────────────────────────────────┐
│           ✦  SHOOB GACHA  ✦             │  ← title
│                                         │
│         ┌──────────────┐                │
│         │              │                │
│         │   CARD SLOT  │                │  ← 300×420px card stage
│         │  (back / img)│                │
│         └──────────────┘                │
│                                         │
│           [ DRAW CARD ]                 │  ← button (disabled during draw)
│                                         │
│   ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐       │  ← history strip (session)
│   │   │ │   │ │   │ │   │ │   │       │
│   └───┘ └───┘ └───┘ └───┘ └───┘       │
└─────────────────────────────────────────┘
```

### States

| State | Card slot | Button |
|---|---|---|
| Idle (first load) | Decorative card back, subtle glow pulse | "Draw Card" — enabled |
| Loading | Card back spins/pulses with shimmer particles | "Drawing..." — disabled |
| Revealed | Card front (image + name + tier badge), flip completes | "Draw Another" — enabled |
| Error | Error message in card slot | "Try Again" — enabled |

### Animations
- **Idle pulse**: card back has a slow gold border glow loop (`box-shadow` keyframe, 3s infinite)
- **Loading shimmer**: faster spin + shimmer overlay on card back while polling
- **Card flip**: CSS `rotateY` 3D transform, 0.8s ease. Front face hidden until halfway through flip (`backface-visibility: hidden`)
- **Button shimmer**: gold shimmer sweep on hover

### Tier badge colors
| Tier | Color |
|---|---|
| T1 / R | Grey (`#888`) |
| T2 / SR | Blue (`#4a90d9`) |
| T3 / SSR | Gold (`#c9a84c`) with glow |
| Any unknown | Purple (`#9b59b6`) |

### History strip
- Stores drawn cards for the browser session (JS array in memory, not persisted to server)
- Each thumbnail: 60×84px, rounded corners, hover shows card name tooltip
- Strip scrolls horizontally if it overflows
- Clicking a thumbnail does nothing (display only)

---

## Backend Details (`app.py`)

```python
# Key routes
POST /draw
  → spawns subprocess.Popen(['python', 'scraper.py'], stdout=PIPE, stderr=PIPE)
  → background thread reads output, updates job store
  → returns {"job_id": "<uuid>"}

GET /status/<job_id>
  → returns {"status": "running"}
          | {"status": "done", "card": {"name": str, "anime": str, "tier": str, "image": str}}
          | {"status": "error", "message": str}

GET /cards/<filename>
  → serves file from ./cards/ directory
```

Job store is a plain Python dict (thread-safe writes are fine for single-worker dev server). No persistence needed — jobs are ephemeral.

---

## Dependencies

New additions to `requirements.txt`:
```
flask
```

Existing:
```
playwright
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Scraper exits non-zero | Job set to `error`; stderr surfaced as message in UI |
| Scraper stdout has no "Downloaded:" line | Job set to `error` with "Unexpected scraper output" |
| `/status/<id>` called with unknown ID | 404 JSON response |
| Draw requested while one is already running | 409 response; frontend disables button so this shouldn't happen |
| `./cards/` file not found | 404 from Flask static serve |

---

## Out of Scope

- Authentication / multi-user support
- Persistent history across page reloads (server-side storage)
- Mobile-responsive layout (desktop-first)
- Production deployment (dev server only)
