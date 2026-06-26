# TCG Card UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Flask web UI to the existing shoob card scraper so users can draw random cards via a TCG-themed browser page with a flip-reveal animation.

**Architecture:** Flask serves a single HTML page. When the user clicks "Draw Card", the browser POSTs to `/draw`, which spawns `scraper.py` as a subprocess in a background thread and returns a job ID. The browser polls `/status/<job_id>` every second until done, then triggers a CSS 3D flip to reveal the card. The scraper is left completely untouched.

**Tech Stack:** Python 3.8+, Flask, vanilla HTML/CSS/JS (no frontend framework), subprocess for scraper invocation.

## Global Constraints

- `scraper.py` must not be modified in any way
- Flask dev server only (single worker, no gunicorn/waitress)
- No frontend framework — vanilla JS only
- Card slot dimensions: 300×420px
- Thumbnail dimensions: 60×84px
- Background color: `#0d0d1a`
- Gold accent color: `#c9a84c`
- Tier badge colors: T1/R=`#888`, T2/SR=`#4a90d9`, T3/SSR=`#c9a84c` with glow, unknown=`#9b59b6`
- Card flip animation: CSS `rotateY`, 0.8s ease, `backface-visibility: hidden`
- History strip is session-only (JS in-memory, not persisted to server)

---

### Task 1: Flask backend — job store, /draw, /status, /cards

**Files:**
- Create: `app.py`
- Modify: `requirements.txt` (add `flask`)

**Interfaces:**
- Produces:
  - `POST /draw` → `{"job_id": "<uuid4-string>"}`
  - `GET /status/<job_id>` → `{"status": "running"}` | `{"status": "done", "card": {"name": str, "anime": str, "tier": str, "image": str}}` | `{"status": "error", "message": str}`
  - `GET /cards/<filename>` → binary image file from `./cards/`
  - `parse_filename(filename: str) -> dict` with keys `name`, `anime`, `tier`

- [ ] **Step 1: Add flask to requirements.txt**

Open `requirements.txt` and add `flask` so it reads:
```
playwright
pytest
flask
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_app.py`:

```python
import json
import re
import pytest
from app import app, parse_filename


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


# --- parse_filename ---

def test_parse_filename_standard():
    result = parse_filename("Rem-ReZero-T2-1.png")
    assert result['tier'] == 'T2'


def test_parse_filename_multi_part_anime():
    result = parse_filename("Yuna-Yunis-Yuusha-ga-Shinda-T2-1.png")
    assert result['tier'] == 'T2'
    assert result['name'] != ''
    assert result['anime'] != ''


def test_parse_filename_ssr():
    result = parse_filename("Rem-ReZero-SSR-1.png")
    assert result['tier'] == 'SSR'


def test_parse_filename_unknown_tier():
    result = parse_filename("Rem-ReZero-XYZ-1.png")
    assert result['tier'] == 'XYZ'


# --- /draw ---

def test_draw_returns_job_id(client, monkeypatch):
    import app as app_module

    def fake_run_scraper(job_id):
        app_module.jobs[job_id] = {
            'status': 'done',
            'card': {'name': 'Rem', 'anime': 'ReZero', 'tier': 'T2', 'image': 'Rem-ReZero-T2-1.png'}
        }

    monkeypatch.setattr(app_module, '_run_scraper', fake_run_scraper)
    resp = client.post('/draw')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert 'job_id' in data
    assert re.match(r'^[0-9a-f-]{36}$', data['job_id'])


def test_draw_returns_409_when_running(client, monkeypatch):
    import app as app_module
    existing_id = 'test-running-id'
    app_module.jobs[existing_id] = {'status': 'running'}

    def fake_run_scraper(job_id):
        pass

    monkeypatch.setattr(app_module, '_run_scraper', fake_run_scraper)
    resp = client.post('/draw')
    assert resp.status_code == 409
    app_module.jobs.pop(existing_id, None)


# --- /status ---

def test_status_running(client):
    import app as app_module
    app_module.jobs['abc'] = {'status': 'running'}
    resp = client.get('/status/abc')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['status'] == 'running'
    app_module.jobs.pop('abc', None)


def test_status_done(client):
    import app as app_module
    app_module.jobs['xyz'] = {
        'status': 'done',
        'card': {'name': 'Rem', 'anime': 'ReZero', 'tier': 'T2', 'image': 'Rem-ReZero-T2-1.png'}
    }
    resp = client.get('/status/xyz')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data['status'] == 'done'
    assert data['card']['tier'] == 'T2'
    app_module.jobs.pop('xyz', None)


def test_status_unknown_job(client):
    resp = client.get('/status/does-not-exist')
    assert resp.status_code == 404
```

