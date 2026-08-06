# video-qa

> Inspect rendered videos for technical delivery and visual-content risks.

## Welcome

`video-qa` is a standalone Codex Skill by Eric (`prest4u`). This repository contains everything
needed to inspect, install, adapt, test, and contribute to the Skill without cloning a larger collection.

## What it does

- Probe metadata and sample frames reproducibly
- Create contact sheets and detect black, blank, static, or suspicious renders
- Keep QA outputs separate from the source and report exact delivery risks

**Use it when:** A rendered MP4/WebM needs verification, troubleshooting, or pre-delivery QA.

**Do not use it when:** You need to edit, transcode, repair, upload, or replace the source video rather than inspect it.

## Install

Clone this repository into your Codex Skills directory:

```bash
git clone https://github.com/prest4u/video-qa.git ~/.codex/skills/video-qa
```

Restart Codex after installation. Keep the install directory named `video-qa` so links and examples
remain predictable.

### Runtime requirements

Core metadata and frame QA require Python 3 plus both `ffmpeg` and `ffprobe` on `PATH`. Verify them before use:

```bash
python3 --version
ffmpeg -version
ffprobe -version
```

On macOS with Homebrew, `brew install ffmpeg` supplies both media commands. On other platforms, install FFmpeg from your
package manager or the [official download page](https://ffmpeg.org/download.html). Installing system software is a separate
permission: if the commands are missing, report technical QA as incomplete and obtain approval before installing anything.

## Example prompts

- `Use $video-qa to inspect this MP4 for black frames, static output, duration, FPS, and dimensions.`
- `Generate a bounded contact sheet and a technical QA report for this final render.`

## How it works

Read [`SKILL.md`](SKILL.md) for the authoritative trigger boundary, workflow, stop conditions, and completion
contract. The Skill loads only the references required by the active task and uses bundled scripts or templates
where they provide reproducible behavior.

## Repository guide

- `SKILL.md` — authoritative agent instructions.
- `agents/openai.yaml` — discoverability metadata when present.
- `references/` — focused operating guidance loaded only when relevant.
- `scripts/` — validators, builders, or deterministic helpers when present.
- `tests/` and `test-prompts.json` — contract and regression coverage when present.
- `assets/` and `templates/` — reusable source assets when present; generated deliverables are excluded.

## Validation

Before changing the Skill, run the package's existing tests and validators. At minimum, validate `SKILL.md`
structure and confirm every local reference exists. A passing script does not replace visual, runtime, source,
or independent-review evidence when the Skill explicitly requires those gates.

## Safety and privacy

Do not commit credentials, account state, private task transcripts, personal records, student/customer data,
local absolute paths, caches, or generated deliverables. Invocation guides workflow; it does not grant authority
to publish, deploy, spend money, overwrite files, access accounts, or perform destructive actions.

## Contributing

Issues and pull requests are welcome. Describe observable behavior, use synthetic fixtures, preserve public
triggers unless a breaking change is intentional, and include the smallest check that proves the change.

## License

MIT — see [`LICENSE`](LICENSE).
