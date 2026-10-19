from __future__ import annotations

from typing import Any

import numpy as np

from .calibration import CalibrationModel
from .optics import robot_point_on_plane, undistort_points


def affine_relation(affine: list[list[float]]) -> dict[str, Any]:
    """X_robo e Y_robo como função linear do pixel já corrigido pela lente."""
    matrix = np.asarray(affine, dtype=np.float64)
    if matrix.shape != (3, 2):
        raise ValueError("A afim da campanha não está no formato 3×2")
    x_coefficients = [float(matrix[0, 0]), float(matrix[1, 0]), float(matrix[2, 0])]
    y_coefficients = [float(matrix[0, 1]), float(matrix[1, 1]), float(matrix[2, 1])]
    return {
        "u_v": "u, v = undistort(X_camera, Y_camera) com K, D e K retificada",
        "x_coefficients": x_coefficients,
        "y_coefficients": y_coefficients,
        "x_robo": _linear_formula("u", "v", x_coefficients),
        "y_robo": _linear_formula("u", "v", y_coefficients),
    }


def camera_to_robot(
    x_camera: float,
    y_camera: float,
    *,
    camera_matrix: list[list[float]],
    dist_coeffs: list[float],
    rectified_camera_matrix: list[list[float]],
    robot_from_camera: dict[str, Any],
    plane_z_mm: float,
    affine: list[list[float]],
) -> dict[str, Any]:
    """Cadeia da campanha: lente, pose da câmera no plano Z e afim do molde.

    X_robo e Y_robo são o centro geométrico previsto pela afim no pixel retificado.
    A extrínseca devolve o mesmo pixel projetado no plano, sem substituir a afim.
    """
    rectified = undistort_points(
        np.asarray([[float(x_camera), float(y_camera)]], dtype=np.float64),
        np.asarray(camera_matrix, dtype=np.float64),
        np.asarray(dist_coeffs, dtype=np.float64),
        np.asarray(rectified_camera_matrix, dtype=np.float64),
    )[0]
    u_rectified = float(rectified[0])
    v_rectified = float(rectified[1])
    optical_x, optical_y, optical_z = robot_point_on_plane(
        float(x_camera),
        float(y_camera),
        camera_matrix,
        dist_coeffs,
        robot_from_camera,
        float(plane_z_mm),
    )
    relation = affine_relation(affine)
    model = CalibrationModel(
        plan_z=float(plane_z_mm),
        affine=affine,
        angle_offset_deg=0.0,
        adjustment_count=0,
    )
    x_robo, y_robo = model.transform_xy(u_rectified, v_rectified)
    return {
        "x_camera": float(x_camera),
        "y_camera": float(y_camera),
        "u_rectified_px": u_rectified,
        "v_rectified_px": v_rectified,
        "plane_z_mm": float(plane_z_mm),
        "optical_x_mm": optical_x,
        "optical_y_mm": optical_y,
        "optical_z_mm": optical_z,
        "x_robo": x_robo,
        "y_robo": y_robo,
        "relation": relation,
    }


def _linear_formula(u_name: str, v_name: str, coefficients: list[float]) -> str:
    u_term, v_term, offset = (_format_coefficient(value) for value in coefficients)
    return f"{u_term}*{u_name} + {v_term}*{v_name} + {offset}"


def _format_coefficient(value: float) -> str:
    return f"{float(value):.8f}".rstrip("0").rstrip(".")
