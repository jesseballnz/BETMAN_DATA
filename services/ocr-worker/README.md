# BETMAN OCR Worker (Placeholder)

The OCR worker processes video keyframes to extract structured text and classify
on-screen graphics for the BETMAN data warehouse.

**Status:** This directory is a placeholder. The OCR pipeline is designed and
documented in `docs/architecture.md` (Layer 3a).

## Planned Responsibilities

- Subscribe to `betman.ocr` Redis queue (published by Consumer)
- For each keyframe:
  1. Classify scene type (race, replay, studio, parade ring, ad, results graphic)
  2. If scene is relevant, run OCR on full frame and region-of-interest crops
  3. Normalise detected text (race number, horse names, odds values, clock, lower-thirds)
  4. Write to `ocr_observations` with bbox, confidence, and observation type
  5. Write to `scene_classifications`
  6. Cross-reference detected odds against `odds_snapshots` for validation
  7. If a results graphic is detected, attempt automated result parsing

## Expected Tech

- Python 3.11 + asyncio
- `easyocr` or `paddleocr` for text extraction
- `opencv-python` for frame preprocessing (crop, threshold, deskew)
- Custom CNN scene classifier (PyTorch / torchvision)
- `pytesseract` as fallback OCR for specific regions

## Key OCR Targets

| Region | Target Text |
|---|---|
| Top bar | Race number, meeting name, track |
| Tote panel | Odds/prices for each runner |
| Lower third | Horse name, barrier, weight, jockey |
| Race clock | Time since jump |
| Results graphic | Final positions, margins, dividends |
