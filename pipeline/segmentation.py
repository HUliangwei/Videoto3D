
import json
import os
import shutil
import subprocess
from pathlib import Path


def xywh_to_xyxy(box):
    x, y, width, height = box

    return (
        int(x),
        int(y),
        int(x + width),
        int(y + height),
    )


def copy_frames_for_masked_run(
    source_frames,
    target_frames,
):
    source_frames = Path(source_frames)
    target_frames = Path(target_frames)

    frames = sorted(
        source_frames.glob("frame_*.jpg")
    )

    if not frames:
        raise RuntimeError(
            "No extracted frames found in {}".format(
                source_frames
            )
        )

    target_frames.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove only generated frame copies, never user source data.
    for old_frame in target_frames.glob(
        "frame_*.jpg"
    ):
        old_frame.unlink()

    for frame in frames:
        shutil.copy2(
            frame,
            target_frames / frame.name,
        )

    return len(frames)


def build_segmentation_worker_command(
    runtime,
    worker_script,
    frames_dir,
    masks_dir,
    report_path,
    box=None,
):
    command = [
        str(Path(runtime["python"])),
        str(Path(worker_script)),
        "--frames",
        str(Path(frames_dir)),
        "--masks",
        str(Path(masks_dir)),
        "--checkpoint",
        str(Path(runtime["checkpoint"])),
        "--model-config",
        runtime["model_config"],
        "--report",
        str(Path(report_path)),
    ]

    if box is None:
        command.append(
            "--interactive-box"
        )
    else:
        command.extend(
            [
                "--box",
                str(int(box[0])),
                str(int(box[1])),
                str(int(box[2])),
                str(int(box[3])),
            ]
        )

    return command


def run_segmentation(
    runtime,
    worker_script,
    frames_dir,
    masks_dir,
    report_path,
    log_path,
    box=None,
):
    worker_script = Path(worker_script)
    frames_dir = Path(frames_dir)
    masks_dir = Path(masks_dir)
    report_path = Path(report_path)
    log_path = Path(log_path)

    if not worker_script.exists():
        raise FileNotFoundError(
            "SAM2 worker script not found: {}".format(
                worker_script
            )
        )

    masks_dir.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    for old_mask in masks_dir.glob("*.png"):
        old_mask.unlink()

    if report_path.exists():
        report_path.unlink()

    command = build_segmentation_worker_command(
        runtime=runtime,
        worker_script=worker_script,
        frames_dir=frames_dir,
        masks_dir=masks_dir,
        report_path=report_path,
        box=box,
    )

    env = os.environ.copy()
    repo = Path(runtime["sam2_repo"])
    previous = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo)
        if not previous
        else str(repo) + os.pathsep + previous
    )
    env["SAM2_BUILD_CUDA"] = "0"

    with log_path.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log:
        result = subprocess.run(
            command,
            cwd=str(repo),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if result.returncode != 0:
        log_text = log_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        if "out of memory" in log_text.lower():
            raise RuntimeError(
                "SAM2 ran out of GPU memory. "
                "Close GPU-heavy applications or switch to the Tiny checkpoint. "
                "See {}".format(log_path)
            )

        raise RuntimeError(
            "SAM2 mask worker failed with exit code {}. See {}".format(
                result.returncode,
                log_path,
            )
        )

    if not report_path.exists():
        raise RuntimeError(
            "SAM2 worker exited successfully but did not create report: {}"
            .format(report_path)
        )

    report = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    if report.get("status") != "ready":
        raise RuntimeError(
            "SAM2 report is not ready: {}".format(
                report
            )
        )

    if report.get("mask_count") != report.get("frame_count"):
        raise RuntimeError(
            "SAM2 mask count mismatch: {} masks for {} frames"
            .format(
                report.get("mask_count"),
                report.get("frame_count"),
            )
        )

    return report


def sample_qa_indices(frame_count):
    frame_count = int(frame_count)
    if frame_count <= 0:
        return []

    last = frame_count - 1
    indices = [
        round(last * fraction)
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]

    result = []
    for index in indices:
        if index not in result:
            result.append(index)
    return result


def _load_pillow_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Mask validation requires Pillow in the main Python environment. "
            "Install it with: python -m pip install pillow"
        ) from exc
    return Image


