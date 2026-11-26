"""CPU inference for Vivian with the bundled eSpeak NG shared library."""
import argparse
import ctypes as ct
import io
from pathlib import Path
import wave

import espeakng_loader
import torch

from . import en_text
from .infer import load_model, speak_text
from .text import SYMBOLS

DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[2] / "models/vivian-104000/inference.pt"


def configure_espeak():
    lib = espeakng_loader.load_library()
    data = str(Path(espeakng_loader.get_data_path()).parent).encode()
    if lib.espeak_Initialize(2, 0, data, 0) <= 0 or lib.espeak_SetVoiceByName(b"en-us") != 0:
        raise RuntimeError("Could not initialize the eSpeak NG en-us voice")
    lib.espeak_TextToPhonemes.argtypes = [ct.POINTER(ct.c_void_p), ct.c_int, ct.c_int]
    lib.espeak_TextToPhonemes.restype = ct.c_char_p

    def words(piece):
        buffer = ct.create_string_buffer(piece.encode())
        cursor = ct.cast(buffer, ct.c_void_p)
        parts = []
        while cursor.value:
            part = lib.espeak_TextToPhonemes(ct.byref(cursor), 1, 2 | (ord("_") << 8))
            if part is None:
                raise ValueError("eSpeak NG could not phonemize this word")
            parts.append(part.decode())
        return en_text.parse_espeak(" ".join(parts))

    en_text.set_frontend("espeak")
    en_text.espeak_words = words


def load_local(checkpoint):
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Place the Vivian inference checkpoint at {checkpoint}")
    state = torch.load(checkpoint, weights_only=True, map_location="cpu")
    if state["frontend"]["symbols"] != list(SYMBOLS) or tuple(state["config"]["speakers"]) != ("Vivian",):
        raise ValueError("Expected the Vivian bilingual symbol inventory and speaker")
    del state
    configure_espeak()
    torch.set_num_threads(2)
    # Colab fingerprints the CLI version string. The local demo uses the shared library.
    return load_model(checkpoint, check_frontend=False)


def synthesize_wav(model, text, speed=1.0):
    if not 0.7 <= speed <= 1.4:
        raise ValueError("语速范围为 0.7 至 1.4")
    with torch.inference_mode():
        samples, _ = speak_text(model, text, "Vivian", speed)
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setparams((1, 2, model.config.sample_rate, 0, "NONE", ""))
        wav.writeframes((samples * 32767).short().numpy().astype("<i2").tobytes())
    return audio.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    audio = synthesize_wav(load_local(args.checkpoint), args.text, args.speed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(audio)
    print(args.output)


if __name__ == "__main__":
    main()
