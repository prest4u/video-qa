---
name: video-qa
description: 'Inspect rendered video files for encoding, visual, timing, caption and audio defects, with checks scoped to the requested output.'
---

# Video QA

Inspect the actual rendered file. QA is read-only unless repairs are requested; do not transcode, publish, upload, overwrite or regenerate the source by default. Put reports and extracted frames in the project or a task-specific temporary folder, with a fresh destination when necessary.

Choose coverage from the change and consequence. For a known draft, inspect metadata, the changed interval and its joins, plus the affected captions/audio. For an unknown or formal final file, check complete decoding and all important scenes, beginning/end, title/caption safe areas, cuts and audio coverage. A duration or container match does not establish content completeness.

```bash
python3 scripts/video_probe.py <video> --json --report <report.md>
python3 scripts/extract_frames.py <video> --out <frames-dir>
```

Read each helper's `--help` for sampling controls. Reuse trustworthy unchanged inspection results. Review probe failures and seek enough frames around a visible defect to identify its interval. An identical-frame run may be an intentional hold; distinguish it from a frozen render by the actual scene.

Inspect full-size frames for clipped text, incorrect spelling, missing media, unreadable contrast, subtitle timing, aspect ratio and consistent content. Compare with the brief or approved script. Watch motion at normal playback where possible; isolated frames do not prove smooth motion. Listen for clipping, missing speech, abrupt joins, timing and voice consistency. If direct audition is unavailable, report it; signal metrics and transcripts do not prove natural delivery.

Use the matching sections of the local QA references for a formal audit or a specific failure. Remotion references apply only to Remotion. Report defects with file, timestamp/interval, observed effect and a concrete repair suggestion. Separate blocking content/encoding failures from presentation improvements. Verify a repaired file after its affected inputs change. Do not invent a quality score or visual/auditory PASS from probes alone.

For Remotion export/render failures, read the matching [render rule](references/upstream/remotion-render/SKILL.md). For composition, animation or asset behavior, read only the matching [Remotion practice](references/upstream/remotion-best-practices/SKILL.md).
