"""sherpa-onnx local TTS playback service for pilot/ATC transmissions.

Replaces the Deepgram API backend with sherpa-onnx offline inference.
The public interface (KokoroTTSService class, speak(), pause(), resume() …)
is unchanged so the rest of the codebase needs minimal edits.

Supported model types (set tts_model_type in settings.json):
    "kokoro"  – Kokoro-en-v0_19 (high quality, 9 EN speakers)  [recommended]
    "vits"    – Any VITS model, incl. VCTK multi-speaker (109 speakers)
    "piper"   – Piper single-speaker ONNX models

Model download instructions are in docs/tts_models.md.
"""

from __future__ import annotations

import io
import json as _json
import re
import threading
import time
import wave
from collections import deque, OrderedDict
from pathlib import Path
from typing import Dict, Optional

import pygame

from ._audio_log import _get_logger
log = _get_logger("audio.tts")

# ── sherpa-onnx import (graceful failure) ─────────────────────────────────────
try:
    import sherpa_onnx as _sherpa
    _SHERPA_AVAILABLE = True
except ImportError:
    _sherpa = None  # type: ignore
    _SHERPA_AVAILABLE = False
    log.error("sherpa-onnx not installed. Run: pip install sherpa-onnx")

# ── Phonetic / digit tables ────────────────────────────────────────────────────
phonetic_alphabet: Dict[str, str] = {
    "A": "ALPHA", "B": "BRAVO", "C": "CHARLIE", "D": "DELTA", "E": "ECHO",
    "F": "FOXTROT", "G": "GOLF", "H": "HOTEL", "I": "INDIA", "J": "JULIET",
    "K": "KILO", "L": "LIMA", "M": "MIKE", "N": "NOVEMBER", "O": "OSCAR",
    "P": "PAPA", "Q": "QUEBEC", "R": "ROMEO", "S": "SIERRA", "T": "TANGO",
    "U": "UNIFORM", "V": "VICTOR", "W": "WHISKEY", "X": "XRAY",
    "Y": "YANKEE", "Z": "ZULU",
}

digit_words: Dict[str, str] = {
    "0": "ZERO", "1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR",
    "5": "FIVE", "6": "SIX", "7": "SEVEN", "8": "EIGHT", "9": "NINE",
}

# ── Radio static ───────────────────────────────────────────────────────────────
radio_static_file = Path(__file__).resolve().parents[2] / "data/audio/sfx/tts-static.mp3"
radio_static_volume = 0.30

# ── Airline callsign lookup ────────────────────────────────────────────────────
CALLSIGN_FILE = Path(__file__).resolve().parents[2] / "airlines.json"
_callsign_cache: Optional[Dict[str, str]] = None


def _load_callsign_lookup() -> Dict[str, str]:
    global _callsign_cache
    if _callsign_cache is not None:
        return _callsign_cache
    lookup: Dict[str, str] = {}
    try:
        if CALLSIGN_FILE.exists():
            with CALLSIGN_FILE.open("r", encoding="utf-8") as f:
                data = _json.load(f)
            for entry in data:
                code = (entry.get("airline_icao") or "").strip().upper()
                spoken = (entry.get("callsign") or entry.get("name") or "").strip()
                if code and spoken:
                    lookup[code] = spoken
            log.info(f"Loaded {len(lookup)} airline callsigns")
    except Exception as exc:
        log.error(f"Failed to load callsigns: {exc}")
    _callsign_cache = lookup
    return lookup


# ── Audio conversion helper ────────────────────────────────────────────────────

def _samples_to_wav(samples, sample_rate: int) -> io.BytesIO:
    """Convert sherpa-onnx float32 samples to an in-memory WAV buffer."""
    import struct
    buf = io.BytesIO()
    n = len(samples)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)           # 16-bit PCM
        wf.setframerate(sample_rate)
        # Convert float [-1, 1] → int16
        pcm = bytearray(n * 2)
        for i, s in enumerate(samples):
            v = max(-32768, min(32767, int(s * 32767)))
            struct.pack_into("<h", pcm, i * 2, v)
        wf.writeframes(bytes(pcm))
    buf.seek(0)
    return buf


# ── sherpa-onnx model loader ───────────────────────────────────────────────────

