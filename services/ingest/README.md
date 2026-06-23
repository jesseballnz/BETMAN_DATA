# BETMAN Ingest Service (Placeholder)

The ingest service handles the raw capture layer:
- Subscribing to HLS stream URLs (Trackside 1, Trackside 2)
- Downloading `.ts` segments
- Uploading raw segments to object storage (MinIO / S3)
- Triggering downstream media processing workers

**Status:** This directory is a placeholder. The ingestion logic is currently handled
by the Consumer service (`services/consumer/app/feed_manager.py`).
As the platform grows, segment download and upload logic will be extracted into
this dedicated service to allow independent scaling.

## Planned Responsibilities

- Long-lived HLS playlist polling
- Parallel segment downloads with retry logic
- Segment integrity verification (content hash)
- Metadata extraction (duration, codec, resolution, bitrate) via FFmpeg
- Upload to MinIO with structured key paths: `{feed_id}/{YYYY}/{MM}/{DD}/{segment_name}.ts`
- Publish `segment_ready` events to Redis for downstream workers

## Expected Tech

- Python 3.11 + asyncio
- `m3u8` library for HLS playlist parsing
- `httpx` for segment downloads
- `aiobotocore` for async S3/MinIO uploads
- `ffprobe` (FFmpeg) for media metadata extraction
