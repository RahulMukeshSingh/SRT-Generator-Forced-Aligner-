import os
import shutil
import subprocess
import tempfile
import re

def reinject_case_and_characters(word_intervals, original_script):
    """
    Replace lowercased/normalized word_text with original text from the script.
    Preserves punctuation, casing, emojis, etc.
    """
    # Split script into words while keeping punctuation
    words_from_script = re.findall(r"\S+", original_script)
    updated_intervals = []
    script_index = 0

    for interval in word_intervals:
        word = interval.get("text", "")
        if not word.strip():
            continue
        # Try to match loosely: ignore case + punctuation
        while script_index < len(words_from_script):
            candidate = words_from_script[script_index]
            script_index += 1
            # Normalize both for comparison
            clean_candidate = re.sub(r'\W+', '', candidate).lower()
            clean_word = re.sub(r'\W+', '', word).lower()
            if clean_candidate == clean_word:
                interval["text"] = candidate
                break
        updated_intervals.append(interval)

    return updated_intervals

def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

def parse_textgrid(file_path: str) -> list:
    """
    Parse a TextGrid file and extract word intervals only from the 'words' tier.
    Returns a list of dictionaries with keys: xmin, xmax, text.
    """
    intervals = []
    current_interval = {}
    in_words_tier = False

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("name ="):
                tier_name = line.split("=")[1].strip().strip('"')
                in_words_tier = (tier_name.lower() == "words")
            elif in_words_tier and line.startswith("xmin ="):
                current_interval["xmin"] = float(line.split("=")[1].strip())
            elif in_words_tier and line.startswith("xmax ="):
                current_interval["xmax"] = float(line.split("=")[1].strip())
            elif in_words_tier and line.startswith("text ="):
                text_val = line.split("=", 1)[1].strip().strip('"')
                current_interval["text"] = text_val
                intervals.append(current_interval)
                current_interval = {}

    return intervals

def group_words_into_sentences(word_intervals: list, max_chars: int) -> list:
    """
    Group word intervals into sentences suitable for mobile display.
    Groups words until a sentence-ending punctuation is encountered
    or until the current line reaches a specified maximum character length.
    Returns a list of tuples: (start_time, end_time, sentence_text).
    """
    subtitles = []
    current_sentence = ""
    sentence_start = None
    sentence_end = None
    for word in word_intervals:
        word_text = word.get("text", "").strip()
        if not word_text:
            continue
        if sentence_start is None:
            sentence_start = word["xmin"]
        if current_sentence:
            # Add a space before adding new word.
            new_sentence = current_sentence + " " + word_text
        else:
            new_sentence = word_text

        # If adding this word exceeds the max_chars for this video type,
        # or if the word ends with punctuation, end the current subtitle line.
        if len(new_sentence) > max_chars or word_text[-1] in ".!?":
            current_sentence = new_sentence
            sentence_end = word["xmax"]
            subtitles.append((sentence_start, sentence_end, current_sentence.strip()))
            current_sentence = ""
            sentence_start = None
            sentence_end = None
        else:
            current_sentence = new_sentence

    # Append any leftover sentence.
    if current_sentence and sentence_start is not None:
        subtitles.append((sentence_start, word_intervals[-1]["xmax"], current_sentence.strip()))
    return subtitles

def create_srt(subtitles: list, output_file: str):
    """
    Write the list of subtitle tuples (start, end, text) to an SRT file.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(subtitles, start=1):
            f.write(f"{idx}\n")
            f.write(f"{seconds_to_timestamp(start)} --> {seconds_to_timestamp(end)}\n")
            f.write(f"{text}\n\n")

def main(video_type: str, audio_file: str, script_file: str):
    """
    Main function:
      - Sets up a temporary MFA corpus.
      - Runs forced alignment using MFA.
      - Parses the resulting TextGrid file and smartly groups word intervals
        into single-line subtitles based on the video type.
      - Generates an SRT file with a naming convention: {Script_File_Name}_{Video_Type}.srt.
    """
    # Determine the maximum characters per subtitle based on video type.
    # For vertical videos ("Shorts"), use a lower threshold.
    if video_type.lower() == "shorts":
        max_chars = 30  # fewer words per line for smaller screens
    else:
        max_chars = 50  # more words per line for horizontal videos

    with tempfile.TemporaryDirectory() as corpus_dir, tempfile.TemporaryDirectory() as output_dir:
        base_name = os.path.splitext(os.path.basename(script_file))[0]
        transcript_dest = os.path.join(corpus_dir, base_name + ".txt")
        audio_dest = os.path.join(corpus_dir, base_name + os.path.splitext(audio_file)[1])
        shutil.copy(script_file, transcript_dest)
        shutil.copy(audio_file, audio_dest)

        # Update these paths to point to your actual dictionary and acoustic model.
        dictionary_path = "dictionaries/english_india_mfa.dict"      
        acoustic_model_path = "models/english_mfa.zip"  


        # mfa_command = [
        #     "mfa", "align",
        #     corpus_dir,
        #     dictionary_path,
        #     acoustic_model_path,
        #     output_dir,
        #     "--clean",
        #     "--quiet"
        # ]

        mfa_command = [
            "mfa", "align",
            corpus_dir,
            dictionary_path,
            acoustic_model_path,
            output_dir,
            "--use_g2p", "True",
            "--single_speaker",
            "--clean",
            "--quiet"
        ]
        try:
            print("Running Montreal Forced Aligner...")
            subprocess.run(mfa_command, check=True)
        except subprocess.CalledProcessError as e:
            print("MFA alignment failed:", e)
            return

        textgrid_file = os.path.join(output_dir, base_name + ".TextGrid")
        if not os.path.exists(textgrid_file):
            raise FileNotFoundError("TextGrid file not found after MFA alignment.")

        word_intervals = parse_textgrid(textgrid_file)
        with open(script_file, 'r', encoding='utf-8') as sf:
            original_script = sf.read()

        # 🪄 Re-inject real casing, emojis, punctuation
        word_intervals = reinject_case_and_characters(word_intervals, original_script)
        if not word_intervals:
            raise ValueError("No word intervals found in the TextGrid file.")

        subtitles = group_words_into_sentences(word_intervals, max_chars)
        output_srt_file = f"{base_name}_{video_type}.srt"
        create_srt(subtitles, output_srt_file)
        print("SRT file created:", output_srt_file)

if __name__ == "__main__":
    # Example usage: update these variables with the correct paths and settings.
    video_type = "Shorts"  # "Shorts" for vertical, "Long" for horizontal
    audio_file = "audio/part.mp3"      # TTS-generated audio file (mp3)
    
    script_file = "scripts/Ghibli_Art_Hinglish.txt"    # Script text file
    
    main(video_type, audio_file, script_file)

