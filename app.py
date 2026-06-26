import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory

BASE_DIR = Path(__file__).parent

app = Flask(__name__)

jobs: dict = {}


def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    parts = stem.split('-')
    known_tier = re.compile(r'^(T\d+|SSR|SR|R|S)$', re.IGNORECASE)
    tier = 'unknown'
    tier_idx = len(parts)
    # Search right-to-left, skip trailing digit suffix, find first tier token
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].isdigit():
            continue
        if known_tier.match(parts[i]):
            tier = parts[i].upper()
            tier_idx = i
            break
        # Non-digit, non-tier token encountered — stop searching
        break

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
            cwd=BASE_DIR,
        )
        try:
            stdout, stderr = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            jobs[job_id] = {'status': 'error', 'message': 'Scraper timed out after 120 seconds'}
            return

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
    # Prune completed/error jobs (keep only running ones + last 50)
    running = any(j.get('status') == 'running' for j in jobs.values())
    if running:
        return jsonify({'error': 'A draw is already in progress'}), 409
    # Remove non-running jobs beyond the last 50
    done_keys = [k for k, v in jobs.items() if v.get('status') != 'running']
    for k in done_keys[:-50]:
        jobs.pop(k, None)

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
    return send_from_directory(BASE_DIR / 'cards', filename)


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


if __name__ == '__main__':
    app.run(debug=True)
