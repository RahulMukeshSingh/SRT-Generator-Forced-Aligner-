import sys
import os
import shutil
import subprocess
import tempfile
import re
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog,
    QComboBox, QLineEdit, QMessageBox, QTextEdit
)

def reinject_case_and_characters(word_intervals, original_script):
    words_from_script = re.findall(r"\S+", original_script)
    updated_intervals = []
    script_index = 0

    for interval in word_intervals:
        word = interval.get("text", "")
        if not word.strip():
            continue
        while script_index < len(words_from_script):
            candidate = words_from_script[script_index]
            script_index += 1
            clean_candidate = re.sub(r'\W+', '', candidate).lower()
            clean_word = re.sub(r'\W+', '', word).lower()
            if clean_candidate == clean_word:
                interval["text"] = candidate
                break
        updated_intervals.append(interval)
    return updated_intervals

def seconds_to_timestamp(seconds: float) -> str:
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
    subtitles = []
    current_sentence = ""
    sentence_start = None
    for word in word_intervals:
        word_text = word.get("text", "").strip()
        if not word_text:
            continue
        if sentence_start is None:
            sentence_start = word["xmin"]
        new_sentence = f"{current_sentence} {word_text}".strip() if current_sentence else word_text
        if len(new_sentence) > max_chars or word_text[-1] in ".!?":
            subtitles.append((sentence_start, word["xmax"], new_sentence))
            current_sentence = ""
            sentence_start = None
        else:
            current_sentence = new_sentence
    if current_sentence and sentence_start is not None:
        subtitles.append((sentence_start, word_intervals[-1]["xmax"], current_sentence))
    return subtitles

