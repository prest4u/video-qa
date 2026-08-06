#!/usr/bin/env python3
import argparse
import json
import math
import pathlib
import statistics
import subprocess
import sys

sys.dont_write_bytecode = True

from safe_io import UnsafePathError, assert_existing_file, assert_safe_output_path, ensure_parent


BLACK_MEAN_THRESHOLD = 5.0
BLACK_STDEV_THRESHOLD = 3.0
WHITE_MEAN_THRESHOLD = 250.0
WHITE_STDEV_THRESHOLD = 5.0
STATIC_MEAN_RANGE_THRESHOLD = 2.0
STATIC_STDEV_RANGE_THRESHOLD = 2.0


def _parse_fraction(value):
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        denominator_value = float(denominator)
        if denominator_value == 0:
            return 0.0
        return float(numerator) / denominator_value
    return float(value)


def _number_or_none(value, cast=float):
    if value in (None, "N/A", ""):
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


def parse_ffprobe_json(payload):
    video_stream = None
    for stream in payload.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break
    if video_stream is None:
        raise ValueError("No video stream found in ffprobe output.")

    fmt = payload.get("format", {})
    duration = _number_or_none(video_stream.get("duration")) or _number_or_none(fmt.get("duration")) or 0.0
    fps = _parse_fraction(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    frame_count = _number_or_none(video_stream.get("nb_frames"), int)
    if frame_count is None and duration and fps:
        frame_count = int(round(duration * fps))

    return {
        "duration": float(duration),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": fps,
        "frame_count": frame_count or 0,
        "video_bitrate": _number_or_none(video_stream.get("bit_rate"), int) or _number_or_none(fmt.get("bit_rate"), int),
        "codec": video_stream.get("codec_name", "unknown"),
        "size": _number_or_none(fmt.get("size"), int),
    }


def sample_timestamps(duration, count=5):
    if duration <= 0:
        return [0.0]
    if count <= 1:
        return [0.0]
    last = max(0.0, duration - min(0.5, duration * 0.2))
    step = last / (count - 1) if count > 1 else 0.0
    values = []
    for index in range(count):
        value = min(index * step, last)
        values.append(round(value, 2))
    return values


def classify_video(metadata, frame_stats):
    total = max(len(frame_stats), 1)
    black_count = sum(
        1
        for stat in frame_stats
        if stat.get("mean", 0.0) <= BLACK_MEAN_THRESHOLD
        and stat.get("stdev", 0.0) <= BLACK_STDEV_THRESHOLD
    )
    white_count = sum(
        1
        for stat in frame_stats
        if stat.get("mean", 0.0) >= WHITE_MEAN_THRESHOLD
        and stat.get("stdev", 0.0) <= WHITE_STDEV_THRESHOLD
    )
    black_ratio = black_count / total
    white_ratio = white_count / total

    means = [float(stat.get("mean", 0.0)) for stat in frame_stats]
    stdevs = [float(stat.get("stdev", 0.0)) for stat in frame_stats]
    mean_range = (max(means) - min(means)) if means else 0.0
    stdev_range = (max(stdevs) - min(stdevs)) if stdevs else 0.0

    black_frame_risk = black_ratio >= 0.8
    white_frame_risk = white_ratio >= 0.8
    static_frame_risk = (
        len(frame_stats) >= 3
        and not black_frame_risk
        and not white_frame_risk
        and mean_range <= STATIC_MEAN_RANGE_THRESHOLD
        and stdev_range <= STATIC_STDEV_RANGE_THRESHOLD
    )

    if black_frame_risk or white_frame_risk:
        severity = "P0"
    elif static_frame_risk:
        severity = "P1"
    else:
        severity = "pass"

    return {
        "metadata": metadata,
        "frame_stats": frame_stats,
        "black_frame_ratio": round(black_ratio, 3),
        "white_frame_ratio": round(white_ratio, 3),
        "mean_range": round(mean_range, 3),
        "stdev_range": round(stdev_range, 3),
        "severity": severity,
        "risks": {
            "black_frame_risk": black_frame_risk,
            "white_frame_risk": white_frame_risk,
            "static_frame_risk": static_frame_risk,
        },
    }


def run_ffprobe(video_path, ffprobe="ffprobe"):
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate",
        "-show_streams",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


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


def _frame_bytes_to_stats(raw_bytes):
    if not raw_bytes:
        return {"mean": 0.0, "stdev": 0.0}
    values = list(raw_bytes)
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {"mean": round(mean, 3), "stdev": round(stdev, 3)}


def sample_frame_stats(video_path, metadata, ffmpeg="ffmpeg", count=5):
    width = metadata["width"]
    height = metadata["height"]
    if width <= 0 or height <= 0:
        raise ValueError("Video width and height must be positive for frame sampling.")
    expected_bytes = width * height * 3
    stats = []
    for timestamp in sample_timestamps(metadata["duration"], count=count):
        command = [
            ffmpeg,
            "-v",
            "error",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
        completed = subprocess.run(command, check=True, capture_output=True)
        raw = completed.stdout[:expected_bytes]
        if len(raw) < expected_bytes:
            raise RuntimeError(
                f"ffmpeg produced an incomplete sample at {timestamp:.2f}s "
                f"({len(raw)} of {expected_bytes} bytes)"
            )
        stat = _frame_bytes_to_stats(raw)
        stat["timestamp"] = timestamp
        stats.append(stat)
    return stats


def write_markdown_report(result, output_path):
    risks = result["risks"]
    metadata = result["metadata"]
    lines = [
        "# Video QA Report",
        "",
        f"Severity: {result['severity']}",
        "",
        "## Metadata",
        "",
        f"- Duration: {metadata['duration']}s",
        f"- Resolution: {metadata['width']}x{metadata['height']}",
        f"- FPS: {metadata['fps']:.3f}",
        f"- Frames: {metadata['frame_count']}",
        f"- Codec: {metadata['codec']}",
        "",
        "## Risks",
        "",
        f"- Black frame risk: {risks['black_frame_risk']} ({result['black_frame_ratio']})",
        f"- White frame risk: {risks['white_frame_risk']} ({result['white_frame_ratio']})",
        f"- Static frame risk: {risks['static_frame_risk']}",
        "",
        "## Sample Frames",
        "",
    ]
    for stat in result["frame_stats"]:
        lines.append(
            f"- t={stat['timestamp']:.2f}s mean={stat['mean']} stdev={stat['stdev']}"
        )
    ensure_parent(output_path)
    pathlib.Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def failure_result(severity, error, message, metadata=None):
    return {
        "severity": severity,
        "error": error,
        "message": message,
        "metadata": metadata or {},
        "frame_stats": [],
        "risks": {
            "black_frame_risk": False,
            "white_frame_risk": False,
            "static_frame_risk": False,
        },
    }


def write_failure_report(result, output_path):
    lines = [
        "# Video QA Report",
        "",
        f"Severity: {result['severity']}",
        "",
        "## Failure",
        "",
        f"- Error: {result['error']}",
        f"- Message: {result['message']}",
        "",
        "## What Was Not Checked",
        "",
        "- Full visual QA was not completed because the probe failed.",
    ]
    metadata = result.get("metadata") or {}
    if metadata:
        lines[5:5] = [
            "## Metadata",
            "",
            f"- Duration: {metadata.get('duration', 'unknown')}s",
            f"- Resolution: {metadata.get('width', 'unknown')}x{metadata.get('height', 'unknown')}",
            f"- FPS: {metadata.get('fps', 'unknown')}",
            "",
        ]
    ensure_parent(output_path)
    pathlib.Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_failure(result, *, json_enabled, report_path=None):
    if report_path:
        write_failure_report(result, report_path)
    if json_enabled:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"{result['severity']}: {result['message']}", file=sys.stderr)


def exit_code_for_severity(severity):
    if severity == "P0":
        return 2
    if severity == "P1":
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Probe a rendered video for delivery risks.")
    parser.add_argument("video", help="Path to an MP4 or other video file.")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    parser.add_argument("--report", help="Write a Markdown report.")
    parser.add_argument("--overwrite", action="store_true", help="Allow replacing an existing Markdown report.")
    args = parser.parse_args(argv)

    if args.samples < 1 or args.samples > 24:
        parser.error("--samples must be between 1 and 24")

    try:
        video_path = assert_existing_file(args.video, label="video")
        report_path = None
        if args.report:
            report_path = assert_safe_output_path(
                args.report,
                overwrite=args.overwrite,
                allowed_suffixes={".md"},
                source_paths=[video_path],
            )
    except UnsafePathError as exc:
        parser.error(str(exc))

    try:
        payload = run_ffprobe(video_path, ffprobe=args.ffprobe)
        metadata = parse_ffprobe_json(payload)
    except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        result = failure_result("P0", "ffprobe_failed", _process_error_message("ffprobe", exc))
        emit_failure(result, json_enabled=args.json or not args.report, report_path=report_path)
        return 2

    try:
        frame_stats = sample_frame_stats(video_path, metadata, ffmpeg=args.ffmpeg, count=args.samples)
    except (FileNotFoundError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        result = failure_result("P1", "frame_sampling_failed", _process_error_message("ffmpeg", exc), metadata=metadata)
        emit_failure(result, json_enabled=args.json or not args.report, report_path=report_path)
        return 3

    result = classify_video(metadata, frame_stats)

    if report_path:
        write_markdown_report(result, report_path)
    if args.json or not args.report:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code_for_severity(result["severity"])


if __name__ == "__main__":
    raise SystemExit(main())
