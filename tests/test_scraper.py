import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scraper import (
    load_seen, save_seen, generate_unique_number,
    calculate_page_and_index,
    sanitize_component, build_filename,
)


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
