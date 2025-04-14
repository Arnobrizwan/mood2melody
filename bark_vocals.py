from bark import generate_audio, preload_models
import numpy as np
from scipy.io.wavfile import write
import os

def generate_vocals(text, output_path="vocals.wav", speaker="v2/en_speaker_6"):
    try:
        preload_models()
        print(f"🎶 Generating vocals for: {text}")
        audio_array = generate_audio(text, history_prompt=speaker)
        write(output_path, 24000, audio_array)
        print(f"✅ Vocal audio saved: {output_path}")
        return output_path
    except Exception as e:
        print("❌ Bark vocal generation failed:", e)
        return None