"""
Deepgram Speech-to-Text for ATC voice commands.

The ENTIRE recording session runs in a background thread — nothing audio-related
ever touches the main pygame thread, preventing freezes from pygame/PortAudio conflicts.

Usage (from simulation.py):
  # PTT pressed:
  stt.begin_ptt_session(on_transcript_callback)

  # PTT released:
  stt.end_ptt_session()

Requires:
  pip install sounddevice numpy requests
  Deepgram API key in data/settings.json → "deepgram_api_key"
"""

from __future__ import annotations

import io
import threading
import traceback
import wave
from typing import Callable, Optional

from ._audio_log import _get_logger
log = _get_logger("audio.stt")

# Optional deps — fail gracefully so the sim still launches without them
try:
    import sounddevice as sd
    import numpy as np
    _SOUNDDEVICE_OK = True
except ImportError:
    _SOUNDDEVICE_OK = False
    log.error("sounddevice not installed. Run: pip install sounddevice numpy")

# Use stdlib urllib instead of requests to avoid shadowing by local requests.py
import urllib.request as _urllib_request
import urllib.error as _urllib_error
_REQUESTS_OK = True  # always available (stdlib)


SAMPLE_RATE = 16000
CHANNELS    = 1
DTYPE       = "int16"


class DeepgramSTT:
    """
    PTT recorder → Deepgram transcription.
    All audio work happens in a daemon thread; the main thread only sets an event.
    """

    def __init__(self, api_key: str, mic_device: int = -1):
        self.api_key    = api_key
        self.mic_device = None if mic_device == -1 else mic_device  # None = system default
        self.available  = _SOUNDDEVICE_OK and bool(api_key)

        log.info(f"Init — sounddevice={_SOUNDDEVICE_OK}, "
                 f"key={'yes' if api_key else 'NO'}, available={self.available}")

        self._stop_event  = threading.Event()
        self._session_thread: Optional[threading.Thread] = None

    # ── Public API ────────────────────────────────────────────────────────────

    def begin_ptt_session(self, on_result: Callable[[Optional[str]], None]) -> bool:
        """
        Start recording in a background thread.
        on_result(transcript) will be called from that thread when done.
        Returns False immediately if unavailable.
        """
        if not self.available:
            log.warning("begin_ptt_session called but STT not available")
            return False

        if self._session_thread and self._session_thread.is_alive():
            log.warning("Session already running — ignoring PTT press")
            return False

        self._stop_event.clear()
        self._session_thread = threading.Thread(
            target=self._session_worker,
            args=(on_result,),
            daemon=True,
            name="STT-Session",
        )
        self._session_thread.start()
        log.debug("STT session thread started")
        return True

    def end_ptt_session(self):
        """Signal the recording thread to stop and transcribe."""
        log.debug("end_ptt_session — signalling stop")
        self._stop_event.set()

    # ── Worker (runs entirely in background thread) ───────────────────────────

    def _session_worker(self, on_result: Callable[[Optional[str]], None]):
        """Record until stop_event, then transcribe and call on_result."""
        frames: list = []

        def _callback(indata, frame_count, time_info, status):
            if status:
                log.warning(f"Audio callback status: {status}")
            frames.append(indata.copy())

        # Open mic stream inside the thread — avoids pygame/PortAudio conflict
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=_callback,
                blocksize=2048,
                device=self.mic_device,  # None = system default
            )
        except Exception as e:
            log.error(f"Failed to open mic stream: {e}\n{traceback.format_exc()}")
            on_result(None)
            return

        with stream:
            log.debug("Recording… waiting for PTT release")
            self._stop_event.wait()   # block until PTT released

        log.debug(f"Stream closed — {len(frames)} frames captured")

        if not frames:
            log.warning("No audio frames captured — mic may be muted or wrong device")
            on_result(None)
            return

        audio = np.concatenate(frames, axis=0)
        duration_s = len(audio) / SAMPLE_RATE
        if duration_s < 0.3:
            log.debug(f"Recording too short ({duration_s:.2f}s) — ignoring")
            on_result(None)
            return

        wav_bytes = self._to_wav(audio)
        log.info(f"Audio captured: {duration_s:.2f}s — sending {len(wav_bytes)} bytes to Deepgram")

        transcript = self._transcribe(wav_bytes)
        on_result(transcript)

    # ── Audio helpers ─────────────────────────────────────────────────────────

    def _to_wav(self, audio: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()

    def _transcribe(self, wav_bytes: bytes) -> Optional[str]:
        import json as _json
        base_url = "https://api.deepgram.com/v1/listen"
        # nova-3 has better accuracy on short phrases and aviation terminology
        # keywords boost recognition of common ATC terms
        # nova-3 uses keyterm (one per param, single words only) instead of keywords
        atc_keyterms = (
            # Core ATC commands
            "&keyterm=pushback&keyterm=taxi&keyterm=runway&keyterm=taxiway"
            "&keyterm=squawk&keyterm=wilco&keyterm=roger&keyterm=affirm"
            "&keyterm=ground&keyterm=tower&keyterm=clearance&keyterm=approved"
            "&keyterm=hold&keyterm=short&keyterm=cross&keyterm=contact&keyterm=expect"
            "&keyterm=heading&keyterm=maintain&keyterm=climb&keyterm=descend"
            "&keyterm=cleared&keyterm=expedite&keyterm=departure&keyterm=arrival"
            "&keyterm=intersection&keyterm=frequency&keyterm=altimeter&keyterm=position"
            "&keyterm=niner&keyterm=decimal"
            # NATO phonetic alphabet — critical for callsign recognition
            "&keyterm=alpha&keyterm=bravo&keyterm=charlie&keyterm=delta&keyterm=echo"
            "&keyterm=foxtrot&keyterm=golf&keyterm=hotel&keyterm=india&keyterm=juliet"
            "&keyterm=kilo&keyterm=lima&keyterm=mike&keyterm=november&keyterm=oscar"
            "&keyterm=papa&keyterm=quebec&keyterm=romeo&keyterm=sierra&keyterm=tango"
            "&keyterm=uniform&keyterm=victor&keyterm=whiskey&keyterm=xray"
            "&keyterm=yankee&keyterm=zulu"
        )
        query = (
            "model=nova-3&language=en-US&punctuate=false"
            f"&numerals=false&smart_format=false&filler_words=false{atc_keyterms}"
        )
        full_url = f"{base_url}?{query}"

        req = _urllib_request.Request(
            full_url,
            data=wav_bytes,
            method="POST",
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type":  "audio/wav",
            },
        )

        try:
            log.debug("POST → Deepgram nova-3…")
            with _urllib_request.urlopen(req, timeout=15) as resp:
                status = resp.status
                body   = _json.loads(resp.read().decode("utf-8"))

            log.debug(f"Deepgram HTTP {status}")

            alt = (body.get("results", {})
                       .get("channels", [{}])[0]
                       .get("alternatives", [{}])[0])

            transcript = alt.get("transcript", "").strip()
            confidence = alt.get("confidence", 0.0)
            log.info(f"Transcript: '{transcript}'  confidence={confidence:.3f}")

            if confidence < 0.25:
                log.warning(f"Confidence too low ({confidence:.3f}) — discarding")
                return None

            return transcript or None

        except _urllib_error.HTTPError as e:
            log.error(f"Deepgram HTTP {e.code}: {e.read().decode()}")
            return None
        except Exception as e:
            log.error(f"Deepgram request failed: {e}\n{traceback.format_exc()}")
            return None
