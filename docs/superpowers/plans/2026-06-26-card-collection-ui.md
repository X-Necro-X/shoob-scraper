# Card Collection UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/collection` page that shows every pulled card with search, tier filter, infinite scroll, and a click-to-preview modal, consistent with the existing dark/gold TCG theme.

**Architecture:** A new `GET /api/cards` Flask endpoint reads `cards/` at request time, parses filenames with the existing `parse_filename()`, applies search/tier filters and pagination, and returns JSON. The `/collection` Jinja template fetches this API client-side via `IntersectionObserver`-driven infinite scroll.

**Tech Stack:** Flask, Jinja2, vanilla JS (no libraries), CSS3 (appended to existing `static/style.css`).

## Global Constraints

- All new CSS goes in `static/style.css` — no new CSS files.
- Cinzel / Cinzel Decorative fonts; `#c9a84c` gold; `#0d0d1a` dark background — match existing palette exactly.
- Existing `parse_filename()` in `app.py` must not be modified.
- Page size default: 20 cards per page, max 100.
- No external JS libraries.

---

### Task 1: Backend — `/api/cards` endpoint and `/collection` route

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `GET /api/cards?q=&tier=&offset=0&limit=20` → `{"cards": [...], "total": int, "has_more": bool}`
  - Each card object: `{"name": str, "anime": str, "tier": str, "image": str}`
- Produces: `GET /collection` → 200 HTML

---

- [ ] **Step 1: Write failing tests for `/api/cards` and `/collection`**

Append these tests to `tests/test_app.py`:

```python
# ── /api/cards ──

def _make_cards(tmp_path, names):
    cards_dir = tmp_path / 'cards'
    cards_dir.mkdir(exist_ok=True)
    for name in names:
        (cards_dir / name).write_bytes(b'')
    return cards_dir


@pytest.fixture
def cards_client(tmp_path, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, 'BASE_DIR', tmp_path)
    app_module.app.config['TESTING'] = True
    with app_module.app.test_client() as c:
        yield c, tmp_path


def test_api_cards_no_cards_dir(cards_client):
    client, _ = cards_client
    resp = client.get('/api/cards')
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data == {'cards': [], 'total': 0, 'has_more': False}


def test_api_cards_returns_all(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'Alina-Clover-T1-2.png'])
    data = json.loads(client.get('/api/cards').data)
    assert data['total'] == 2
    assert len(data['cards']) == 2
    assert data['has_more'] is False


def test_api_cards_newest_first(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'Alina-Clover-T1-2.png'])
    data = json.loads(client.get('/api/cards').data)
    # suffix 2 > suffix 1, so Alina card (suffix 2) should be first
    assert data['cards'][0]['image'] == 'Alina-Clover-T1-2.png'


def test_api_cards_search_by_name(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'Alina-Clover-T1-2.png'])
    data = json.loads(client.get('/api/cards?q=rem').data)
    assert data['total'] == 1
    assert data['cards'][0]['name'] == 'Rem'


def test_api_cards_search_by_anime(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'Alina-Clover-T1-2.png'])
    data = json.loads(client.get('/api/cards?q=rezero').data)
    assert data['total'] == 1
    assert data['cards'][0]['name'] == 'Rem'


def test_api_cards_search_case_insensitive(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png'])
    data = json.loads(client.get('/api/cards?q=REM').data)
    assert data['total'] == 1


def test_api_cards_tier_filter(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'Alina-Clover-T1-2.png'])
    data = json.loads(client.get('/api/cards?tier=T1').data)
    assert data['total'] == 1
    assert data['cards'][0]['tier'] == 'T1'


def test_api_cards_tier_filter_case_insensitive(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png'])
    data = json.loads(client.get('/api/cards?tier=t2').data)
    assert data['total'] == 1


def test_api_cards_pagination_has_more(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, [f'Card-Anime-T1-{i}.png' for i in range(1, 26)])
    data = json.loads(client.get('/api/cards?offset=0&limit=20').data)
    assert len(data['cards']) == 20
    assert data['total'] == 25
    assert data['has_more'] is True


def test_api_cards_pagination_last_page(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, [f'Card-Anime-T1-{i}.png' for i in range(1, 26)])
    data = json.loads(client.get('/api/cards?offset=20&limit=20').data)
    assert len(data['cards']) == 5
    assert data['has_more'] is False


def test_api_cards_ignores_non_png(cards_client):
    client, tmp_path = cards_client
    _make_cards(tmp_path, ['Rem-ReZero-T2-1.png', 'notes.txt', 'thumb.jpg'])
    data = json.loads(client.get('/api/cards').data)
    assert data['total'] == 1


def test_collection_route(cards_client):
    client, _ = cards_client
    resp = client.get('/collection')
    assert resp.status_code == 200
    assert b'COLLECTION' in resp.data
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_app.py::test_api_cards_no_cards_dir tests/test_app.py::test_collection_route -v
```

