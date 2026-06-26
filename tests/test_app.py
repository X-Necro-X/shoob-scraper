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
    assert result['tier'] == 'unknown'


def test_parse_filename_no_tier():
    result = parse_filename("SomeName-Anime-1.png")
    assert result['tier'] == 'unknown'
    assert result['name'] != ''


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


def test_serve_card_not_found(client):
    resp = client.get('/cards/nonexistent-file.png')
    assert resp.status_code == 404


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
