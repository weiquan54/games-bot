"""OpenCV template matching with resolution compensation."""

import cv2
import numpy as np


def match_template(
    screenshot: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.8,
    scale_factor: float = 1.0,
) -> tuple:
    """Find template in screenshot. Returns (x_center, y_center) or None."""
    if scale_factor != 1.0:
        h, w = template.shape[:2]
        new_w = max(1, int(round(w * scale_factor)))
        new_h = max(1, int(round(h * scale_factor)))
        template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        return None

    th, tw = template.shape[:2]
    cx = max_loc[0] + tw // 2
    cy = max_loc[1] + th // 2
    return (cx, cy)