- [ ] **Step 3: Run tests to confirm they fail**

```
pytest tests/test_app.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'` or similar — confirms tests are wired up but nothing exists yet.

- [ ] **Step 4: Implement app.py**

Create `app.py`:

```python
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, render_template

app = Flask(__name__)

jobs: dict = {}


def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    parts = stem.split('-')
    # Find the tier token: last part matching T\d+, SSR, SR, or R before the numeric suffix
    tier = 'unknown'
    tier_idx = len(parts) - 1
    # Last part is the numeric suffix (e.g. "1"), second-to-last is tier
    known_tier = re.compile(r'^(T\d+|SSR|SR|R)$', re.IGNORECASE)
    for i in range(len(parts) - 1, -1, -1):
        if known_tier.match(parts[i]):
            tier = parts[i].upper()
            tier_idx = i
            break
        if parts[i].isdigit():
            continue
        # If not digit and not tier, treat as part of name — stop searching
        break

    # Everything before tier_idx is "CardName-AnimeName" combined
    # Split roughly in half for display: first token = card name, rest = anime
    name_parts = parts[:tier_idx]
    if len(name_parts) >= 2:
        name = name_parts[0]
        anime = ' '.join(name_parts[1:])
    elif len(name_parts) == 1:
        name = name_parts[0]
        anime = ''
    else:
        name = stem
        anime = ''

    return {'name': name, 'anime': anime, 'tier': tier, 'image': filename}


def _run_scraper(job_id: str) -> None:
    try:
        proc = subprocess.Popen(
            [sys.executable, 'scraper.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate()

        if proc.returncode != 0:
            jobs[job_id] = {'status': 'error', 'message': stderr.strip() or 'Scraper exited with error'}
            return

        match = re.search(r'Downloaded:\s*(.+)', stdout)
        if not match:
            jobs[job_id] = {'status': 'error', 'message': 'Unexpected scraper output'}
            return

        filename = match.group(1).strip()
        card = parse_filename(filename)
        jobs[job_id] = {'status': 'done', 'card': card}

    except Exception as exc:
        jobs[job_id] = {'status': 'error', 'message': str(exc)}


@app.get('/')
def index():
    return render_template('index.html')


@app.post('/draw')
def draw():
    running = any(j.get('status') == 'running' for j in jobs.values())
    if running:
        return jsonify({'error': 'A draw is already in progress'}), 409

    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'running'}
    thread = threading.Thread(target=_run_scraper, args=(job_id,), daemon=True)
    thread.start()
    return jsonify({'job_id': job_id})


@app.get('/status/<job_id>')
def status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({'error': 'Unknown job'}), 404
    return jsonify(job)


@app.get('/cards/<path:filename>')
def serve_card(filename: str):
    return send_from_directory('cards', filename)


if __name__ == '__main__':
    app.run(debug=True)
```

- [ ] **Step 5: Run tests — expect them to pass**

```
pip install flask
pytest tests/test_app.py -v
```

Expected output: all 9 tests pass.

- [ ] **Step 6: Commit**

```bash
git add app.py requirements.txt tests/test_app.py
git commit -m "feat: add Flask backend with job store, /draw, /status, /cards"
```

---

### Task 2: Card back SVG

**Files:**
- Create: `static/card-back.svg`

**Interfaces:**
- Produces: `static/card-back.svg` — decorative card back graphic referenced by `index.html` as `/static/card-back.svg`

- [ ] **Step 1: Create the SVG**

