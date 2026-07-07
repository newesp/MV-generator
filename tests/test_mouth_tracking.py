import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.mouth_tracking import (  # noqa: E402
    Rect,
    color_match_patch,
    ellipse_mask,
    mouth_rect_from_points,
    smooth_rect,
)


class MouthTrackingGeometryTests(unittest.TestCase):
    def test_mouth_rect_from_points_pads_and_clamps_to_frame(self):
        points = [(95, 45), (118, 48), (110, 60), (102, 58)]

        rect = mouth_rect_from_points(
            points,
            frame_width=120,
            frame_height=70,
            padding_x=0.5,
            padding_y=1.0,
            min_size=12,
        )

        self.assertEqual(rect, Rect(x=84, y=30, width=36, height=40))

    def test_smooth_rect_blends_current_toward_previous(self):
        previous = Rect(x=100, y=80, width=60, height=30)
        current = Rect(x=140, y=120, width=80, height=50)

        rect = smooth_rect(previous, current, current_weight=0.25)

        self.assertEqual(rect, Rect(x=110, y=90, width=65, height=35))

    def test_ellipse_mask_is_opaque_in_center_and_soft_at_edges(self):
        mask = ellipse_mask(width=9, height=7, feather=1.5)

        self.assertEqual(mask.shape, (7, 9))
        self.assertGreater(mask[3, 4], 0.95)
        self.assertLess(mask[0, 0], 0.05)
        self.assertGreater(mask[3, 1], mask[0, 0])

    def test_color_match_patch_matches_masked_target_statistics(self):
        patch = np.full((4, 4, 3), 40, dtype=np.float32)
        target = np.full((4, 4, 3), 120, dtype=np.float32)
        patch[:, :, 1] = 70
        target[:, :, 1] = 170
        mask = np.zeros((4, 4), dtype=np.float32)
        mask[1:3, 1:3] = 1.0

        matched = color_match_patch(patch, target, mask)

        self.assertTrue(np.allclose(matched[1:3, 1:3, 0], 120, atol=1))
        self.assertTrue(np.allclose(matched[1:3, 1:3, 1], 170, atol=1))


if __name__ == "__main__":
    unittest.main()
