from __future__ import annotations

import numpy as np
import pytest

from sincro_robo.projection import camera_to_robot


def test_camera_pixel_becomes_robot_xy_through_lens_pose_and_affine() -> None:
    matrix = [[100.0, 0.0, 50.0], [0.0, 100.0, 40.0], [0.0, 0.0, 1.0]]
    pose = {"R": np.eye(3).tolist(), "t": [0.0, 0.0, 0.0]}
    affine = [[0.0, 0.0], [0.0, 0.0], [12.5, -4.0]]
    projected = camera_to_robot(
        50.0,
        40.0,
        camera_matrix=matrix,
        dist_coeffs=[0.0, 0.0, 0.0, 0.0, 0.0],
        rectified_camera_matrix=matrix,
        robot_from_camera=pose,
        plane_z_mm=100.0,
        affine=affine,
    )
    assert projected["u_rectified_px"] == pytest.approx(50.0, abs=1e-4)
    assert projected["v_rectified_px"] == pytest.approx(40.0, abs=1e-4)
    assert projected["optical_x_mm"] == pytest.approx(0.0, abs=1e-4)
    assert projected["optical_y_mm"] == pytest.approx(0.0, abs=1e-4)
    assert projected["optical_z_mm"] == pytest.approx(100.0, abs=1e-4)
    assert projected["x_robo"] == pytest.approx(12.5)
    assert projected["y_robo"] == pytest.approx(-4.0)
    assert projected["relation"]["x_robo"] == "0*u + 0*v + 12.5"
    assert projected["relation"]["y_robo"] == "0*u + 0*v + -4"