Create `static/card-back.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 420" width="300" height="420">
  <defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="70%">
      <stop offset="0%" stop-color="#1a1040"/>
      <stop offset="100%" stop-color="#0d0d1a"/>
    </radialGradient>
    <pattern id="diamond" x="0" y="0" width="30" height="30" patternUnits="userSpaceOnUse">
      <polygon points="15,2 28,15 15,28 2,15" fill="none" stroke="#c9a84c" stroke-width="0.4" opacity="0.25"/>
    </pattern>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="300" height="420" rx="14" ry="14" fill="url(#bg)"/>

  <!-- Diamond lattice -->
  <rect width="300" height="420" rx="14" ry="14" fill="url(#diamond)"/>

  <!-- Outer border -->
  <rect x="6" y="6" width="288" height="408" rx="10" ry="10"
        fill="none" stroke="#c9a84c" stroke-width="2" opacity="0.8"/>

  <!-- Inner border -->
  <rect x="14" y="14" width="272" height="392" rx="7" ry="7"
        fill="none" stroke="#c9a84c" stroke-width="0.8" opacity="0.4"/>

  <!-- Center emblem: stylized star/diamond -->
  <g filter="url(#glow)" transform="translate(150,210)">
    <polygon points="0,-55 13,-13 55,0 13,13 0,55 -13,13 -55,0 -13,-13"
             fill="#c9a84c" opacity="0.9"/>
    <polygon points="0,-35 8,-8 35,0 8,8 0,35 -8,8 -35,0 -8,-8"
             fill="#0d0d1a" opacity="0.85"/>
    <circle cx="0" cy="0" r="10" fill="#c9a84c" opacity="0.9"/>
  </g>

  <!-- Corner ornaments -->
  <g opacity="0.6" stroke="#c9a84c" stroke-width="1.2" fill="none">
    <path d="M20,20 L36,20 L36,24 M20,20 L20,36 L24,36"/>
    <path d="M280,20 L264,20 L264,24 M280,20 L280,36 L276,36"/>
    <path d="M20,400 L36,400 L36,396 M20,400 L20,384 L24,384"/>
    <path d="M280,400 L264,400 L264,396 M280,400 L280,384 L276,384"/>
  </g>

  <!-- "SHOOB" watermark -->
  <text x="150" y="370" text-anchor="middle" font-family="serif"
        font-size="13" fill="#c9a84c" opacity="0.45" letter-spacing="6">SHOOB</text>
</svg>
```

- [ ] **Step 2: Verify the SVG renders**

Open `static/card-back.svg` directly in a browser. You should see a dark card with a gold diamond lattice pattern, a star emblem in the center, corner brackets, and "SHOOB" at the bottom.

- [ ] **Step 3: Commit**

```bash
git add static/card-back.svg
git commit -m "feat: add decorative card back SVG"
```

---

### Task 3: CSS — TCG theme and all animations

**Files:**
- Create: `static/style.css`

**Interfaces:**
- Produces: CSS classes consumed by `index.html`:
  - `.card-stage` — 300×420px 3D perspective container
  - `.card-inner` — flips via `.card-inner.flipped` (adds `rotateY(180deg)`)
  - `.card-back`, `.card-front` — two faces, `backface-visibility: hidden`
  - `.card-back.loading` — activates shimmer/spin animation
  - `.btn-draw` — gold TCG button; `.btn-draw:disabled` — muted state
  - `.tier-badge` — inline badge; `.tier-t1`, `.tier-t2`, `.tier-t3`, `.tier-unknown`
  - `.history-strip` — horizontal scroll container
  - `.history-thumb` — 60×84px thumbnail with tooltip via `title` attribute

- [ ] **Step 1: Write style.css**