Expected: `FAILED` — `404 Not Found` or `AttributeError` (routes don't exist yet).

- [ ] **Step 3: Add `request` to Flask imports in `app.py`**

In `app.py`, line 8, the import already reads:
```python
from flask import Flask, jsonify, send_from_directory, render_template
```

Change it to:
```python
from flask import Flask, jsonify, render_template, request, send_from_directory
```

- [ ] **Step 4: Add `/api/cards` and `/collection` routes to `app.py`**

Insert the following two routes after the existing `@app.get('/cards/<path:filename>')` route (after line 115), before `if __name__ == '__main__':`:

```python
@app.get('/api/cards')
def api_cards():
    q = request.args.get('q', '').strip().lower()
    tier_filter = request.args.get('tier', '').strip().upper()
    try:
        offset = max(0, int(request.args.get('offset', 0)))
        limit = max(1, min(100, int(request.args.get('limit', 20))))
    except (ValueError, TypeError):
        offset, limit = 0, 20

    cards_dir = BASE_DIR / 'cards'
    if not cards_dir.exists():
        return jsonify({'cards': [], 'total': 0, 'has_more': False})

    all_cards = []
    for p in cards_dir.iterdir():
        if p.suffix.lower() != '.png':
            continue
        card = parse_filename(p.name)
        parts = p.stem.split('-')
        card['_sort_key'] = int(parts[-1]) if parts[-1].isdigit() else 0
        all_cards.append(card)

    all_cards.sort(key=lambda c: c['_sort_key'], reverse=True)

    if q:
        all_cards = [c for c in all_cards
                     if q in c['name'].lower() or q in c['anime'].lower()]
    if tier_filter:
        all_cards = [c for c in all_cards if c['tier'].upper() == tier_filter]

    total = len(all_cards)
    page = all_cards[offset:offset + limit]
    for c in page:
        c.pop('_sort_key', None)

    return jsonify({'cards': page, 'total': total, 'has_more': offset + limit < total})


@app.get('/collection')
def collection():
    return render_template('collection.html')
```

- [ ] **Step 5: Run all tests and confirm they pass**

```
pytest tests/test_app.py -v
```

Expected: all tests PASS. Fix any failures before continuing.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: add /api/cards endpoint and /collection route"
```

---

### Task 2: Collection CSS

**Files:**
- Modify: `static/style.css`

**Interfaces:**
- Produces: CSS classes `.back-link`, `.collection-controls`, `.collection-search`, `.tier-toggles`, `.tier-toggle`, `.tier-toggle.active`, `.collection-grid`, `.collection-card`, `.collection-empty`, `.collection-modal`, `.collection-modal-backdrop`, `.collection-modal-inner` — all consumed by Task 3.

---

- [ ] **Step 1: Append collection styles to `static/style.css`**

Add this block at the very end of `static/style.css`:

```css
/* ── Collection Page ── */
.back-link {
  position: relative;
  z-index: 1;
  align-self: flex-start;
  color: #665530;
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-decoration: none;
  margin-bottom: 0.5rem;
  transition: color 0.2s;
}
.back-link:hover { color: #c9a84c; }

.collection-controls {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 1rem;
  width: 100%;
  max-width: 900px;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.collection-search {
  flex: 1;
  min-width: 180px;
  background: rgba(255,255,255,0.04);
  border: 1px solid #c9a84c44;
  color: #e8d9a0;
  font-family: 'Cinzel', serif;
  font-size: 0.8rem;
  letter-spacing: 0.05em;
  padding: 0.5rem 0.9rem;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.collection-search::placeholder { color: #665530; }
.collection-search:focus {
  border-color: #c9a84c;
  box-shadow: 0 0 8px rgba(201,168,76,0.25);
}

.tier-toggles { display: flex; gap: 0.4rem; }

.tier-toggle {
  background: transparent;
  border: 1px solid #c9a84c44;
  color: #665530;
  font-family: 'Cinzel', serif;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}
.tier-toggle:hover { border-color: #c9a84c; color: #c9a84c; }
.tier-toggle.active {
  background: #c9a84c;
  border-color: #c9a84c;
  color: #0d0d1a;
}

.collection-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
  width: 100%;
  max-width: 900px;
}

.collection-card {
  position: relative;
  aspect-ratio: 5 / 7;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #c9a84c33;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
}
.collection-card:hover {
  border-color: #c9a84c;
  box-shadow: 0 0 14px rgba(201,168,76,0.45);
  transform: translateY(-2px);
}
.collection-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.collection-card .tier-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 0.6rem;
  padding: 2px 5px;
}

.collection-empty {
  position: relative;
  z-index: 1;
  color: #665530;
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  margin-top: 3rem;
  text-align: center;
}

/* ── Collection Modal ── */
.collection-modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.collection-modal-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.82);
}

.collection-modal-inner {
  position: relative;
  width: 300px;
  height: 420px;
  border-radius: 14px;
  overflow: hidden;
  border: 2px solid #c9a84c;
  box-shadow:
    0 0 40px rgba(201,168,76,0.5),
    0 0 80px rgba(201,168,76,0.2);
  background: #0d0d1a;
  display: flex;
  flex-direction: column;
}

.collection-modal-inner img {
  flex: 1;
  width: 100%;
  object-fit: cover;
  display: block;
  min-height: 0;
}
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "feat: add collection page CSS"
```

---

### Task 3: `collection.html` template

**Files:**
- Create: `templates/collection.html`

**Interfaces:**
- Consumes: `GET /api/cards` (Task 1), CSS classes from Task 2, existing `.title`, `.tier-badge`, `.tier-t1/t2/t3`, `.card-front-info`, `.card-name`, `.card-anime` from `style.css`
- Consumes: `GET /cards/<filename>` (existing Flask route that serves card images)

---

- [ ] **Step 1: Create `templates/collection.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Collection — Shoob Gacha</title>
  <link rel="stylesheet" href="/static/style.css"/>
</head>
<body>

  <a class="back-link" href="/">← Back</a>
  <h1 class="title"><span>✦</span> COLLECTION <span>✦</span></h1>

  <div class="collection-controls">
    <input class="collection-search" id="searchInput" type="text"
           placeholder="Search by name or anime…" autocomplete="off"/>
    <div class="tier-toggles">
      <button class="tier-toggle active" data-tier="">ALL</button>
      <button class="tier-toggle" data-tier="T1">T1</button>
      <button class="tier-toggle" data-tier="T2">T2</button>
      <button class="tier-toggle" data-tier="T3">T3</button>
    </div>
  </div>

  <div class="collection-grid" id="cardGrid"></div>
  <div class="collection-empty" id="emptyState" style="display:none">No cards found.</div>
  <div id="sentinel" style="height:1px"></div>

  <div class="collection-modal" id="modal" style="display:none"
       role="dialog" aria-modal="true" aria-label="Card preview">
    <div class="collection-modal-backdrop" id="modalBackdrop"></div>
    <div class="collection-modal-inner">
      <img id="modalImage" src="" alt=""/>
      <span class="tier-badge" id="modalTier"></span>
      <div class="card-front-info">
        <div class="card-name" id="modalName"></div>
        <div class="card-anime" id="modalAnime"></div>
      </div>
    </div>
  </div>

  <script>
    const PAGE_SIZE = 20;
    let offset = 0;
    let activeTier = '';
    let searchQuery = '';
    let isFetching = false;
    let hasMore = true;
    let debounceTimer = null;
    let observer = null;

    const grid        = document.getElementById('cardGrid');
    const emptyState  = document.getElementById('emptyState');
    const searchInput = document.getElementById('searchInput');
    const sentinel    = document.getElementById('sentinel');
    const modal       = document.getElementById('modal');
    const modalBackdrop = document.getElementById('modalBackdrop');
    const modalImage  = document.getElementById('modalImage');
    const modalTier   = document.getElementById('modalTier');
    const modalName   = document.getElementById('modalName');
    const modalAnime  = document.getElementById('modalAnime');

    function tierClass(tier) {
      if (!tier) return 'tier-unknown';
      const t = tier.toUpperCase();
      if (t === 'T1' || t === 'R')   return 'tier-t1';
      if (t === 'T2' || t === 'SR')  return 'tier-t2';
      if (t === 'T3' || t === 'SSR') return 'tier-t3';
      return 'tier-unknown';
    }

    function buildCard(card) {
      const el = document.createElement('div');
      el.className = 'collection-card';
      const img = document.createElement('img');
      img.src = `/cards/${card.image}`;
      img.alt = card.name;
      img.loading = 'lazy';
      const badge = document.createElement('span');
      badge.className = `tier-badge ${tierClass(card.tier)}`;
      badge.textContent = card.tier;
      el.appendChild(img);
      el.appendChild(badge);
      el.addEventListener('click', () => openModal(card));
      return el;
    }

    function openModal(card) {
      modalImage.src = `/cards/${card.image}`;
      modalImage.alt = card.name;
      modalTier.textContent = card.tier;
      modalTier.className = `tier-badge ${tierClass(card.tier)}`;
      modalName.textContent = card.name;
      modalAnime.textContent = card.anime;
      modal.style.display = 'flex';
    }

    function closeModal() {
      modal.style.display = 'none';
      modalImage.src = '';
    }

    modalBackdrop.addEventListener('click', closeModal);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') closeModal();
    });

    function reset() {
      offset = 0;
      hasMore = true;
      grid.innerHTML = '';
      emptyState.style.display = 'none';
      if (observer) { observer.disconnect(); observer = null; }
      setupObserver();
    }

    function setupObserver() {
      observer = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && hasMore && !isFetching) {
          fetchPage();
        }
      }, { rootMargin: '200px' });
      observer.observe(sentinel);
    }

    function fetchPage() {
      if (isFetching) return;
      isFetching = true;
      const params = new URLSearchParams({
        offset,
        limit: PAGE_SIZE,
        q: searchQuery,
        tier: activeTier,
      });
      fetch(`/api/cards?${params}`)
        .then(r => r.json())
        .then(data => {
          data.cards.forEach(card => grid.appendChild(buildCard(card)));
          offset += data.cards.length;
          hasMore = data.has_more;
          if (!hasMore && observer) { observer.disconnect(); observer = null; }
          emptyState.style.display = data.total === 0 ? 'block' : 'none';
        })
        .finally(() => { isFetching = false; });
    }

    document.querySelectorAll('.tier-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tier-toggle').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeTier = btn.dataset.tier;
        reset();
      });
    });

    searchInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        searchQuery = searchInput.value.trim();
        reset();
      }, 300);
    });

    setupObserver();
  </script>

