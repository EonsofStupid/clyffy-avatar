# Voice work dir

| Path | Role |
|------|------|
| `models/` | OuteTTS + WavTokenizer GGUFs |
| `samples/` | synthesized pack lines (24 kHz mono wav) |
| `drive/` | per-line lipsync mp4 + `drive_frames.jsonl` |
| `SAMPLES.md` | index + operator A/B |
| `tts_report.json` | last batch metadata |
| `clyffy-blend1-voice.mp3` | optional Drive reference (pull if missing) |
| `gate_proof_tone.wav` | non-voice G5 proof only |

```bash
python3 tools/voice_tts.py --from-pack --no-speaker
```