Create `static/style.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Cinzel+Decorative:wght@700&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  min-height: 100vh;
  background: radial-gradient(ellipse at 50% 30%, #1a1040 0%, #0d0d1a 70%);
  color: #e8d9a0;
  font-family: 'Cinzel', serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 2rem 1rem 3rem;
  overflow-x: hidden;
}

/* Subtle repeating texture overlay */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 18px,
    rgba(201,168,76,0.03) 18px,
    rgba(201,168,76,0.03) 19px
  );
  pointer-events: none;
  z-index: 0;
}

/* ── Title ── */
.title {
  font-family: 'Cinzel Decorative', serif;
  font-size: clamp(1.4rem, 4vw, 2.2rem);
  color: #c9a84c;
  text-shadow: 0 0 18px rgba(201,168,76,0.6), 0 0 40px rgba(201,168,76,0.25);
  letter-spacing: 0.15em;
  margin-bottom: 2.5rem;
  position: relative;
  z-index: 1;
}
.title span { opacity: 0.7; font-size: 0.8em; }

/* ── Card Stage ── */
.card-stage {
  perspective: 900px;
  width: 300px;
  height: 420px;
  position: relative;
  z-index: 1;
  margin-bottom: 2rem;
}

.card-inner {
  width: 100%;
  height: 100%;
  position: relative;
  transform-style: preserve-3d;
  transition: transform 0.8s ease;
}

.card-inner.flipped {
  transform: rotateY(180deg);
}

.card-back,
.card-front {
  position: absolute;
  inset: 0;
  border-radius: 14px;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  overflow: hidden;
}

/* Card back */
.card-back {
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    0 0 18px rgba(201,168,76,0.35),
    0 0 40px rgba(201,168,76,0.12),
    inset 0 0 30px rgba(0,0,0,0.5);
  animation: idle-pulse 3s ease-in-out infinite;
}

.card-back img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 14px;
}

/* Loading state — pulse + shimmer (no rotateY: card-back has backface-visibility:hidden
   so a full 360° rotateY would make it vanish at 90° and 270°) */
.card-back.loading {
  animation: loading-pulse 0.7s ease-in-out infinite;
}
.card-back.loading::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 14px;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(201,168,76,0.4) 50%,
    transparent 70%
  );
  background-size: 200% 100%;
  animation: shimmer-sweep 0.9s linear infinite;
}

/* Card front */
.card-front {
  transform: rotateY(180deg);
  background: #0d0d1a;
  border: 2px solid #c9a84c;
  box-shadow:
    0 0 24px rgba(201,168,76,0.5),
    0 0 60px rgba(201,168,76,0.2);
  display: flex;
  flex-direction: column;
}

.card-front-image {
  flex: 1;
  overflow: hidden;
}

.card-front-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card-front-info {
  padding: 0.6rem 0.8rem 0.7rem;
  background: linear-gradient(to top, rgba(0,0,0,0.85), transparent);
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  border-radius: 0 0 12px 12px;
}

.card-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: #f0e0a0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-anime {
  font-size: 0.7rem;
  color: #a89060;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

/* Tier badge */
.tier-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-family: monospace;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.05em;
  border: 1px solid currentColor;
}

.tier-t1 { color: #888; border-color: #888; background: rgba(136,136,136,0.15); }
.tier-t2 { color: #4a90d9; border-color: #4a90d9; background: rgba(74,144,217,0.15); }
.tier-t3 {
  color: #c9a84c;
  border-color: #c9a84c;
  background: rgba(201,168,76,0.15);
  box-shadow: 0 0 8px rgba(201,168,76,0.5);
}
.tier-unknown { color: #9b59b6; border-color: #9b59b6; background: rgba(155,89,182,0.15); }

/* Error state */
.card-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #e05555;
  font-size: 0.8rem;
  padding: 1.5rem;
  text-align: center;
  gap: 0.5rem;
}
.card-error .error-icon { font-size: 2rem; }

/* ── Draw Button ── */
.btn-draw {
  position: relative;
  z-index: 1;
  background: linear-gradient(135deg, #2a1f00, #1a1400);
  border: 2px solid #c9a84c;
  color: #c9a84c;
  font-family: 'Cinzel', serif;
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: 0.8rem 2.8rem;
  border-radius: 6px;
  cursor: pointer;
  overflow: hidden;
  transition: box-shadow 0.2s, color 0.2s;
  box-shadow: 0 0 10px rgba(201,168,76,0.2);
}

.btn-draw::before {
  content: '';
  position: absolute;
  top: 0; left: -75%;
  width: 50%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(201,168,76,0.3), transparent);
  transform: skewX(-20deg);
  transition: left 0s;
}

.btn-draw:hover:not(:disabled)::before {
  left: 150%;
  transition: left 0.5s ease;
}

.btn-draw:hover:not(:disabled) {
  box-shadow: 0 0 22px rgba(201,168,76,0.5);
  color: #f0d060;
}

.btn-draw:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  border-color: #666;
  color: #666;
  box-shadow: none;
}

/* ── History Strip ── */
.history-section {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 700px;
  margin-top: 2.5rem;
}

.history-label {
  font-size: 0.65rem;
  letter-spacing: 0.2em;
  color: #665530;
  margin-bottom: 0.6rem;
  text-transform: uppercase;
}

.history-strip {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  padding-bottom: 0.4rem;
  scrollbar-width: thin;
  scrollbar-color: #c9a84c22 transparent;
}

.history-strip::-webkit-scrollbar { height: 3px; }
.history-strip::-webkit-scrollbar-track { background: transparent; }
.history-strip::-webkit-scrollbar-thumb { background: #c9a84c44; border-radius: 2px; }

.history-thumb {
  flex-shrink: 0;
  width: 60px;
  height: 84px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #c9a84c44;
  cursor: default;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.history-thumb:hover {
  border-color: #c9a84c;
  box-shadow: 0 0 8px rgba(201,168,76,0.4);
}

.history-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* ── Keyframes ── */
@keyframes idle-pulse {
  0%, 100% { box-shadow: 0 0 18px rgba(201,168,76,0.35), 0 0 40px rgba(201,168,76,0.12); }
  50%       { box-shadow: 0 0 30px rgba(201,168,76,0.6),  0 0 60px rgba(201,168,76,0.25); }
}

@keyframes loading-pulse {
  0%, 100% {
    box-shadow: 0 0 18px rgba(201,168,76,0.45), 0 0 45px rgba(201,168,76,0.18);
    filter: brightness(1);
  }
  50% {
    box-shadow: 0 0 50px rgba(201,168,76,0.85), 0 0 90px rgba(201,168,76,0.4);
    filter: brightness(1.18);
  }
}

@keyframes shimmer-sweep {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
```