</body>
</html>
```

- [ ] **Step 2: Start the Flask app and manually verify the collection page**

```
python app.py
```

Open `http://localhost:5000/collection` in a browser. Confirm:
- Title renders in gold Cinzel Decorative font
- "← Back" link is present and returns to home
- Search input and ALL/T1/T2/T3 toggle buttons appear
- Cards from the `cards/` folder load in the grid (newest first by filename number suffix)
- Tier badge appears on each card thumbnail
- Clicking a card opens the full-size modal with name, anime, tier, and image
- Clicking outside the modal or pressing Escape closes it
- Typing in the search box filters cards after ~300ms
- Clicking a tier toggle filters; clicking the active toggle deselects back to ALL

- [ ] **Step 3: Commit**

```bash
git add templates/collection.html
git commit -m "feat: add collection.html with grid, search, tier filter, infinite scroll, and modal"
```

---

### Task 4: Home page "Collection" button

**Files:**
- Modify: `templates/index.html`

**Interfaces:**
- Consumes: `GET /collection` route (Task 1)
- Consumes: `.btn-draw` styles already in `style.css` (reused for consistent look)

---

- [ ] **Step 1: Add Collection button to `templates/index.html`**

After the closing `</button>` of the Draw button (line 38), add:

```html
  <a class="btn-draw" href="/collection" style="margin-top:0.6rem;text-decoration:none;display:inline-block;text-align:center">Collection</a>
```

The full block after edit (lines 38–40 area) should look like:

```html
  <button class="btn-draw" id="btnDraw" onclick="draw()">Draw Card</button>
  <a class="btn-draw" href="/collection" style="margin-top:0.6rem;text-decoration:none;display:inline-block;text-align:center">Collection</a>
```

- [ ] **Step 2: Verify home page in browser**

With the Flask app still running (`python app.py`), open `http://localhost:5000`. Confirm:
- "Collection" button appears below the Draw button
- Clicking it navigates to `/collection`
- The Draw flow still works correctly (no regressions)

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: add Collection button to home page"
```