def create_srt(subtitles: list, output_file: str):
    with open(output_file, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(subtitles, start=1):
            f.write(f"{idx}\n")
            f.write(f"{seconds_to_timestamp(start)} --> {seconds_to_timestamp(end)}\n")
            f.write(f"{text}\n\n")

def generate_subtitles(video_type, audio_file, script_file):
    dictionary_path = "dictionaries/english_india_mfa.dict"
    acoustic_model_path = "models/english_mfa.zip"
    max_chars = 30 if video_type.lower() == "shorts" else 60

    with tempfile.TemporaryDirectory() as corpus_dir, tempfile.TemporaryDirectory() as output_dir:
        base_name = os.path.splitext(os.path.basename(script_file))[0]
        transcript_dest = os.path.join(corpus_dir, base_name + ".txt")
        audio_dest = os.path.join(corpus_dir, base_name + os.path.splitext(audio_file)[1])
        shutil.copy(script_file, transcript_dest)
        shutil.copy(audio_file, audio_dest)

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

        subprocess.run(mfa_command, check=True)

        textgrid_file = os.path.join(output_dir, base_name + ".TextGrid")
        word_intervals = parse_textgrid(textgrid_file)

        with open(script_file, 'r', encoding='utf-8') as sf:
            original_script = sf.read()

        word_intervals = reinject_case_and_characters(word_intervals, original_script)
        subtitles = group_words_into_sentences(word_intervals, max_chars)
        output_srt_file = f"{base_name}_{video_type}.srt"
        create_srt(subtitles, output_srt_file)
        return output_srt_file


class SubtitleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRT Subtitle Generator")
        self.setMinimumWidth(500)
        layout = QVBoxLayout()

        self.video_type_label = QLabel("Select Video Type:")
        self.video_type_combo = QComboBox()
        self.video_type_combo.addItems(["Shorts", "Long"])

        self.audio_label = QLabel("Select Audio File:")
        self.audio_path = QLineEdit()
        self.audio_browse = QPushButton("Browse")
        self.audio_browse.clicked.connect(self.browse_audio)

        self.script_label = QLabel("Select Script File:")
        self.script_path = QLineEdit()
        self.script_browse = QPushButton("Browse")
        self.script_browse.clicked.connect(self.browse_script)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Progress will appear here...")

        self.run_button = QPushButton("Generate Subtitles")
        self.run_button.clicked.connect(self.run_alignment)

        layout.addWidget(self.video_type_label)
        layout.addWidget(self.video_type_combo)
        layout.addWidget(self.audio_label)
        layout.addWidget(self.audio_path)
        layout.addWidget(self.audio_browse)
        layout.addWidget(self.script_label)
        layout.addWidget(self.script_path)
        layout.addWidget(self.script_browse)
        layout.addWidget(self.log_box)
        layout.addWidget(self.run_button)

        self.setLayout(layout)
        self.process = None  # For MFA

    def browse_audio(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.wav)")
        if file:
            self.audio_path.setText(file)

    def browse_script(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Script File", "", "Text Files (*.txt)")
        if file:
            self.script_path.setText(file)

    def log(self, message):
        self.log_box.append(message)

    def run_alignment(self):
        video_type = self.video_type_combo.currentText()
        audio_file = self.audio_path.text()
        script_file = self.script_path.text()

        if not os.path.exists(audio_file) or not os.path.exists(script_file):
            QMessageBox.critical(self, "Error", "Please select valid audio and script files.")
            return

        self.run_button.setEnabled(False)
        self.log_box.clear()
        self.log("Setting up alignment...")

        try:
            # Prepare temp folders
            self.video_type = video_type
            self.audio_file = audio_file
            self.script_file = script_file
            self.dictionary_path = "dictionaries/english_india_mfa.dict"
            self.acoustic_model_path = "models/english_mfa.zip"
            self.max_chars = 30 if video_type.lower() == "shorts" else 60

            self.corpus_dir = tempfile.TemporaryDirectory()
            self.output_dir = tempfile.TemporaryDirectory()

            base_name = os.path.splitext(os.path.basename(script_file))[0]
            self.base_name = base_name
            transcript_dest = os.path.join(self.corpus_dir.name, base_name + ".txt")
            audio_dest = os.path.join(self.corpus_dir.name, base_name + os.path.splitext(audio_file)[1])
            shutil.copy(script_file, transcript_dest)
            shutil.copy(audio_file, audio_dest)

            # Launch MFA using QProcess
            self.process = QProcess()
            self.process.readyReadStandardOutput.connect(self.read_stdout)
            self.process.readyReadStandardError.connect(self.read_stderr)
            self.process.finished.connect(self.on_mfa_finished)

            command = [
                "mfa", "align",
                self.corpus_dir.name,
                self.dictionary_path,
                self.acoustic_model_path,
                self.output_dir.name,
                "--use_g2p", "True",
                "--single_speaker"
            ]
            self.log(f"Running command: {' '.join(command)}")
            self.process.start("mfa", command[1:])
        except Exception as e:
            self.run_button.setEnabled(True)
            QMessageBox.critical(self, "Error", str(e))

    def read_stdout(self):
        output = self.process.readAllStandardOutput().data().decode()
        self.log(output.strip())

    def read_stderr(self):
        error = self.process.readAllStandardError().data().decode()
        self.log(f"<span style='color:red'>{error.strip()}</span>")

    def on_mfa_finished(self):
        try:
            self.log("Alignment completed. Creating SRT...")

            textgrid_file = os.path.join(self.output_dir.name, self.base_name + ".TextGrid")
            word_intervals = parse_textgrid(textgrid_file)

            with open(self.script_file, 'r', encoding='utf-8') as sf:
                original_script = sf.read()

            word_intervals = reinject_case_and_characters(word_intervals, original_script)
            subtitles = group_words_into_sentences(word_intervals, self.max_chars)

            # Ask user where to save the SRT file
            suggested_name = f"{self.base_name}_{self.video_type}.srt"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save SRT File As",
                suggested_name,
                "SubRip Subtitle File (*.srt)"
            )

            if save_path:
                create_srt(subtitles, save_path)
                self.log(f"<b>SRT file saved as: {save_path}</b>")
                QMessageBox.information(self, "Success", f"SRT file saved as:\n{save_path}")
            else:
                self.log("<i>User cancelled SRT save dialog.</i>")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.run_button.setEnabled(True)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SubtitleGUI()
    window.show()
    sys.exit(app.exec())
