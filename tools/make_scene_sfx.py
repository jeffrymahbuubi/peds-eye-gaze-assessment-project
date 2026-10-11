"""Make the Choice-making effect sounds from the raw Lyria cues (SPEC-scene-cause-effect-task.md 4.7, step 6).

Input: ``configs/assets/scenes/<scene>/reference/sfx_raw/<object>.mp3`` (google/lyria-3-clip-preview through
the user's ``mcp-audio-openrouter``, about 30 s each; prompts in ASSETS.md). For each object the cue is
decoded with Qt Multimedia (``QAudioDecoder``, the FFmpeg backend bundled with PySide6, so no extra tool),
its leading silence trimmed (-40 dB below its peak), cut to the effect's length from the scene manifest,
faded in 5 ms and out 300 ms, levelled to -22 dBFS RMS (2 dB under the spoken prompts) with peaks capped at
-3 dBFS, and written as PCM 16-bit, 48 kHz, 2 channels to ``audio/sfx/<object>.wav`` (what
``src/ui/scene_audio.py`` plays).

Usage (from the repository root): python tools/make_scene_sfx.py [scene]
"""

import sys
import wave
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QUrl
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.tasks.choice_scene import load_manifest, scene_folder  # noqa: E402

RATE, CHANNELS = 48000, 2
TARGET_RMS_DB, PEAK_DB = -22.0, -3.0
FADE_IN_S, FADE_OUT_S = 0.005, 0.3


def decode(path: Path) -> np.ndarray:
    """All samples of ``path`` as float32 in [-1, 1], shape (frames, 2), at 48 kHz."""
    fmt = QAudioFormat()
    fmt.setSampleRate(RATE)
    fmt.setChannelCount(CHANNELS)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    decoder = QAudioDecoder()
    decoder.setAudioFormat(fmt)
    decoder.setSource(QUrl.fromLocalFile(str(path)))
    chunks: list[np.ndarray] = []
    loop = QEventLoop()
    failure: list[str] = []

    def take() -> None:
        while decoder.bufferAvailable():
            buf = decoder.read()
            if buf.isValid():
                chunks.append(np.frombuffer(bytes(buf.constData()), np.int16).copy())

    decoder.bufferReady.connect(take)
    decoder.finished.connect(loop.quit)
    decoder.error.connect(lambda _e: (failure.append(decoder.errorString()), loop.quit()))
    decoder.start()
    loop.exec()
    take()
    if failure or not chunks:
        raise SystemExit(f"cannot decode {path}: {failure or 'no audio'}")
    return (np.concatenate(chunks).astype(np.float32) / 32768.0).reshape(-1, CHANNELS)


def shape(samples: np.ndarray, length_s: float) -> np.ndarray:
    level = np.abs(samples).max(axis=1)
    start = int(np.argmax(level > level.max() * 10 ** (-40 / 20)))
    out = samples[start:start + int(round(length_s * RATE))].copy()
    n_in, n_out = int(FADE_IN_S * RATE), int(FADE_OUT_S * RATE)
    out[:n_in] *= np.linspace(0, 1, n_in)[:, None]
    out[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
    rms = float(np.sqrt(np.mean(out**2)))
    out *= 10 ** (TARGET_RMS_DB / 20) / max(rms, 1e-9)
    peak = float(np.abs(out).max())
    if peak > 10 ** (PEAK_DB / 20):
        out *= 10 ** (PEAK_DB / 20) / peak
    return out


def write(path: Path, samples: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    QCoreApplication.instance() or QCoreApplication([])
    scene = sys.argv[1] if len(sys.argv) > 1 else "park"
    folder = scene_folder(scene)
    manifest = load_manifest(scene)
    for obj in manifest.objects:
        raw = folder / "reference" / "sfx_raw" / f"{obj.id}.mp3"
        if not raw.is_file():
            print(f"{obj.id}: no raw cue, skipped")
            continue
        out = shape(decode(raw), obj.effect.duration_ms / 1000)
        write(folder / "audio" / "sfx" / f"{obj.id}.wav", out)
        rms = 20 * np.log10(np.sqrt(np.mean(out**2)))
        peak = 20 * np.log10(np.abs(out).max())
        print(f"{obj.id}: {len(out) / RATE * 1000:.0f} ms, RMS {rms:.1f} dBFS, peak {peak:.1f} dBFS")


if __name__ == "__main__":
    main()
