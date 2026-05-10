"""Kokoro TTS helper module used by the simulator."""

from typing import Optional
import io

import soundfile as sf
from kokoro import KPipeline

DEFAULT_SAMPLE_RATE = 24_000
_PIPELINES = {}


def _get_pipeline(lang_code: str = "a") -> KPipeline:
    """Return a cached Kokoro pipeline for the requested language."""
    pipeline = _PIPELINES.get(lang_code)
    if pipeline is None:
        pipeline = KPipeline(lang_code=lang_code)
        _PIPELINES[lang_code] = pipeline
    return pipeline


def generate_tts_wav_buffer(
    text: str,
    *,
    voice: str = "af_heart",
    lang_code: str = "a",
    speed: float = 1.0,
) -> Optional[io.BytesIO]:
    """Generate a WAV audio buffer for the provided text.

    Args:
        text: The text to convert to speech
        voice: Voice to use for TTS (default: "af_heart")
        lang_code: Language code (default: "a" for English)
        speed: Playback speed multiplier (default: 1.0)

    Returns:
        io.BytesIO: In-memory WAV data or None if generation failed
    """
    clean_text = (text or "").strip()
    if not clean_text:
        return None

    pipeline = _get_pipeline(lang_code)
    audio_generator = pipeline(clean_text, voice=voice, speed=speed)

    buffer = io.BytesIO()
    chunk_count = 0
    with sf.SoundFile(
        buffer,
        mode="w",
        samplerate=DEFAULT_SAMPLE_RATE,
        channels=1,
        format="WAV",
        subtype="PCM_16",
    ) as audio_file:
        for _, _, audio in audio_generator:
            audio_file.write(audio)
            chunk_count += 1

    if chunk_count == 0:
        return None

    buffer.seek(0)
    return buffer


def demo():
    """Simple CLI demo for manual testing."""
    sample_text = (
        "Kokoro is an open-weight TTS model with 82 million parameters. "
        "Despite its lightweight architecture, it delivers comparable "
        "quality to larger models while being significantly faster and "
        "more cost-efficient."
    )
    buffer = generate_tts_wav_buffer(sample_text)
    if not buffer:
        print("No audio generated.")
        return

    with open("tts_demo.wav", "wb") as outfile:
        outfile.write(buffer.getbuffer())
    print("Saved demo audio to tts_demo.wav")


if __name__ == "__main__":
    demo()