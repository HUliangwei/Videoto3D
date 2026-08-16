import argparse
from pathlib import Path

import cv2
import numpy as np


def sample_indices(count):
    if count <= 0:
        return []
    last = count - 1
    result = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        index = round(last * fraction)
        if index not in result:
            result.append(index)
    return result


def fit_thumbnail(image, max_height=620, max_width=330):
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale < 1.0:
        image = cv2.resize(
            image,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    return image


def make_overlay(frame, mask, label):
    foreground = mask > 0
    overlay = frame.copy()
    tint = np.zeros_like(frame)
    tint[:, :, 1] = 255
    overlay[foreground] = cv2.addWeighted(
        frame[foreground],
        0.55,
        tint[foreground],
        0.45,
        0.0,
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    cv2.drawContours(overlay, contours, -1, (0, 255, 255), 2)
    cv2.putText(
        overlay,
        label,
        (12, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return fit_thumbnail(overlay)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", required=True)
    parser.add_argument("--masks", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    frames_dir = Path(args.frames)
    masks_dir = Path(args.masks)
    output_path = Path(args.output)

    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("No frames found in {}".format(frames_dir))

    selected = sample_indices(len(frames))
    panels = []

    for index in selected:
        frame_path = frames[index]
        mask_path = masks_dir / (frame_path.name + ".png")
        frame = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if frame is None:
            raise RuntimeError("Could not read frame: {}".format(frame_path))
        if mask is None:
            raise RuntimeError("Could not read mask: {}".format(mask_path))
        if frame.shape[:2] != mask.shape[:2]:
            raise RuntimeError("Frame/mask dimension mismatch: {}".format(frame_path.name))

        label = "{}  ({}/{})".format(frame_path.name, index + 1, len(frames))
        panels.append(make_overlay(frame, mask, label))

    target_height = max(panel.shape[0] for panel in panels)
    normalized = []
    for panel in panels:
        if panel.shape[0] < target_height:
            pad = target_height - panel.shape[0]
            panel = cv2.copyMakeBorder(
                panel,
                0,
                pad,
                0,
                0,
                cv2.BORDER_CONSTANT,
                value=(0, 0, 0),
            )
        normalized.append(panel)

    montage = np.hstack(normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), montage):
        raise RuntimeError("Could not write QA image: {}".format(output_path))

    print("QA frames:", ", ".join(str(i + 1) for i in selected))
    print("Saved:", output_path)
    print("Press any key in the QA window to close.")

    cv2.imshow("Videoto3D Mask QA - green = retained object", montage)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
