# Calibration icons: provenance

This is the provenance record for every file in this folder (SPEC-app-drawn-calibration.md 4.6,
decisions U2, Q6, D3). Every file has a row here with its generating model, prompt, date and the
user's approval.

**Not Grid 3 art.** Grid 3 ships its calibration bee compiled inside its eye-gaze program files
(`SensorySoftware.EyeGaze*.dll`), with no loose image files. Smartbox art is licensed and was
ruled out by decision U2, so every icon here is our own, AI-generated.

## Images

- **Tool:** `mcp-image-openrouter` `generate_image` (the user's own MCP server), with
  `SKIP_PROMPT_ENHANCEMENT=true`.
- **Model:** `google/gemini-3.1-flash-image` via OpenRouter (`quality: "quality"`), at 1:1 aspect,
  1024 x 1024 raw.
- **Generated:** 2026-10-13 (tool timestamps 08:02-08:04 UTC), one take per icon.
- **Style:** a flat vector character on a white disc with a thick dark navy ring, so it reads on the
  White, Black and Grey calibration backgrounds. The subject is centred, because the disc centre
  is the point the child fixates.
- **Pipeline:**
  1. The bee is generated first as the style anchor.
  2. The other five are generated with the bee as `inputImagePath` ("use only as the STYLE
     reference").
  3. Each is drawn on flat `#00FF00` with no green inside the disc, then keyed out with
     `tools/chroma_key.py`. The crop is 70..953 on both axes, the same for all six.
  4. Each is scaled to 384 x 384 (smooth).
- **Raw takes:** `reference/<name>_raw.png`. The `reference/` folder is not shipped in the exe.
- **Preview:** `reference/preview_sheet.png` shows all six on White / Black / Grey, large and small.
- **Approved:** by the user, all 6, 2026-10-13.

**Bee (anchor) prompt:** "A single cute cartoon bee icon for a children's eye-tracking calibration
target. Friendly smiling bee with bold yellow and black stripes, small white wings, big round eyes,
viewed from the front, centred. The bee sits inside a plain white circular disc with a thick dark
navy outline ring around the disc. Flat vector style, bold clean dark outlines, simple shapes,
high contrast, no text, no shadow, no gradient background. The area outside the white disc is a
completely flat, uniform pure green #00FF00 background with nothing else. Do not use any green
colour inside the disc."

**Other five, common prompt:** "Using the attached bee icon only as the STYLE reference (same flat
vector style, same bold dark navy outlines, same white circular disc with the same thick dark navy
ring, same size and framing, same flat pure green #00FF00 background outside the disc): draw
instead <SUBJECT>, centred in the white disc. No bee. No text, no shadow. Do not use any green
colour inside the disc."

| File | `<SUBJECT>` | SHA-256 (first 12) | Raw SHA-256 (first 12) |
|---|---|---|---|
| `bee.png` | (anchor prompt above) | f42ac4c652c1 | b0af889b4606 |
| `star.png` | a single cute smiling yellow five-pointed STAR with big round eyes | 22a8ac010095 | 572c08e60cd9 |
| `ball.png` | a single colourful beach BALL with red, yellow and blue segments and a small white highlight (no face) | 70cbb5638211 | 63bcfb66a541 |
| `fish.png` | a single cute smiling orange FISH with a big round eye and a blue fin and tail, seen from the side, swimming to the right (no water, no bubbles) | 877fcfea4344 | 4a64322d22bf |
| `flower.png` | a single cute FLOWER head seen from the front: pink petals around a round yellow centre with a small smiling face (no stem, no leaves) | 869934a20cd9 | cf8c4b8049e4 |
| `car.png` | a single cute small red toy CAR with big round headlight eyes and a smile, seen from the side, facing right, with dark wheels and light blue windows (no road) | 2a89fa1658b1 | a8d829a09096 |