- [ ] **Step 2: Verify the font imports work**

The CSS imports Google Fonts (Cinzel / Cinzel Decorative). This requires internet access at page load time. If offline, fonts fall back to serif — acceptable for dev.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: add TCG CSS theme with flip, shimmer, and pulse animations"
```

---

### Task 4: HTML template — single-page UI with JS polling

**Files:**
- Create: `templates/index.html`

**Interfaces:**
- Consumes:
  - `GET /draw` (POST) → `{job_id: string}`
  - `GET /status/<job_id>` → `{status, card?}` where `card = {name, anime, tier, image}`
  - `GET /cards/<filename>` → image binary
  - `/static/style.css`
  - `/static/card-back.svg`
- Produces: the complete browser UI

- [ ] **Step 1: Create templates/index.html**

First create the directory:
```bash
mkdir templates
```

Then create `templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Shoob Gacha</title>
  <link rel="stylesheet" href="/static/style.css"/>
</head>
<body>

  <h1 class="title"><span>✦</span> SHOOB GACHA <span>✦</span></h1>

  <!-- Card stage -->
  <div class="card-stage">
    <div class="card-inner" id="cardInner">

      <!-- Back face (shown by default) -->
      <div class="card-back" id="cardBack">
        <img src="/static/card-back.svg" alt="Card back"/>
      </div>

      <!-- Front face (revealed after flip) -->
      <div class="card-front" id="cardFront">
        <div class="card-front-image" id="cardImageWrap">
          <img id="cardImage" src="" alt="Card"/>
        </div>
        <span class="tier-badge" id="tierBadge"></span>
        <div class="card-front-info">
          <div class="card-name" id="cardName"></div>
          <div class="card-anime" id="cardAnime"></div>
        </div>
      </div>

    </div>
  </div>

  <!-- Draw button -->
  <button class="btn-draw" id="btnDraw" onclick="draw()">Draw Card</button>

  <!-- History -->
  <div class="history-section" id="historySection" style="display:none">
    <div class="history-label">Session History</div>
    <div class="history-strip" id="historyStrip"></div>
  </div>

  <script>
    const cardInner  = document.getElementById('cardInner');
    const cardBack   = document.getElementById('cardBack');
    const cardFront  = document.getElementById('cardFront');
    const cardImage  = document.getElementById('cardImage');
    const tierBadge  = document.getElementById('tierBadge');
    const cardName   = document.getElementById('cardName');
    const cardAnime  = document.getElementById('cardAnime');
    const btnDraw    = document.getElementById('btnDraw');
    const historySection = document.getElementById('historySection');
    const historyStrip   = document.getElementById('historyStrip');

    let pollTimer = null;

    function tierClass(tier) {
      if (!tier) return 'tier-unknown';
      const t = tier.toUpperCase();
      if (t === 'T1' || t === 'R')   return 'tier-t1';
      if (t === 'T2' || t === 'SR')  return 'tier-t2';
      if (t === 'T3' || t === 'SSR') return 'tier-t3';
      return 'tier-unknown';
    }

    function setLoading() {
      // Reset flip
      cardInner.classList.remove('flipped');
      // Restore back face, add loading class
      cardBack.className = 'card-back loading';
      cardBack.innerHTML = '<img src="/static/card-back.svg" alt="Card back"/>';
      btnDraw.disabled = true;
      btnDraw.textContent = 'Drawing...';
    }

    function showError(msg) {
      cardBack.className = 'card-back';
      cardBack.innerHTML = `<div class="card-error"><div class="error-icon">✕</div><div>${msg}</div></div>`;
      btnDraw.disabled = false;
      btnDraw.textContent = 'Try Again';
    }

    function revealCard(card) {
      // Populate front face
      cardImage.src = `/cards/${card.image}`;
      cardName.textContent = card.name;
      cardAnime.textContent = card.anime;
      tierBadge.textContent = card.tier;
      tierBadge.className = `tier-badge ${tierClass(card.tier)}`;

      // Wait for image to load then flip
      cardImage.onload = () => {
        cardBack.className = 'card-back'; // stop loading animation
        cardInner.classList.add('flipped');
        btnDraw.disabled = false;
        btnDraw.textContent = 'Draw Another';
        addToHistory(card);
      };
      cardImage.onerror = () => {
        showError('Image failed to load.');
      };
    }

    function addToHistory(card) {
      historySection.style.display = '';
      const thumb = document.createElement('div');
      thumb.className = 'history-thumb';
      thumb.title = `${card.name} · ${card.anime} · ${card.tier}`;
      const img = document.createElement('img');
      img.src = `/cards/${card.image}`;
      img.alt = card.name;
      thumb.appendChild(img);
      historyStrip.appendChild(thumb);
      // Scroll to end
      historyStrip.scrollLeft = historyStrip.scrollWidth;
    }

    function poll(jobId) {
      fetch(`/status/${jobId}`)
        .then(r => r.json())
        .then(data => {
          if (data.status === 'running') {
            pollTimer = setTimeout(() => poll(jobId), 1000);
          } else if (data.status === 'done') {
            revealCard(data.card);
          } else {
            showError(data.message || 'Something went wrong.');
          }
        })
        .catch(() => {
          showError('Network error while polling.');
        });
    }

    function draw() {
      if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
      setLoading();
      fetch('/draw', { method: 'POST' })
        .then(r => {
          if (r.status === 409) throw new Error('A draw is already in progress.');
          if (!r.ok) throw new Error('Server error starting draw.');
          return r.json();
        })
        .then(data => {
          poll(data.job_id);
        })
        .catch(err => {
          showError(err.message);
        });
    }
  </script>