def _build_tts(model_dir: str, model_type: str, num_threads: int) -> Optional[object]:
    """
    Construct and return a sherpa_onnx.OfflineTts object.

    model_dir  – directory that contains the ONNX file(s).
    model_type – "kokoro", "vits", or "piper".
    """
    if not _SHERPA_AVAILABLE:
        return None

    d = Path(model_dir)
    if not d.exists():
        log.error(f"Model directory not found: {d}")
        return None

    try:
        if model_type == "kokoro":
            # Expected files: model.onnx, voices.bin, tokens.txt,
            #                 espeak-ng-data/, date.fst, number.fst
            model_cfg = _sherpa.OfflineTtsModelConfig(
                kokoro=_sherpa.OfflineTtsKokoroModelConfig(
                    model=str(d / "model.onnx"),
                    voices=str(d / "voices.bin"),
                    tokens=str(d / "tokens.txt"),
                    data_dir=str(d / "espeak-ng-data"),
                ),
                provider="cpu",
                debug=False,
                num_threads=num_threads,
            )
            # Optional FST rules for number/date normalisation
            rule_fsts_parts = []
            for fname in ("date.fst", "number.fst", "phone.fst"):
                fpath = d / fname
                if fpath.exists():
                    rule_fsts_parts.append(str(fpath))
            rule_fsts = ",".join(rule_fsts_parts)
            # max_num_sentences is not used by Kokoro — omit it to suppress the warning
            cfg = _sherpa.OfflineTtsConfig(
                model=model_cfg,
                rule_fsts=rule_fsts,
            )

        elif model_type in ("vits", "piper"):
            # Expected files: model.onnx, tokens.txt
            # Optional:       lexicon.txt, espeak-ng-data/
            lexicon = str(d / "lexicon.txt") if (d / "lexicon.txt").exists() else ""
            data_dir = str(d / "espeak-ng-data") if (d / "espeak-ng-data").exists() else ""
            model_cfg = _sherpa.OfflineTtsModelConfig(
                vits=_sherpa.OfflineTtsVitsModelConfig(
                    model=str(d / "model.onnx"),
                    lexicon=lexicon,
                    tokens=str(d / "tokens.txt"),
                    data_dir=data_dir,
                ),
                provider="cpu",
                debug=False,
                num_threads=num_threads,
            )
            cfg = _sherpa.OfflineTtsConfig(
                model=model_cfg,
            )

        else:
            log.error(f"Unknown model type: {model_type!r}. Use 'kokoro', 'vits', or 'piper'.")
            return None

        tts = _sherpa.OfflineTts(cfg)
        log.info(f"sherpa-onnx loaded ({model_type}) — {tts.num_speakers} speaker(s), "
                 f"sample rate {tts.sample_rate} Hz")
        return tts

    except Exception as exc:
        log.error(f"Failed to load sherpa-onnx model: {exc}")
        return None


# ── Audio cache ────────────────────────────────────────────────────────────────
_tts_cache: OrderedDict = OrderedDict()   # (text, speaker_id) → wav BytesIO
_TTS_CACHE_MAX = 60


def _sherpa_speak(
    text: str,
    speaker_id: int,
    tts_engine,
    speed: float = 1.5,
) -> Optional[io.BytesIO]:
    """Generate speech locally via sherpa-onnx and return a WAV BytesIO."""
    cache_key = (text, speaker_id)
    if cache_key in _tts_cache:
        _tts_cache.move_to_end(cache_key)
        wav = _tts_cache[cache_key]
        wav.seek(0)
        return wav

    try:
        audio = tts_engine.generate(text, sid=speaker_id, speed=speed)
        if not audio.samples:
            log.warning(f"Empty audio returned for: {text[:60]!r}")
            return None
        log.debug(f"Generated sid={speaker_id} speed={speed}x  [{text[:60]}]")
        wav = _samples_to_wav(audio.samples, audio.sample_rate)
    except Exception as exc:
        log.error(f"Generation error: {exc}")
        return None

    _tts_cache[cache_key] = wav
    if len(_tts_cache) > _TTS_CACHE_MAX:
        _tts_cache.popitem(last=False)
    return wav


# ── Service class ──────────────────────────────────────────────────────────────

