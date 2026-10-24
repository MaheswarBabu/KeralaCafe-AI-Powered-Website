"""
tts_service.py
---------------
Server-side text-to-speech for CafeMate, so the bot can actually SPEAK
Malayalam (and sound more natural in English) regardless of what voices the
visitor's browser/OS happens to have installed.

Uses the `edge-tts` package, which streams Microsoft's neural voices - no
API key, no billing. Voices used (override with env vars if you like):

    English  : en-IN-NeerjaNeural      (TTS_VOICE_EN)
    Malayalam: ml-IN-SobhanaNeural     (TTS_VOICE_ML)   [male option: ml-IN-MidhunNeural]

Replies in Malayalam mode usually mix Malayalam script with English dish
names ("... Chicken Biriyani ഞങ്ങളുടെ മെനുവിൽ ..."). A Malayalam voice tends to
mangle Latin-script words, so the text is split by script: Malayalam chunks
are read by the Malayalam voice, English chunks by the English voice, and the
MP3 pieces are joined back together in order.

If synthesis fails for any reason (no internet from the server, the service
changing, etc.) `synthesize()` returns None and /api/tts answers 204, which
makes the browser fall back to its own built-in voice - nothing breaks.

Note: edge-tts talks to an unofficial Microsoft endpoint. If it ever stops
working, `pip install -U edge-tts` usually fixes it.
"""

import asyncio
import os
import re
from collections import OrderedDict
from typing import List, Optional, Tuple

VOICE_EN = os.getenv("TTS_VOICE_EN", "en-IN-NeerjaNeural")
VOICE_ML = os.getenv("TTS_VOICE_ML", "ml-IN-SobhanaNeural")

MAX_CHARS = 1500          # keep requests small; replies/intros are far shorter
CACHE_SIZE = 200          # the intro is identical for every visitor - cache it
REQUEST_TIMEOUT = 20      # seconds, per whole reply

_cache: "OrderedDict[Tuple[str, str], bytes]" = OrderedDict()


def _is_ml_char(ch: str) -> bool:
    return "\u0d00" <= ch <= "\u0d7f"


def split_by_script(text: str) -> List[Tuple[str, str]]:
    """Split text into [("ml"|"en", chunk), ...] runs.

    Spaces, digits and punctuation don't decide the language - they stick to
    whichever run they're inside, so a sentence isn't chopped at every comma.
    Text with no letters at all is returned as a single "en" run.
    """
    runs: List[Tuple[str, str]] = []
    current: Optional[str] = None
    buf: List[str] = []

    for ch in text:
        if _is_ml_char(ch):
            lang: Optional[str] = "ml"
        elif ch.isalpha():
            lang = "en"
        else:
            lang = None  # neutral

        if lang is None:
            buf.append(ch)
            continue

        if current is None:
            current = lang
        elif lang != current:
            runs.append((current, "".join(buf)))
            buf = []
            current = lang
        buf.append(ch)

    if buf:
        runs.append((current or "en", "".join(buf)))

    # Drop runs that are only whitespace/punctuation (nothing to read out).
    return [(lang, chunk) for lang, chunk in runs if re.search(r"\w", chunk)]


async def _synth_chunk(text: str, voice: str) -> bytes:
    import edge_tts  # imported lazily so the app still starts without it

    communicate = edge_tts.Communicate(text, voice)
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            audio.extend(chunk["data"])
    if not audio:
        raise RuntimeError("no audio received")
    return bytes(audio)


async def synthesize(text: str, lang: str = "en-IN") -> Optional[bytes]:
    """Return MP3 bytes for `text`, or None if speech couldn't be produced.

    `lang` ("en-IN" / "ml-IN") only decides the voice for text that has no
    Malayalam letters in it; mixed text is always split by script.
    """
    text = re.sub(r"\s+", " ", text or "").strip()[:MAX_CHARS]
    if not text:
        return None

    key = (lang, text)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]

    runs = split_by_script(text)
    if not runs:
        return None

    # A message with no Malayalam letters is read entirely in the requested
    # language's voice (so an English reply stays a single, smooth request).
    if not any(run_lang == "ml" for run_lang, _ in runs):
        runs = [("ml" if lang.startswith("ml") else "en", text)]

    try:
        pieces = await asyncio.wait_for(
            asyncio.gather(
                *[_synth_chunk(chunk, VOICE_ML if run_lang == "ml" else VOICE_EN)
                  for run_lang, chunk in runs]
            ),
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as exc:  # network down, service changed, timeout, ...
        print(f"[tts_service] synthesis failed, browser voice will be used: {exc!r}")
        return None

    audio = b"".join(pieces)
    _cache[key] = audio
    if len(_cache) > CACHE_SIZE:
        _cache.popitem(last=False)
    return audio
