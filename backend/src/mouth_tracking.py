from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


# MediaPipe Face Mesh mouth and near-mouth landmark ids. The compositor uses
# these only to build a stable ROI; it does not assume full mesh availability.
MOUTH_LANDMARK_IDS = (
    0,
    13,
    14,
    17,
    37,
    39,
    40,
    61,
    78,
    80,
    81,
    82,
    84,
    87,
    88,
    91,
    95,
    146,
    178,
    181,
    185,
    191,
    267,
    269,
    270,
    291,
    308,
    310,
    311,
    312,
    314,
    317,
    318,
    321,
    324,
    375,
    402,
    405,
    409,
    415,
)


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


def mouth_rect_from_points(
    points: Iterable[tuple[float, float]],
    *,
    frame_width: int,
    frame_height: int,
    padding_x: float = 0.45,
    padding_y: float = 0.75,
    min_size: int = 16,
) -> Rect:
    pts = np.asarray(list(points), dtype=np.float32)
    if pts.size == 0:
        raise ValueError("mouth_rect_from_points requires at least one point")

    min_x = float(np.min(pts[:, 0]))
    max_x = float(np.max(pts[:, 0]))
    min_y = float(np.min(pts[:, 1]))
    max_y = float(np.max(pts[:, 1]))

    box_w = max(max_x - min_x, float(min_size))
    box_h = max(max_y - min_y, float(min_size))
    pad_x = int(box_w * padding_x)
    pad_y = int(box_h * padding_y)

    x0 = max(0, int(np.floor(min_x)) - pad_x)
    y0 = max(0, int(np.floor(min_y)) - pad_y)
    x1 = min(frame_width, int(np.ceil(max_x)) + pad_x)
    y1 = min(frame_height, int(np.ceil(max_y)) + pad_y)

    return Rect(x=x0, y=y0, width=max(0, x1 - x0), height=max(0, y1 - y0))


def mouth_rect_from_normalized_landmarks(
    landmarks: Sequence[object],
    *,
    frame_width: int,
    frame_height: int,
    landmark_ids: Sequence[int] = MOUTH_LANDMARK_IDS,
    padding_x: float = 0.45,
    padding_y: float = 0.75,
    min_size: int = 16,
) -> Rect:
    points: list[tuple[float, float]] = []
    for landmark_id in landmark_ids:
        if landmark_id >= len(landmarks):
            continue
        landmark = landmarks[landmark_id]
        points.append((float(landmark.x) * frame_width, float(landmark.y) * frame_height))

    return mouth_rect_from_points(
        points,
        frame_width=frame_width,
        frame_height=frame_height,
        padding_x=padding_x,
        padding_y=padding_y,
        min_size=min_size,
    )


def smooth_rect(previous: Rect | None, current: Rect, *, current_weight: float = 0.35) -> Rect:
    if previous is None:
        return current
    weight = min(1.0, max(0.0, current_weight))

    def blend(old: int, new: int) -> int:
        return int(round((old * (1.0 - weight)) + (new * weight)))

    return Rect(
        x=blend(previous.x, current.x),
        y=blend(previous.y, current.y),
        width=blend(previous.width, current.width),
        height=blend(previous.height, current.height),
    )


def ellipse_mask(width: int, height: int, *, feather: float = 1.5) -> np.ndarray:
    if width <= 0 or height <= 0:
        raise ValueError("ellipse_mask dimensions must be positive")
    yy, xx = np.mgrid[0:height, 0:width]
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    rx = max(width / 2.0, 1.0)
    ry = max(height / 2.0, 1.0)
    dist = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    mask = np.clip((1.0 - dist) * feather, 0.0, 1.0)
    return mask.astype(np.float32)


def color_match_patch(patch: np.ndarray, target: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if patch.shape != target.shape:
        raise ValueError("patch and target must have the same shape")
    if patch.ndim != 3 or patch.shape[2] != 3:
        raise ValueError("patch and target must be HxWx3 arrays")
    if mask.shape != patch.shape[:2]:
        raise ValueError("mask must match patch height and width")

    active = mask > 0.05
    if not np.any(active):
        return patch.copy()

    patch_float = patch.astype(np.float32)
    target_float = target.astype(np.float32)
    patch_pixels = patch_float[active]
    target_pixels = target_float[active]

    patch_mean = patch_pixels.mean(axis=0)
    target_mean = target_pixels.mean(axis=0)
    patch_std = patch_pixels.std(axis=0)
    target_std = target_pixels.std(axis=0)
    safe_patch_std = np.where(patch_std < 1e-6, 1.0, patch_std)

    matched = (patch_float - patch_mean) * (target_std / safe_patch_std) + target_mean
    return np.clip(matched, 0, 255).astype(np.float32)
