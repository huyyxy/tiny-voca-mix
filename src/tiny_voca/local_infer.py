"""CPU inference using the Misaki frontend."""
import argparse
import io
from pathlib import Path
import wave

import torch

from .infer import load_model, speak_text

def load_local(checkpoint):
    torch.set_num_threads(2)
    return load_model(checkpoint)


def synthesize_wav(model, text, speed=1.0, voice=None):
    if not 0.7 <= speed <= 1.4:
        raise ValueError("语速范围为 0.7 至 1.4")
    if voice is None:
        voice = model.config.speakers[0]
    if voice not in model.config.speakers:
        raise ValueError(f"Unknown speaker {voice!r}")
    with torch.inference_mode():
        samples, _ = speak_text(model, text, voice, speed)
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, model.config.sample_rate, 0, "NONE", ""))
        wav.writeframes((samples * 32767).short().numpy().astype("<i2").tobytes())
    return audio.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--voice", help="voice name in checkpoint")
    args = parser.parse_args()
    audio = synthesize_wav(load_local(args.checkpoint), args.text, args.speed, args.voice)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(audio)
    print(args.output)


if __name__ == "__main__":
    main()