class KokoroTTSService:
    """
    sherpa-onnx offline TTS backend.

    Drop-in replacement for the old Deepgram-based KokoroTTSService.
    Configure via settings.json:
        tts_model_dir   – path to the model directory (absolute or relative to project root)
        tts_model_type  – "kokoro" (default), "vits", or "piper"
        tts_speed       – speech rate multiplier (default 1.5)
        tts_num_threads – CPU threads for inference (default 2)
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        model_dir: str = "",
        model_type: str = "kokoro",
        num_threads: int = 2,
        speed: float = 1.1,
        max_queue: int = 5,
        enable_radio_static: bool = True,
        # Kept for backward compat — ignored
        api_key: str = "",        # noqa: ARG002
        voice: Optional[str] = None,  # noqa: ARG002
        lang_code: str = "a",    # noqa: ARG002
    ) -> None:
        self.speed = speed
        self.max_queue = max_queue
        self.enable_radio_static = enable_radio_static
        self.callsign_lookup = _load_callsign_lookup()

        # Resolve model_dir relative to project root if needed
        if model_dir and not Path(model_dir).is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            model_dir = str(project_root / model_dir)

        # Load TTS engine
        self._tts = _build_tts(model_dir, model_type, num_threads) if model_dir else None
        self.num_speakers: int = self._tts.num_speakers if self._tts else 1
        self.enabled = enabled and self._tts is not None

        # Per-callsign speaker ID mapping
        self.voice_mapping: Dict[str, int] = {}

        # Queue / playback state
        self._tts_queue: deque = deque()
        self._is_playing = False
        self._queue_lock = threading.Lock()
        self._pause_checker = None
        self._current_channel = None

        # Radio static
        self.radio_static_sound: Optional[pygame.mixer.Sound] = None
        self.radio_static_channel: Optional[pygame.mixer.Channel] = None
        if self.enable_radio_static:
            self._load_radio_static()

        if not self._tts:
            if not model_dir:
                log.warning("No model directory configured — TTS disabled. "
                            "Set tts_model_dir in settings.json.")
            # else: _build_tts already logged the error
        elif not enabled:
            log.info("TTS disabled by settings.")
        else:
            log.info(f"sherpa-onnx TTS ready — {self.num_speakers} voice(s), speed={speed}x")
            # Warm up the model in the background so the first in-game
            # transmission plays without the cold-start delay (~1-2 s).
            threading.Thread(target=self._warmup, daemon=True).start()

    # ── Public API ─────────────────────────────────────────────────────────────

    def _warmup(self) -> None:
        """Run one silent inference to load ONNX weights into CPU cache."""
        try:
            audio = self._tts.generate("ready", sid=0, speed=self.speed)
            _ = _samples_to_wav(audio.samples, audio.sample_rate)
            log.info("Model warmed up — first transmission will play instantly")
        except Exception as exc:
            log.warning(f"Warmup error (non-fatal): {exc}")

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled and self._tts is not None

    def set_radio_static_enabled(self, enabled: bool) -> None:
        self.enable_radio_static = enabled
        if not enabled and self.radio_static_channel:
            try:
                self.radio_static_channel.stop()
            except Exception:
                pass

    def set_pause_checker(self, pause_checker) -> None:
        self._pause_checker = pause_checker

    def pause(self) -> None:
        for ch in (self._current_channel, self.radio_static_channel):
            if ch:
                try:
                    ch.pause()
                except Exception:
                    pass

    def resume(self) -> None:
        for ch in (self._current_channel, self.radio_static_channel):
            if ch:
                try:
                    ch.unpause()
                except Exception:
                    pass

    def get_voice_for_callsign(self, callsign: str) -> int:
        """Return a stable speaker ID for the given callsign."""
        base = callsign.strip() if callsign else ""
        if base in self.voice_mapping:
            return self.voice_mapping[base]
        sid = abs(hash(base)) % max(self.num_speakers, 1)
        self.voice_mapping[base] = sid
        return sid

    def speak(
        self,
        text: str,
        callsign: Optional[str] = None,
        voice=None,               # int speaker_id, or None for auto-assign
        on_ready_callback=None,   # called just before audio starts (text display)
        on_complete_callback=None,  # called after audio finishes (exchange unlock)
    ) -> None:
        if not text:
            return
        if not self.enabled:
            if on_ready_callback:
                try:
                    on_ready_callback()
                except Exception as e:
                    log.error(f"Callback error (TTS disabled): {e}")
            if on_complete_callback:
                try:
                    on_complete_callback()
                except Exception as e:
                    log.error(f"Complete callback error (TTS disabled): {e}")
            return

        # Resolve speaker ID
        if voice is None:
            if callsign is None:
                words = text.split()
                callsign = words[0] if words else ""
            speaker_id = self.get_voice_for_callsign(callsign)
        elif isinstance(voice, int):
            speaker_id = voice % max(self.num_speakers, 1)
        else:
            # Legacy string voice from aircraft.assigned_voice — hash it to an ID
            speaker_id = abs(hash(str(voice))) % max(self.num_speakers, 1)

        prepared = self._naturalize_callsigns(self._normalize_atc(text))

        should_start = False
        with self._queue_lock:
            while len(self._tts_queue) >= self.max_queue:
                dropped = self._tts_queue.popleft()
                log.warning(f"Queue full, dropping: {dropped[0][:40]}…")
                # Fire both callbacks so nothing stays locked
                for _cb in (dropped[2], dropped[3]):
                    if _cb:
                        try:
                            _cb()
                        except Exception:
                            pass
            self._tts_queue.append((prepared, speaker_id, on_ready_callback, on_complete_callback))
            if not self._is_playing:
                should_start = True

        if should_start:
            self._process_queue()

    def shutdown(self) -> None:
        self.enabled = False

    # ── Internal queue / playback ──────────────────────────────────────────────

    def _process_queue(self) -> None:
        with self._queue_lock:
            if self._is_playing or not self._tts_queue:
                return
            if self._pause_checker and self._pause_checker():
                return
            self._is_playing = True
            text, speaker_id, cb, complete_cb = self._tts_queue.popleft()

        threading.Thread(
            target=self._play_text,
            args=(text, speaker_id, cb, complete_cb),
            daemon=True,
        ).start()

    def _play_text(
        self,
        text: str,
        speaker_id: int,
        on_ready_callback=None,
        on_complete_callback=None,
    ) -> None:
        static_channel = None
        try:
            wav_buf = _sherpa_speak(text, speaker_id, self._tts, self.speed)
            if not wav_buf:
                log.warning(f"No audio returned for: {text[:60]}")
                if on_ready_callback:
                    try:
                        on_ready_callback()
                    except Exception:
                        pass
                if on_complete_callback:
                    try:
                        on_complete_callback()
                    except Exception:
                        pass
                return

            try:
                sound = pygame.mixer.Sound(file=wav_buf)
            except Exception as exc:
                log.error(f"pygame Sound load error: {exc}")
                if on_ready_callback:
                    try:
                        on_ready_callback()
                    except Exception:
                        pass
                if on_complete_callback:
                    try:
                        on_complete_callback()
                    except Exception:
                        pass
                return

            if on_ready_callback:
                try:
                    on_ready_callback()
                except Exception as e:
                    log.error(f"on_ready_callback error: {e}")

            # Wait if paused (e.g. PTT is active)
            while self._pause_checker and self._pause_checker():
                time.sleep(0.1)

            static_channel = self._start_static()
            channel = sound.play()
            self._current_channel = channel
            if channel:
                self._wait_for_channel(channel)
            if static_channel:
                static_channel.stop()
            self._current_channel = None

            # Audio finished — notify exchange manager so the next aircraft can transmit
            if on_complete_callback:
                try:
                    on_complete_callback()
                except Exception as e:
                    log.error(f"on_complete_callback error: {e}")

        except Exception as exc:
            log.error(f"_play_text error: {exc}")
            if static_channel:
                try:
                    static_channel.stop()
                except Exception:
                    pass
            if on_complete_callback:
                try:
                    on_complete_callback()
                except Exception:
                    pass
        finally:
            self._is_playing = False
            self._process_queue()

    # ── Audio helpers ──────────────────────────────────────────────────────────

    def _load_radio_static(self) -> None:
        if not radio_static_file.exists():
            return
        try:
            self.radio_static_sound = pygame.mixer.Sound(str(radio_static_file))
            self.radio_static_sound.set_volume(radio_static_volume)
        except Exception as exc:
            log.error(f"Failed to load radio static: {exc}")

    def _start_static(self) -> Optional[pygame.mixer.Channel]:
        if not self.enable_radio_static or not self.radio_static_sound:
            return None
        try:
            if self.radio_static_channel:
                try:
                    self.radio_static_channel.stop()
                except Exception:
                    pass
            ch = self.radio_static_sound.play(loops=-1)
            if ch:
                ch.set_volume(radio_static_volume)
            self.radio_static_channel = ch
            return ch
        except Exception as exc:
            log.error(f"Radio static playback error: {exc}")
            return None

    def _wait_for_channel(self, channel: pygame.mixer.Channel) -> None:
        try:
            while channel and channel.get_busy():
                if self._pause_checker and self._pause_checker():
                    try:
                        channel.pause()
                    except Exception:
                        pass
                    if self.radio_static_channel:
                        try:
                            self.radio_static_channel.pause()
                        except Exception:
                            pass
                    while self._pause_checker and self._pause_checker():
                        time.sleep(0.1)
                    try:
                        channel.unpause()
                    except Exception:
                        pass
                    if self.radio_static_channel:
                        try:
                            self.radio_static_channel.unpause()
                        except Exception:
                            pass
                else:
                    time.sleep(0.05)
        except Exception as e:
            log.error(f"Channel wait error: {e}")
        finally:
            if self.radio_static_channel:
                try:
                    self.radio_static_channel.stop()
                except Exception:
                    pass

    # ── Text normalisation ─────────────────────────────────────────────────────

    def _normalize_atc(self, text: str) -> str:
        """Expand ATC-specific shorthand before TTS synthesis."""
        def _spell(s: str) -> str:
            return " ".join(digit_words.get(c, c) for c in s if c.isdigit())

        # FL350 → "flight level three five zero"
        text = re.sub(
            r'\bFL(\d{2,3})\b',
            lambda m: f"flight level {_spell(m.group(1))}",
            text, flags=re.IGNORECASE,
        )
        # Radio freq 118.0–136.975 MHz
        text = re.sub(
            r'\b(1[1-3]\d)\.(\d{1,3})\b',
            lambda m: f"{_spell(m.group(1))} point {_spell(m.group(2))}",
            text,
        )
        # Altimeter setting 29.xx / 30.xx
        text = re.sub(
            r'\b(2[89]|30)\.(\d{2})\b',
            lambda m: f"{_spell(m.group(1))} point {_spell(m.group(2))}",
            text,
        )
        return text

    def _naturalize_callsigns(self, text: str) -> str:
        text = self._convert_taxiway_names_to_phonetic(text)
        if not self.callsign_lookup:
            return text

        pattern = re.compile(r"\b([A-Z]{2,3})([0-9][A-Z0-9]*)\b")

        def replace(m: re.Match) -> str:
            prefix, suffix = m.group(1), m.group(2)
            airline = self.callsign_lookup.get(prefix)
            spoken_suffix = self._spell_callsign("", suffix).strip()
            if airline:
                return f"{airline} {spoken_suffix}".strip()
            return self._spell_callsign(prefix, suffix)

        return pattern.sub(replace, text)

    def _convert_taxiway_names_to_phonetic(self, text: str) -> str:
        result, last_end = [], 0
        for match in re.finditer(r'\b(via|taxiway)\s+', text, re.IGNORECASE):
            result.append(text[last_end:match.end()])
            remaining = text[match.end():]
            i = 0
            while i < len(remaining):
                if remaining[i].isupper() and remaining[i].isalpha():
                    next_ch = remaining[i + 1] if i + 1 < len(remaining) else ''
                    if next_ch in ' ,\t' or next_ch == '':
                        result.append(phonetic_alphabet.get(remaining[i], remaining[i]))
                        i += 1
                        if i < len(remaining) and remaining[i] == ' ':
                            result.append(' ')
                            i += 1
                        continue
                    else:
                        break
                elif remaining[i] == ',':
                    if i + 1 < len(remaining) and remaining[i + 1] == ' ':
                        j = i + 2
                        while j < len(remaining) and remaining[j] == ' ':
                            j += 1
                        if j < len(remaining) and remaining[j].isupper():
                            k = j + 1
                            while k < len(remaining) and remaining[k].isalnum():
                                k += 1
                            if k - j > 1:
                                break
                    result.append(remaining[i])
                    i += 1
                elif remaining[i] == ' ':
                    result.append(remaining[i])
                    i += 1
                else:
                    break
            last_end = match.end() + i
        result.append(text[last_end:])
        return ''.join(result)

    def _spell_callsign(self, prefix: str, suffix: str) -> str:
        spoken_prefix = " ".join(
            phonetic_alphabet.get(ch.upper(), ch.upper()) for ch in prefix
        )
        tokens = []
        i = 0
        while i < len(suffix):
            if suffix[i].isdigit():
                j = i
                while j < len(suffix) and suffix[j].isdigit():
                    j += 1
                num = suffix[i:j]
                pairs: list[str] = []
                d = num
                while len(d) > 2:
                    if len(d) % 2 == 1:
                        pairs.append(d[0])
                        d = d[1:]
                    else:
                        pairs.append(d[:2])
                        d = d[2:]
                if d:
                    pairs.append(d)
                tokens.extend(pairs)
                i = j
            elif suffix[i].isalpha():
                tokens.append(phonetic_alphabet.get(suffix[i].upper(), suffix[i].upper()))
                i += 1
            else:
                i += 1
        return f"{spoken_prefix} {' '.join(tokens)}".strip()
