### `README.md`

```markdown
# SRT Subtitle Generator using Montreal Forced Aligner (MFA) & PyQt6

This application provides a graphical interface to generate SRT subtitle files from an audio file and a script using Montreal Forced Aligner (MFA). 
It supports both short and long video formats with configurable subtitle length.

---

## Basic Implementation

### Workflow:
1. User Input: Upload an audio file (WAV/MP3) and its corresponding script (TXT).
2. MFA Alignment:
   - Uses a pretrained acoustic model and optionally a pronunciation dictionary.
   - Aligns audio with the script and produces a TextGrid file.
3. Post-Processing:
   - Parses the TextGrid file to extract word-level timestamps.
   - Re-injects original casing and punctuation from the script.
   - Groups words into sentences for subtitle lines.
   - Converts them to standard `.srt` format.
4. GUI:
   - Built with PyQt6 for user-friendly interaction.
   - Logs progress and prompts for SRT file saving location.

---

## Environment Setup

### 1. Install Montreal Forced Aligner (MFA)

Create a dedicated environment using Conda for MFA:

```bash
conda env create -f mfa_env.yml
conda activate mfa_env
```

### 2. Install GUI dependencies (PyQt6)

Install PyQt6 and related packages in a separate or the same environment:

```bash
pip install PyQt6==6.7.1
```

---

## File Structure

```
.
├── main.py                    # The main PyQt6 application
├── dictionaries/
│   └── english_india_mfa.dict  # Optional dictionary file
├── models/
│   └── english_mfa.zip         # Acoustic model (download from MFA website)
├── mfa_env.yml               # Conda environment file for MFA
├── requirements.txt     # Pip dependencies for GUI
└── README.md
```

---

## Notes

- Ensure `mfa` CLI is available in your `PATH` (after installing via conda).
- If not using a dictionary, modify the `generate_subtitles` function and remove the `dictionary_path` argument.
- This project supports dictionary-free alignment using `--use_g2p True`.

---

## Resources

- Montreal Forced Aligner: https://montreal-forced-aligner.readthedocs.io/
- PyQt6 Docs: https://doc.qt.io/qtforpython/

---
```

---

### `Miniconda`
conda==24.9.2

### `mfa_env.yml` — Conda Environment File for MFA

```
name: mfa_env
channels:
  - defaults
  - conda-forge
dependencies:
  - python=3.10
  - montreal-forced-aligner=3.2.1
```

---

### `requirements.txt` — Pip Requirements for GUI

```txt
PyQt6==6.7.1
```