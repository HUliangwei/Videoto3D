import shutil
import subprocess
from pathlib import Path


def build_ffmpeg_extract_command(
    ffmpeg_path,
    input_video,
    output_pattern,
    fps=4,
):
    return [
        str(Path(ffmpeg_path)),
        "-hide_banner",
        "-y",
        "-i",
        str(Path(input_video)),
        "-vf",
        "fps={}".format(fps),
        "-q:v",
        "2",
        str(Path(output_pattern)),
    ]


def extract_frames(
    ffmpeg_path,
    input_video,
    output_dir,
    logs_dir,
    fps=4,
    overwrite=True,
):
    ffmpeg_path = Path(ffmpeg_path)
    input_video = Path(input_video)
    output_dir = Path(output_dir)
    logs_dir = Path(logs_dir)

    if not ffmpeg_path.exists():
        raise FileNotFoundError(
            "FFmpeg not found: {}".format(ffmpeg_path)
        )

    if not input_video.exists():
        raise FileNotFoundError(
            "Input video not found: {}".format(input_video)
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    logs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if overwrite:
        for frame in output_dir.glob("frame_*.jpg"):
            frame.unlink()

    output_pattern = (
        output_dir / "frame_%04d.jpg"
    )

    command = build_ffmpeg_extract_command(
        ffmpeg_path=ffmpeg_path,
        input_video=input_video,
        output_pattern=output_pattern,
        fps=fps,
    )

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    log_path = logs_dir / "ffmpeg_extract.log"
    log_path.write_text(
        result.stdout or "",
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg extraction failed with exit code {}. "
            "See {}".format(
                result.returncode,
                log_path,
            )
        )

    frames = sorted(
        output_dir.glob("frame_*.jpg")
    )

    if not frames:
        raise RuntimeError(
            "FFmpeg completed but no frames were generated. "
            "See {}".format(log_path)
        )

    return {
        "input": str(input_video),
        "fps": fps,
        "frame_count": len(frames),
        "output_dir": str(output_dir),
        "log": str(log_path),
    }
