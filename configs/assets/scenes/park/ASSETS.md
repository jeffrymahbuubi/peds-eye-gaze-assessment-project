# Park scene assets: provenance

Provenance record for every file in this folder (SPEC-scene-cause-effect-task.md 4.7, A10).
Each file must have a row here with its generating model, prompt, date and the user's approval.

## Spoken prompts: `audio/en/prompt_<object>.wav`

- **Tool:** `mcp-audio-openrouter` `generate_voice` (user's own MCP server).
- **Model:** `openai/gpt-audio` via OpenRouter; voice `shimmer`; output WAV (24 kHz raw take).
- **Generated:** 2026-10-11 (tool timestamps 2026-10-10 17:00-17:01 UTC); one take per file.
- **Generation prompt** (identical for all 8 except `<SENTENCE>`):
  "You are a warm, friendly female teacher reading aloud to a young child. Speak slowly and very
  clearly, with a gentle, encouraging smile in your voice. Say exactly this sentence and nothing
  else, with no introduction and no extra words before or after: "<SENTENCE>""
- **Post-processing:** silence trimmed at -40 dB below each take's peak with 50 ms padding kept;
  5 ms fades in and out; voiced part matched to -20.0 dBFS RMS (peaks -4.2 to -7.9 dBFS);
  written as PCM 16-bit, 48 kHz, 2 channels (same format as `configs/assets/sounds/forest_hit.wav`).
- **Text check:** the generator's transcript and a local Whisper "small" transcription of each
  final file both match the sentence word for word.
- **Approved:** by the user, all 8, 2026-10-11.

| File | Sentence | Length (ms) | SHA-256 (first 12) |
|---|---|---|---|
| `prompt_balloons.wav` | Make the balloons pop! | 2390 | 48657b79879d |
| `prompt_rainbow.wav` | Make the rainbow sparkle! | 2980 | b14f13a1757b |
| `prompt_seesaw.wav` | Make the seesaw go up and down! | 3920 | 38914d0c9667 |
| `prompt_apples.wav` | Make the apples fall! | 2180 | 15047d915082 |
| `prompt_cloud.wav` | Make the cloud float away! | 3910 | d9153d9582d1 |
| `prompt_bubbles.wav` | Make the bubbles fly! | 3250 | 31706a1ba96a |
| `prompt_bike.wav` | Make the bike ride away! | 3720 | 013a1d026500 |
| `prompt_swing.wav` | Make the swing go! | 2520 | 72dfbd3ec0d1 |

## Effect sounds, images

None yet (step 2 art and step 6).
