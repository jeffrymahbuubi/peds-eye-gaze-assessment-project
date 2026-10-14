# Scanning Search assets: provenance

This file records the source of every file in this folder (SPEC-scanning-search-cues.md 4.3, S5).
Each file has a row with its generating model, prompt, date and the user's approval.

## Spoken prompts: `audio/en/prompt_<shape>.wav`

These play in the "Match the sample" search mode while the sample shape is shown.

- **Tool:** `mcp-audio-openrouter` `generate_voice` (the user's own MCP server).
- **Model:** `openai/gpt-audio` via OpenRouter, voice `shimmer`. The output is WAV (24 kHz mono
  raw take).
- **Generated:** 2026-10-14, tool timestamps 08:35-08:36 UTC. One take per file; the circle needed
  a retry after an HTTP 429.
- **Generation prompt** (the same as the park prompts, identical for all 6 except `<SENTENCE>`):
  "You are a warm, friendly female teacher reading aloud to a young child. Speak slowly and very
  clearly, with a gentle, encouraging smile in your voice. Say exactly this sentence and nothing
  else, with no introduction and no extra words before or after: "<SENTENCE>""
- **Post-processing** (as the park prompts):
  - silence trimmed at -40 dB below each take's peak, keeping 50 ms of padding;
  - 5 ms fades in and out;
  - the voiced part matched to -20.0 dBFS RMS (peaks -4.4 to -8.2 dBFS);
  - written as PCM 16-bit, 48 kHz, 2 channels.
- **Text check:** the generator's transcript and a local Whisper "small" transcription (talkthrough)
  of each final file both match the sentence word for word.
- **Raw takes:** `reference/raw_prompt_<shape>.wav`. These are not shipped in the exe.
- **Approved:** by the user, all 6, 2026-10-14.

| File | Sentence | Length (ms) | SHA-256 (first 12) | Raw SHA-256 (first 12) |
|---|---|---|---|---|
| `prompt_circle.wav` | Find the circle! | 2027 | 1dd93009897e | a984c3f6c2dd |
| `prompt_square.wav` | Find the square! | 2355 | 2330f53e8ee7 | 949fd5319931 |
| `prompt_triangle.wav` | Find the triangle! | 1698 | f8ddfa5a746a | 095f64f0979d |
| `prompt_diamond.wav` | Find the diamond! | 2006 | b4de921bc9d0 | 5efcfadc5691 |
| `prompt_hexagon.wav` | Find the hexagon! | 1952 | 6a02c13ae8db | 8c56bdf156bc |
| `prompt_star.wav` | Find the star! | 2046 | 0f7f94ed2cf6 | 650294bf31df |
