# Mood2Melody: Flask Web App with AI Music Generator 🎶

from flask import Flask, render_template, request, send_file
from textblob import TextBlob
from music21 import stream, note, tempo, meter, key, midi, instrument, chord
import subprocess
import os
import uuid
import random
import openai
from dotenv import load_dotenv
from bark_vocals import generate_vocals

# Load API Key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# ---------------------- Mood Detection ----------------------
def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.3:
        return 'happy'
    elif polarity < -0.3:
        return 'sad'
    else:
        return 'neutral'

# ---------------------- AI Lyrics Generator ----------------------
def generate_lyrics(mood, user_text):
    prompt = f"Write two poetic lines of lyrics that reflect a {mood} mood based on: '{user_text}'"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You're a creative songwriter."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.8
        )
        lyrics_text = response['choices'][0]['message']['content'].strip()
        lines = lyrics_text.split('\n')
        return lines[:2] if len(lines) >= 2 else lines + ["❤️", "❤️"]
    except Exception as e:
        print("❌ OpenAI Error (lyrics generation):", e)
        return ["AI lyric line 1", "AI lyric line 2"]

# ---------------------- Music Mapping ----------------------
def mood_to_music_params(mood, lyrics):
    return {
        'scale': 'C' if mood == 'happy' else 'A' if mood == 'sad' else 'D',
        'mode': 'major' if mood == 'happy' or mood == 'neutral' else 'minor',
        'tempo': 120 if mood == 'happy' else 60 if mood == 'sad' else 90,
        'instrument': instrument.Piano() if mood == 'happy' else instrument.Viola() if mood == 'sad' else instrument.AcousticGuitar(),
        'lyrics': lyrics
    }

# ---------------------- Music Generator ----------------------
def generate_music(mood_params, output_id):
    mid_filename = f"static/{output_id}.mid"
    os.makedirs("static", exist_ok=True)

    s = stream.Stream()
    s.append(key.Key(mood_params['scale'], mood_params['mode']))
    s.append(meter.TimeSignature('4/4'))
    s.append(tempo.MetronomeMark(number=mood_params['tempo']))

    melody_part = stream.Part()
    melody_part.insert(0, instrument.Piano())

    harmony_part = stream.Part()
    harmony_part.insert(0, instrument.Woodblock())

    lyrics = mood_params.get('lyrics', [])
    lyrics_index = 0
    note_count = 0

    notes = {
        'major': ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4'],
        'minor': ['A3', 'B3', 'C4', 'D4', 'E4', 'F4', 'G4']
    }[mood_params['mode']]

    for _ in range(8):
        pitch = random.choice(notes)
        melody_note = note.Note(pitch)
        melody_note.quarterLength = 1

        if lyrics_index < len(lyrics):
            melody_note.lyrics = [lyrics[lyrics_index]]
            lyrics_index += 1

        melody_part.append(melody_note)
        note_count += 1

        chord_root = note.Note(pitch)
        bg_chord = chord.Chord([chord_root, chord_root.transpose(4), chord_root.transpose(7)])
        bg_chord.duration.quarterLength = 1
        harmony_part.append(bg_chord)

    if note_count == 0:
        melody_part.append(note.Note("C4"))
        print("🛟 Fallback note added")

    print("🎼 Melody Notes:", [n.nameWithOctave for n in melody_part.notes])

    s.insert(0, melody_part)
    s.insert(0, harmony_part)

    mf = midi.translate.streamToMidiFile(s)
    mf.open(mid_filename, 'wb')
    mf.write()
    mf.close()
    print(f"✅ Generated {note_count} melody notes. MIDI saved: {mid_filename}")
    return mid_filename

# ---------------------- MIDI to MP3 ----------------------
def convert_to_mp3(mid_path, sf_path="FluidR3_GM.sf2"):
    wav_path = mid_path.replace(".mid", ".wav")
    mp3_path = mid_path.replace(".mid", ".mp3")

    from midi2audio import FluidSynth
    fs = FluidSynth(sound_font=sf_path)
    fs.midi_to_audio(mid_path, wav_path)

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, mp3_path],
        capture_output=True,
        text=True
    )
    print("FFmpeg stdout:", result.stdout)
    print("FFmpeg stderr:", result.stderr)

    if os.path.exists(mp3_path):
        print(f"✅ MP3 File Size: {os.path.getsize(mp3_path)} bytes")
        os.remove(wav_path)
        return mp3_path
    else:
        print("❌ MP3 generation failed")
        return None

# ---------------------- Flask Routes ----------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        user_text = request.form['user_text']
        mood = analyze_sentiment(user_text)
        lyrics = generate_lyrics(mood, user_text)
        params = mood_to_music_params(mood, lyrics)
        unique_id = str(uuid.uuid4())
        mid_file = generate_music(params, unique_id)
        mp3_file = convert_to_mp3(mid_file)

        vocal_path = generate_vocals(" ".join(lyrics), f"static/{unique_id}_vocals.wav")
        final_mix = f"static/{unique_id}_final.mp3"

        if vocal_path and os.path.exists(vocal_path):
            subprocess.run([
                "ffmpeg", "-y",
                "-i", mp3_file,
                "-i", vocal_path,
                "-filter_complex", "amix=inputs=2:duration=shortest",
                final_mix
            ])
            output_file = final_mix
        else:
            print("⚠️ Bark vocal generation failed. Skipping vocals.")
            output_file = mp3_file

        return render_template('index.html', mood=mood, music_file=output_file, lyrics=lyrics)
    return render_template('index.html')

@app.route('/download/<filename>')
def download(filename):
    return send_file(f"static/{filename}", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
