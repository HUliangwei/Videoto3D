
import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--frames",
        required=True,
    )
    parser.add_argument(
        "--masks",
        required=True,
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
    )
    parser.add_argument(
        "--model-config",
        required=True,
    )
    parser.add_argument(
        "--report",
        required=True,
    )

    prompt = parser.add_mutually_exclusive_group(
        required=True
    )
    prompt.add_argument(
        "--interactive-box",
        action="store_true",
    )
    prompt.add_argument(
        "--box",
        nargs=4,
        type=int,
        metavar=("X0", "Y0", "X1", "Y1"),
    )

    return parser.parse_args()


def frame_sort_key(path):
    match = re.search(
        r"(\d+)(?=\.[^.]+$)",
        path.name,
    )

    if not match:
        return (1, path.name)

    return (0, int(match.group(1)))


def list_frames(frames_dir):
    frames = [
        path
        for path in Path(frames_dir).iterdir()
        if path.suffix.lower() in (
            ".jpg",
            ".jpeg",
        )
    ]

    return sorted(
        frames,
        key=frame_sort_key,
    )


def stage_numeric_frames(
    frames,
    staging_dir,
):
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    mapping = []

    for index, source in enumerate(frames):
        destination = (
            staging_dir
            / "{:05d}.jpg".format(index)
        )

        try:
            os.link(
                str(source),
                str(destination),
            )
            mode = "hardlink"
        except OSError:
            shutil.copy2(
                source,
                destination,
            )
            mode = "copy"

        mapping.append(
            {
                "source": source,
                "staged": destination,
                "mode": mode,
            }
        )

    return mapping


def select_box(first_frame):
    import cv2

    image = cv2.imread(
        str(first_frame)
    )

    if image is None:
        raise RuntimeError(
            "Could not open first frame: {}".format(
                first_frame
            )
        )

    height, width = image.shape[:2]

    scale = min(
        1.0,
        900.0 / float(height),
        1400.0 / float(width),
    )

    display = image

    if scale < 1.0:
        display = cv2.resize(
            image,
            (
                int(width * scale),
                int(height * scale),
            ),
            interpolation=cv2.INTER_AREA,
        )

    window = (
        "Videoto3D - drag a box around the target, "
        "ENTER/SPACE confirm, C cancel"
    )

    x, y, w, h = cv2.selectROI(
        window,
        display,
        showCrosshair=True,
        fromCenter=False,
    )
    cv2.destroyAllWindows()

    if w <= 0 or h <= 0:
        raise RuntimeError(
            "Target selection cancelled."
        )

    inverse = 1.0 / scale

    x0 = int(round(x * inverse))
    y0 = int(round(y * inverse))
    x1 = int(round((x + w) * inverse))
    y1 = int(round((y + h) * inverse))

    return (
        max(0, x0),
        max(0, y0),
        min(width, x1),
        min(height, y1),
    )


def save_mask(path, mask):
    import numpy as np
    from PIL import Image

    data = (
        mask.astype(np.uint8)
        * 255
    )

    Image.fromarray(
        data,
        mode="L",
    ).save(path)


def main():
    args = parse_args()

    frames_dir = Path(args.frames)
    masks_dir = Path(args.masks)
    report_path = Path(args.report)
    checkpoint = Path(args.checkpoint)

    frames = list_frames(
        frames_dir
    )

    if not frames:
        raise RuntimeError(
            "No JPEG frames found in {}".format(
                frames_dir
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

    box = (
        tuple(args.box)
        if args.box is not None
        else select_box(frames[0])
    )

    import numpy as np
    import torch
    from sam2.build_sam import (
        build_sam2_video_predictor,
    )

    print(
        "Videoto3D SAM2 worker"
    )
    print(
        "Frames     :",
        len(frames),
    )
    print(
        "Checkpoint :",
        checkpoint,
    )
    print(
        "Config     :",
        args.model_config,
    )
    print(
        "Box XYXY   :",
        box,
    )
    print(
        "GPU        :",
        torch.cuda.get_device_name(0),
    )

    with tempfile.TemporaryDirectory(
        prefix="videoto3d_sam2_",
        dir=str(report_path.parent),
    ) as temp_dir:
        mapping = stage_numeric_frames(
            frames,
            Path(temp_dir),
        )

        predictor = build_sam2_video_predictor(
            config_file=args.model_config,
            ckpt_path=str(checkpoint),
            device="cuda",
            apply_postprocessing=False,
        )

        with torch.inference_mode(), torch.autocast(
            device_type="cuda",
            dtype=torch.bfloat16,
        ):
            state = predictor.init_state(
                video_path=str(temp_dir),
                offload_video_to_cpu=True,
                offload_state_to_cpu=True,
                async_loading_frames=False,
            )

            predictor.add_new_points_or_box(
                inference_state=state,
                frame_idx=0,
                obj_id=1,
                box=np.asarray(
                    box,
                    dtype=np.float32,
                ),
            )

            mask_count = 0

            for (
                frame_idx,
                object_ids,
                mask_logits,
            ) in predictor.propagate_in_video(
                state
            ):
                mask = (
                    mask_logits[0]
                    > 0.0
                ).squeeze().cpu().numpy()

                source_name = (
                    mapping[frame_idx]["source"].name
                )

                output_path = (
                    masks_dir
                    / "{}.png".format(
                        source_name
                    )
                )

                save_mask(
                    output_path,
                    mask,
                )

                mask_count += 1

    report = {
        "status": "ready",
        "frame_count": len(frames),
        "mask_count": mask_count,
        "object_id": 1,
        "box_xyxy": list(box),
        "model": checkpoint.name,
        "model_config": args.model_config,
        "device": "cuda",
        "gpu": torch.cuda.get_device_name(0),
    }

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "Masks      :",
        mask_count,
    )
    print(
        "Report     :",
        report_path,
    )


if __name__ == "__main__":
    main()
