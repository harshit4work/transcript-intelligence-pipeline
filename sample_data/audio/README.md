# Audio directory

This pipeline is designed to take raw interview **audio** in, run it through
Whisper, and hand the transcript to the GPT-4 extraction chain.

For portability (no large binary files in the repo, no API key required to
try the project), the `sample_data/transcripts/` folder ships with 5
pre-transcribed interviews — formatted exactly like Whisper's timestamped
output — so the pipeline can be demoed end-to-end with zero setup.

If you drop a real `.mp3` / `.wav` / `.m4a` file in this folder and set
`OPENAI_API_KEY` in `.env`, `src/tip/transcription.py` will transcribe it
with the real Whisper API instead of reading a stub transcript. See the
README at the repo root, section "Live mode", for details.
