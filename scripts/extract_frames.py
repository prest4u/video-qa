#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True

from safe_io import UnsafePathError, assert_existing_file, assert_safe_output_dir


def sample_timestamps(duration, count=5):
    if duration <= 0:
        return [0.0]
    if count <= 1:
        return [0.0]
    last = max(0.0, duration - min(0.5, duration * 0.2))
    step = last / (count - 1) if count > 1 else 0.0
    return [round(min(index * step, last), 2) for index in range(count)]


def _frame_name(index, timestamp):
    return f"frame-{index:03d}-{timestamp:.2f}s.png"


def _tile_shape(count):
    columns = math.ceil(math.sqrt(count))
    rows = math.ceil(count / columns)
    return columns, rows


def _contact_sheet_command(ffmpeg, frame_paths, output_path):
    if not frame_paths:
        raise ValueError("contact sheet requires at least one frame")

    tile_width = 480
    tile_height = 270
    command = [ffmpeg, "-y", "-v", "error"]
    for frame_path in frame_paths:
        command.extend(["-i", str(frame_path)])

    filters = []
    labels = []
    for index in range(len(frame_paths)):
        label = f"v{index}"
        filters.append(
            f"[{index}:v]"
            f"scale={tile_width}:{tile_height}:force_original_aspect_ratio=decrease,"
            f"pad={tile_width}:{tile_height}:(ow-iw)/2:(oh-ih)/2"
            f"[{label}]"
        )
        labels.append(f"[{label}]")

    if len(frame_paths) == 1:
        filter_complex = filters[0]
        map_label = labels[0]
    else:
        columns, _rows = _tile_shape(len(frame_paths))
        layout = "|".join(
            f"{(index % columns) * tile_width}_{(index // columns) * tile_height}"
            for index in range(len(frame_paths))
        )
        filter_complex = (
            ";".join(filters)
            + ";"
            + "".join(labels)
            + f"xstack=inputs={len(frame_paths)}:layout={layout}[out]"
        )
        map_label = "[out]"

    command.extend(["-filter_complex", filter_complex, "-map", map_label, str(output_path)])
    return command


def build_extract_commands(ffmpeg, video, out_dir, timestamps):
    output_dir = pathlib.Path(out_dir)
    frame_commands = []
    frame_paths = []
    for index, timestamp in enumerate(timestamps, start=1):
        output_path = output_dir / _frame_name(index, timestamp)
        frame_paths.append(output_path)
        frame_commands.append(
            [
                ffmpeg,
                "-y",
                "-v",
                "error",
                "-ss",
                f"{timestamp:.2f}",
                "-i",
                str(video),
                "-frames:v",
                "1",
                str(output_path),
            ]
        )

    contact_sheet = _contact_sheet_command(ffmpeg, frame_paths, output_dir / "contact-sheet.png")
    return {"frames": frame_commands, "contact_sheet": contact_sheet}


def run_ffprobe_duration(video_path, ffprobe="ffprobe"):
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    return float(payload.get("format", {}).get("duration", 0.0))


def _process_error_message(tool, exc):
    if isinstance(exc, FileNotFoundError):
        return f"{tool} not found: {exc.filename or tool}"
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stdout = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        detail = (stderr or stdout or str(exc)).strip()
        return f"{tool} failed with exit {exc.returncode}: {detail}"
    if isinstance(exc, json.JSONDecodeError):
        return f"{tool} returned invalid JSON: {exc}"
    return f"{tool} failed: {exc}"


def _print_failure(severity, message):
    print(f"{severity}: {message}", file=sys.stderr)


def run_commands(commands):
    for command in commands["frames"]:
        subprocess.run(command, check=True)
        output_path = pathlib.Path(command[-1])
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"frame extraction produced no image: {output_path}")
    subprocess.run(commands["contact_sheet"], check=True)
    output_path = pathlib.Path(commands["contact_sheet"][-1])
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"contact sheet was not created: {output_path}")


def clear_managed_outputs(out_dir):
    output_dir = pathlib.Path(out_dir)
    for frame_path in output_dir.glob("frame-*.png"):
        if frame_path.is_file() or frame_path.is_symlink():
            frame_path.unlink()
    contact_sheet = output_dir / "contact-sheet.png"
    if contact_sheet.is_file() or contact_sheet.is_symlink():
        contact_sheet.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract review frames from a video.")
    parser.add_argument("video", help="Path to an MP4 or other video file.")
    parser.add_argument("--out", required=True, help="Output directory for frames.")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing existing QA frame outputs.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.samples < 1 or args.samples > 24:
        parser.error("--samples must be between 1 and 24")

    try:
        video_path = assert_existing_file(args.video, label="video")
        out_dir = assert_safe_output_dir(args.out, overwrite=args.overwrite)
    except UnsafePathError as exc:
        parser.error(str(exc))

    try:
        duration = run_ffprobe_duration(video_path, ffprobe=args.ffprobe)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        _print_failure("P0", _process_error_message("ffprobe", exc))
        return 2

    timestamps = sample_timestamps(duration, count=args.samples)
    commands = build_extract_commands(args.ffmpeg, str(video_path), str(out_dir), timestamps)
    if args.dry_run:
        print(json.dumps(commands, indent=2))
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        clear_managed_outputs(out_dir)
    try:
        run_commands(commands)
    except (FileNotFoundError, subprocess.CalledProcessError, RuntimeError) as exc:
        _print_failure("P1", _process_error_message("ffmpeg", exc))
        return 3

    print(out_dir / "contact-sheet.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
