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


class AllCardsDownloaded(Exception):
    pass


BASE_URL = "https://shoob.gg/cards"
OUTPUT_DIR = "./cards"
SEEN_FILE = "./seen.json"
CARDS_PER_PAGE = 15


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
        raise AllCardsDownloaded("All cards have been downloaded.")
    while True:
        n = random.randint(1, total)
        if n not in seen_set:
            return n


def calculate_page_and_index(number: int, cards_per_page: int = CARDS_PER_PAGE) -> tuple:
    page = math.ceil(number / cards_per_page)
    index = (number - 1) % cards_per_page
    return page, index


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


async def fetch_total(page: Page) -> int:
    await page.goto(BASE_URL)
    total_el = page.locator("text=/TOTAL \\d+/i").first
    await total_el.wait_for(state="attached")
    text = await total_el.inner_text()
    m = re.search(r'Total (\d+)', text, re.IGNORECASE)
    if not m:
        raise RuntimeError("Could not parse total card count from page.")
    return int(m.group(1))


async def get_card_info(page: Page, card_page: int, card_index: int) -> dict:
    await page.goto(f"{BASE_URL}?page={card_page}")
    await page.locator('a[href^="/cards/info/"]').first.wait_for(state="attached")
    links = page.locator('a[href^="/cards/info/"]')
    await links.nth(card_index).click()
    await page.locator('ol li').nth(3).wait_for(state="attached")
    items = page.locator('ol li')
    tier_text = await items.nth(1).inner_text()
    anime_name = await items.nth(2).inner_text()
    card_name = await items.nth(3).inner_text()
    tier_num = re.search(r'\d+', tier_text)
    tier = f"T{tier_num.group()}" if tier_num else sanitize_component(tier_text)
    media_url = None

    # Try static image first
    img_loc = page.locator('img.img-fluid').first
    try:
        await img_loc.wait_for(state="attached", timeout=5000)
        media_url = await img_loc.get_attribute('src')
    except Exception:
        pass

    # Fall back to video (shoob serves .webm for animated cards)
    if not media_url:
        for sel in ('video source', 'video'):
            loc = page.locator(sel).first
            try:
                await loc.wait_for(state="attached", timeout=5000)
                media_url = await loc.get_attribute('src')
                if media_url:
                    break
            except Exception:
                pass

    if media_url and not media_url.startswith('http'):
        media_url = urllib.parse.urljoin(f"{BASE_URL}/", media_url)
    if not media_url:
        raise RuntimeError("Could not find image or video URL on card page.")
    return {
        'card_name': card_name.strip(),
        'anime_name': anime_name.strip(),
        'tier': tier,
        'image_url': media_url.strip(),
    }


async def download_image(url: str, dest: Path, page: Page) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.tmp')
    try:
        response = await page.context.request.get(url)
        if not response.ok:
            raise RuntimeError(f"Image download failed: HTTP {response.status}")
        body = await response.body()
        tmp.write_bytes(body)
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


async def run(headed: bool = False) -> str:
    seen = load_seen()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
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

            await download_image(info['image_url'], dest, page)

            seen.append(number)
            save_seen(seen)

            return dest.name
        finally:
            await browser.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Download a random shoob.gg card.")
    parser.add_argument('--headed', action='store_true', help='Show browser window')
    args = parser.parse_args()

    try:
        filename = await run(headed=args.headed)
        print(f"Downloaded: {filename}")
    except AllCardsDownloaded:
        print("All cards downloaded.")
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())
