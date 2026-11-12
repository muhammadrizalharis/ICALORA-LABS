"""Transkrip Audio (ASR) dengan faster-whisper.

Model dimuat lazy & di-cache (default 'base', int8, CPU) agar tidak membebani
GPU bersama. Mendukung berkas audio/video umum via ffmpeg (bawaan PyAV).
"""

from __future__ import annotations

import os
import tempfile
import threading

_MODEL = None
_LOCK = threading.Lock()

_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
_CACHE_DIR = os.environ.get("WHISPER_CACHE", os.path.expanduser("~/.cache/icalora-whisper"))
# Beam search (>1) lebih akurat daripada greedy; default 5 seimbang akurasi/latensi.
_BEAM_SIZE = int(os.environ.get("WHISPER_BEAM", "5"))

# Batas aman ukuran unggahan audio (MB).
MAX_AUDIO_BYTES = 50 * 1024 * 1024

_ALLOWED_EXT = (
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus",
    ".mp4", ".webm", ".mkv", ".mov", ".wma",
)


def _get_model():
    global _MODEL
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                from faster_whisper import WhisperModel

                os.makedirs(_CACHE_DIR, exist_ok=True)
                _MODEL = WhisperModel(
                    _MODEL_SIZE,
                    device=_DEVICE,
                    compute_type=_COMPUTE,
                    download_root=_CACHE_DIR,
                )
    return _MODEL


def is_supported(filename: str) -> bool:
    return (filename or "").lower().endswith(_ALLOWED_EXT)


def transcribe_audio(filename: str, data: bytes, language: str | None = None) -> dict:
    """Transkripsi berkas audio/video menjadi teks + segmen berwaktu."""
    suffix = os.path.splitext(filename or "")[1] or ".mp3"
    model = _get_model()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            language=language or None,
            vad_filter=True,
            beam_size=_BEAM_SIZE,
        )
        seg_list: list[dict] = []
        parts: list[str] = []
        for s in segments:
            txt = s.text.strip()
            seg_list.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})
            parts.append(txt)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    full = " ".join(parts).strip()
    return {
        "text": full,
        "language": info.language,
        "language_probability": round(float(info.language_probability), 3),
        "duration": round(float(info.duration), 1),
        "segments": seg_list,
        "model": _MODEL_SIZE,
    }
