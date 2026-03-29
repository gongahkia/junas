from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def detect_board_holds(image_path: Path) -> list[dict[str, object]]:
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Image not found at {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    contours, hierarchy = cv2.findContours(
        thresh, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )

    holds: list[dict[str, object]] = []
    if hierarchy is None:
        return holds

    for index, contour in enumerate(contours):
        if hierarchy[0][index][3] != -1:
            continue
        area = cv2.contourArea(contour)
        if area < 30:
            continue
        points = contour.reshape(-1, 2)
        xs = points[:, 0]
        ys = points[:, 1]
        holds.append(
            {
                "position": len(holds),
                "centroid_x": float(xs.mean()),
                "centroid_y": float(ys.mean()),
                "contour": points.tolist(),
            }
        )
    return holds


ROLE_COLORS = {
    "start": "#16A34A",
    "end": "#DC2626",
    "hand": "#2563EB",
    "foothold": "#E879F9",
}


def default_color_for_role(role: str) -> str:
    return ROLE_COLORS.get(role, "#64748B")