</body>
</html>
```

- [ ] **Step 2: Smoke-test the full app**

Install flask if not already:
```
pip install flask
```

Start the server:
```
python app.py
```

Open `http://127.0.0.1:5000` in a browser. Verify:
- The page loads with the dark background, gold title, and card back displayed
- The "Draw Card" button is visible and gold-bordered
- No console errors in browser devtools

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: add TCG HTML/JS single-page UI with card flip and history strip"
```

---

### Task 5: End-to-end manual verification

**Files:** none (verification only)

**Interfaces:**
- Consumes: the running app at `http://127.0.0.1:5000`

- [ ] **Step 1: Start the server**

```
python app.py
```

- [ ] **Step 2: Verify idle state**

Open `http://127.0.0.1:5000`. Confirm:
- Dark background with subtle diagonal texture
- Gold "✦ SHOOB GACHA ✦" title with glow
- Card back (dark with gold lattice + star) visible with slow pulsing glow
- "Draw Card" button visible, gold-bordered, enabled
- History strip hidden

- [ ] **Step 3: Verify loading state**

Click "Draw Card". Confirm within 1–2 seconds:
- Button changes to "Drawing..." and becomes disabled
- Card back pulses with an intensified gold glow and a shimmer sweep

- [ ] **Step 4: Verify reveal**

Wait for scraper to complete (~5–15 sec). Confirm:
- Card flips with smooth 3D animation (0.8s)
- Card front shows the downloaded image
- Card name and anime name appear in the overlay at the bottom
- Tier badge appears in the top-right corner with correct color:
  - T1 → grey, T2 → blue, T3/SSR → gold with glow, other → purple
- Button changes to "Draw Another"

- [ ] **Step 5: Verify history**

After first card: confirm the history section appears below the button with a 60×84px thumbnail. Hover over it to see the tooltip with name · anime · tier.

Draw a second card. Confirm a second thumbnail is added.

- [ ] **Step 6: Verify error handling**

To simulate an error: temporarily rename `scraper.py` to `scraper_bak.py`, click "Draw Card". Confirm the card slot shows an error message and the button reads "Try Again". Rename `scraper.py` back.

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "feat: TCG card UI complete — Flask + flip reveal + history strip"
```