def validate_masks(frames_dir, masks_dir):
    frames_dir = Path(frames_dir)
    masks_dir = Path(masks_dir)

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    masks = sorted(masks_dir.glob("*.png"))

    if not frames:
        raise RuntimeError(
            "No source frames found in {}".format(frames_dir)
        )

    if len(masks) != len(frames):
        raise RuntimeError(
            "Mask count mismatch: {} masks for {} frames".format(
                len(masks),
                len(frames),
            )
        )

    Image = _load_pillow_image()
    expected_masks = []
    dimensions = None

    for frame in frames:
        mask_path = masks_dir / (frame.name + ".png")
        expected_masks.append(mask_path)

        if not mask_path.exists():
            raise RuntimeError(
                "Missing mask for {}: {}".format(
                    frame.name,
                    mask_path,
                )
            )

        with Image.open(frame) as frame_image:
            frame_size = frame_image.size

        with Image.open(mask_path) as mask_image:
            if mask_image.size != frame_size:
                raise RuntimeError(
                    "Mask dimension mismatch for {}: frame {} vs mask {}".format(
                        frame.name,
                        frame_size,
                        mask_image.size,
                    )
                )

            if mask_image.mode not in ("1", "L"):
                raise RuntimeError(
                    "Mask must be single-channel binary PNG: {} has mode {}".format(
                        mask_path,
                        mask_image.mode,
                    )
                )

            gray = mask_image.convert("L")
            colors = gray.getcolors(maxcolors=3)

            if colors is None:
                raise RuntimeError(
                    "Mask must be binary {{0,255}}: {} contains more than two values".format(
                        mask_path
                    )
                )

            values = {value for _, value in colors}
            if not values.issubset({0, 255}):
                raise RuntimeError(
                    "Mask must be binary {{0,255}}: {} contains {}".format(
                        mask_path,
                        sorted(values),
                    )
                )

            if 255 not in values:
                raise RuntimeError(
                    "Mask contains no foreground pixels: {}".format(mask_path)
                )

        if dimensions is None:
            dimensions = list(frame_size)

    expected_set = {path.resolve() for path in expected_masks}
    actual_set = {path.resolve() for path in masks}
    unexpected = actual_set - expected_set
    if unexpected:
        raise RuntimeError(
            "Unexpected mask filenames: {}".format(
                ", ".join(sorted(str(path) for path in unexpected))
            )
        )

    return {
        "status": "ready",
        "frame_count": len(frames),
        "mask_count": len(masks),
        "dimensions": dimensions,
        "qa_indices": sample_qa_indices(len(frames)),
    }


def build_mask_qa_viewer_command(
    runtime,
    viewer_script,
    frames_dir,
    masks_dir,
    output_path,
):
    return [
        str(Path(runtime["python"])),
        str(Path(viewer_script)),
        "--frames", str(Path(frames_dir)),
        "--masks", str(Path(masks_dir)),
        "--output", str(Path(output_path)),
    ]


def run_mask_qa_viewer(
    runtime,
    viewer_script,
    frames_dir,
    masks_dir,
    output_path,
    log_path,
    cwd=None,
):
    viewer_script = Path(viewer_script)
    output_path = Path(output_path)
    log_path = Path(log_path)

    if not viewer_script.exists():
        raise FileNotFoundError(
            "Mask QA viewer script not found: {}".format(viewer_script)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = build_mask_qa_viewer_command(
        runtime=runtime,
        viewer_script=viewer_script,
        frames_dir=frames_dir,
        masks_dir=masks_dir,
        output_path=output_path,
    )

    result = subprocess.run(
        command,
        cwd=str(cwd or viewer_script.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    log_path.write_text(
        result.stdout or "",
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Mask QA viewer failed with exit code {}. See {}".format(
                result.returncode,
                log_path,
            )
        )

    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(
            "Mask QA viewer did not create {}".format(output_path)
        )

    return {
        "output": str(output_path),
        "log": str(log_path),
    }



def prepare_openmvs_masks(frames_dir, masks_dir, output_dir):
    """Stage validated SAM2 masks using OpenMVS 2.4 naming.

    OpenMVS DensifyPointCloud expects each image mask to be named
    `<image stem>.mask.png`, e.g. `frame_0001.jpg` -> `frame_0001.mask.png`.
    """
    frames_dir = Path(frames_dir)
    masks_dir = Path(masks_dir)
    output_dir = Path(output_dir)

    validation = validate_masks(frames_dir, masks_dir)
    frames = sorted(frames_dir.glob("frame_*.jpg"))

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for frame in frames:
        source = masks_dir / (frame.name + ".png")
        target = output_dir / (frame.stem + ".mask.png")
        shutil.copy2(source, target)

    return {
        "status": "ready",
        "frame_count": validation["frame_count"],
        "mask_count": validation["mask_count"],
        "output_dir": str(output_dir),
    }
