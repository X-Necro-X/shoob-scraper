#!/usr/bin/env python3
"""
Process card images for printing:
  - Fill transparency with black
  - Save losslessly to ./print
  - Skips images already present in ./print (incremental)
  - Webm videos: middle frame is extracted before processing
"""

import sys
from pathlib import Path
from PIL import Image
import cv2


def extract_middle_frame(video_path):
    """Return the middle frame of a video as a PIL RGBA Image."""
    cap = cv2.VideoCapture(str(video_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 2))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Could not read middle frame from {video_path}")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA))


TARGET_HEIGHT = 980

def process_image(src, dst):
    img = (src if isinstance(src, Image.Image) else Image.open(src)).convert('RGBA')
    result = Image.new('RGBA', img.size, (0, 0, 0, 255))
    result = Image.alpha_composite(result, img)
    w, h = result.size
    if h < TARGET_HEIGHT:
        padded = Image.new('RGB', (w, TARGET_HEIGHT), (0, 0, 0))
        padded.paste(result.convert('RGB'), (0, (TARGET_HEIGHT - h) // 2))
        padded.save(dst, 'PNG')
    else:
        result.convert('RGB').save(dst, 'PNG')


def main():
    cards_dir = Path('cards')
    print_dir = Path('print')

    if not cards_dir.is_dir():
        print("./cards directory not found.")
        sys.exit(1)

    print_dir.mkdir(exist_ok=True)

    sources = sorted(cards_dir.glob('*.png')) + sorted(cards_dir.glob('*.webm'))
    if not sources:
        print("No PNG or WEBM files found in ./cards.")
        return

    processed = skipped = errors = 0

    for src in sources:
        dst = print_dir / (src.stem + '.png')
        if dst.exists():
            skipped += 1
            continue

        try:
            if src.suffix.lower() == '.webm':
                process_image(extract_middle_frame(src), dst)
            else:
                process_image(src, dst)
            print(f"  {src.name}")
            processed += 1
        except Exception as exc:
            print(f"  ERROR {src.name}: {exc}")
            errors += 1

    print(f"\n{processed} processed, {skipped} already done, {errors} skipped/errors.")


if __name__ == '__main__':
    main()
