---
name: video-qa
description: "Inspect rendered videos and HyperFrames outputs for technical delivery risks. Use when the user asks to QA, review, verify, inspect, validate, check, or troubleshoot an MP4/WebM/video render; when a video looks black, blank, static, corrupted, too short, wrong size, wrong fps, or suspicious; or before claiming a video task is complete. Produces ffprobe metadata, sampled frames, contact sheet, black/static-frame risk checks, and a video-qa-report.md."
---

# Video QA

Use this skill after a video has been rendered or when a video render looks suspicious. The goal is to prove what is actually inside the video, not merely that a render command exited successfully.

## Inputs

- Required: path to a rendered video file such as `.mp4` or `.webm`.
- Optional: expected duration, fps, resolution, platform, and intended content.
- Optional: HyperFrames project directory if the video came from HyperFrames.

## Outputs

Create these files in a confirmed project or temporary QA folder. Writing beside the video is acceptable only when that directory is the active project render folder and the paths do not already exist:

- `video-qa-report.md`
- `qa-frames/` sampled PNG frames
- `qa-frames/contact-sheet.png`

## Video QA Boundary Checkpoint

Before running probes or writing files, lock:

- Source video: exact absolute path, expected duration/fps/resolution/platform, and whether the file is a draft, private, student-facing, or public deliverable.
- Output target: exact report path and frame directory. Do not write into skill directories, plugin caches, broad home folders, or unrelated project roots.
- Write mode: default is no-clobber. Existing `video-qa-report.md`, `qa-frames/`, or `contact-sheet.png` require review and an explicit `--overwrite`.
- Privacy: keep private/student/client videos and frames local. Do not upload frames, contact sheets, or full videos to external services unless the user explicitly approves the exact destination.
- Scope: QA may probe and sample evidence only. It must not edit, transcode, repair, publish, upload, delete, or replace the source video.

## Workflow

1. Resolve the video path and confirm it exists.
2. Choose a confirmed QA output folder, usually `<video-dir>/video-qa/` or a project temp folder.
3. Run technical probe:

```bash
SKILL_DIR="<absolute path to installed video-qa skill>"
QA_DIR="<confirmed-output-dir>"
PYTHONDONTWRITEBYTECODE=1 python3 "$SKILL_DIR/scripts/video_probe.py" "<video>" --json --report "$QA_DIR/video-qa-report.md"
```

4. Extract frames:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 "$SKILL_DIR/scripts/extract_frames.py" "<video>" --out "$QA_DIR/qa-frames"
```

Use `--overwrite` only after confirming the previous QA artifacts are safe to replace. Frame extraction removes only managed QA artifacts matching `frame-*.png` and `contact-sheet.png`; it must not clean arbitrary files in the output folder.

5. Inspect `qa-frames/contact-sheet.png` visually when available.
6. Compare actual metadata to expected requirements.
7. Report findings with severity:
   - `P0`: black/white frames dominate, unreadable/corrupt video, duration near zero, or wrong deliverable.
   - `P1`: static-frame risk, wrong resolution/fps/duration for the requested output, or missing visual evidence.
   - `P2`: low bitrate, unusual codec, minor duration mismatch, or weak review evidence.
   - `P3`: optional polish.

## Report Contract

Return:

```text
Verdict: pass / needs fixes / not ready
Video:
Metadata:
Frame Evidence:
Findings:
Recommended Actions:
What Was Not Checked:
```

Always cite the exact video path, generated report path, and contact sheet path.

## Failure Branches

| Trigger | Action |
| --- | --- |
| Video path missing | Ask for or search the expected project render folder; do not infer success. |
| Output path is inside a skill/plugin directory, broad home folder, or unrelated project | Stop and ask for a project/temp QA folder. |
| Report or frame directory already exists | Stop by default; rerun with `--overwrite` only after confirming those QA artifacts can be replaced. |
| `ffmpeg`/`ffprobe` is missing | Mark technical QA incomplete; install only after explicit user approval. |
| `ffprobe` fails | Report P0 with the command error and do not continue to content claims. |
| Frame extraction fails | Report P1, keep metadata evidence, and say visual QA is incomplete. |
| All sampled frames are black or white | Report P0 unless the user explicitly requested a blank video. |
| Frames are visible but nearly identical | Report P1 static-frame risk and request intended animation/hold behavior. |
| HyperFrames `lint/validate/inspect` was not run | Mark as verification gap; do not call the video production-ready. |
| Video contains private/student/client content | Keep all evidence local and redact identifying details in the chat summary. |

## Do Not

- Do not say a video is complete just because `hyperframes render` exited 0.
- Do not rely on a media player's first frame as the only evidence.
- Do not ignore black frames in a blank template; distinguish expected blank tests from real deliverables.
- Do not delete or overwrite the source video.
- Do not overwrite prior QA reports or frame folders without explicit confirmation.
- Do not save QA outputs inside this skill package, plugin caches, or global config directories.
- Do not edit the video while running QA unless the user separately asks for repair.
- Do not upload videos, frames, or contact sheets to third-party tools without explicit approval for that exact artifact.
