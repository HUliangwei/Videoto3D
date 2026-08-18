"""Masked SIFT/ORB matching for synthetic Turntable experiments."""
from __future__ import annotations
from pathlib import Path
import numpy as np

def _load_gray_and_mask(frame_path, mask_path):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("R0.2 image matching needs OpenCV in the active core environment") from exc
    gray = cv2.imread(str(Path(frame_path)), cv2.IMREAD_GRAYSCALE)
    mask = cv2.imread(str(Path(mask_path)), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise FileNotFoundError("Could not read frame: {}".format(frame_path))
    if mask is None:
        raise FileNotFoundError("Could not read mask: {}".format(mask_path))
    if gray.shape != mask.shape:
        raise RuntimeError("Frame/mask shape mismatch: {}".format(frame_path))
    return gray, np.where(mask > 127, 255, 0).astype(np.uint8)

def match_masked_features(left_frame, right_frame, left_mask, right_mask,
                          max_features=6000, ratio_test=0.75):
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("R0.2 image matching needs OpenCV in the active core environment") from exc
    left_gray, left_binary = _load_gray_and_mask(left_frame, left_mask)
    right_gray, right_binary = _load_gray_and_mask(right_frame, right_mask)
    if hasattr(cv2, "SIFT_create"):
        detector = cv2.SIFT_create(nfeatures=int(max_features))
        norm = cv2.NORM_L2
        method = "SIFT"
    else:
        detector = cv2.ORB_create(nfeatures=int(max_features))
        norm = cv2.NORM_HAMMING
        method = "ORB"
    left_kp, left_desc = detector.detectAndCompute(left_gray, left_binary)
    right_kp, right_desc = detector.detectAndCompute(right_gray, right_binary)
    if left_desc is None or right_desc is None:
        raise RuntimeError("Feature extraction produced no descriptors")
    raw = cv2.BFMatcher(norm, crossCheck=False).knnMatch(left_desc, right_desc, k=2)
    provisional = []
    for pair in raw:
        if len(pair) == 2 and pair[0].distance < float(ratio_test) * pair[1].distance:
            provisional.append(pair[0])
    provisional.sort(key=lambda match: float(match.distance))
    used_left, used_right, selected = set(), set(), []
    for match in provisional:
        if match.queryIdx in used_left or match.trainIdx in used_right:
            continue
        used_left.add(match.queryIdx)
        used_right.add(match.trainIdx)
        selected.append(match)
    if len(selected) < 8:
        raise RuntimeError("Too few masked feature matches: {}".format(len(selected)))
    return {
        "method": method,
        "left_points_px": np.array([left_kp[m.queryIdx].pt for m in selected], dtype=np.float64),
        "right_points_px": np.array([right_kp[m.trainIdx].pt for m in selected], dtype=np.float64),
        "match_count": int(len(selected)),
    }
