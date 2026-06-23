# BETMAN Audio Worker (Placeholder)

The audio worker processes audio extracted from media segments to produce:
- Voice Activity Detection (VAD) windows
- Scene classification (commentary, crowd, advertisement, silence, music)
- Race event detection (race start, finish call, result announcement)
- ASR transcription of commentary windows
- Excitement score time series

**Status:** This directory is a placeholder. The audio processing pipeline
is designed and documented in `docs/architecture.md` (Layer 3b).

## Planned Responsibilities

- Subscribe to `betman.audio` Redis queue (published by Consumer)
- For each audio chunk:
  1. Run VAD — only process windows with speech activity
  2. Classify scene type (commentary / ad / crowd / silence)
  3. For commentary windows: run ASR (Whisper-class model)
  4. Write to `transcript_segments` with `race_offset_ms`
  5. Extract excitement score (acoustic energy + pitch variance)
  6. Write to `excitement_scores`
  7. Detect named entities (horse names, positions, distances) → `commentary_entities`
  8. Generate `audio_events` for detected race stages

## Expected Tech

- Python 3.11 + asyncio
- `faster-whisper` or `openai-whisper` for ASR
- `pyannote.audio` or `silero-vad` for VAD
- `librosa` or `torchaudio` for acoustic feature extraction
- Custom fine-tuned classifier for scene classification
- GPU-enabled Docker image for production

## Cost Control

Process only VAD-positive windows. Skip windows classified as advertisement, music, or
silence. Batch transcription for non-live reprocessing jobs.
