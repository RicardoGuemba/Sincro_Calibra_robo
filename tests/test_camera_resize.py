from __future__ import annotations

import numpy as np

from sincro_robo.adapters.camera import SAFETY_MAX_DIMENSION, resize_output


def test_output_longer_side_matches_the_v2108_ceiling() -> None:
    frame = np.zeros((2048, 2448, 3), dtype=np.uint8)
    resized = resize_output(frame, 960)
    assert resized.shape == (803, 960, 3)


def test_frame_inside_the_ceiling_is_unchanged() -> None:
    frame = np.zeros((720, 960, 3), dtype=np.uint8)
    assert resize_output(frame, 960) is frame


def test_zero_limit_uses_the_safety_ceiling() -> None:
    frame = np.zeros((2000, 3000, 3), dtype=np.uint8)
    resized = resize_output(frame, 0)
    assert max(resized.shape[:2]) == SAFETY_MAX_DIMENSION
