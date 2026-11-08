"""
Ergonomic Vector Math & Landmark Analysis.
Vectorized, zero-copy calculations for neck inclination, screen proximity, and shoulder asymmetry.
"""

import math
from typing import Dict, Optional, Tuple

from src.config import (
    LEFT_EAR,
    LEFT_SHOULDER,
    NOSE,
    RIGHT_EAR,
    RIGHT_SHOULDER,
)


class ErgonomicCalculator:
    """
    Computes biomechanical metrics from MediaPipe pose landmarks.
    """

    def __init__(self, min_visibility: float = 0.5):
        self.min_visibility = min_visibility

    def extract_keypoints(self, landmarks, frame_w: int, frame_h: int) -> Dict[str, Dict]:
        """
        Extracts pixel and normalized coordinates for key ergonomic landmarks:
        Nose, Left/Right Ears, Left/Right Shoulders.
        """
        keys = {
            "nose": landmarks[NOSE],
            "left_ear": landmarks[LEFT_EAR],
            "right_ear": landmarks[RIGHT_EAR],
            "left_shoulder": landmarks[LEFT_SHOULDER],
            "right_shoulder": landmarks[RIGHT_SHOULDER],
        }

        extracted = {}
        for name, lm in keys.items():
            vis = getattr(lm, "visibility", 1.0)
            if vis is None:
                vis = 1.0
            extracted[name] = {
                "x_norm": lm.x,
                "y_norm": lm.y,
                "z_norm": getattr(lm, "z", 0.0),
                "x_px": int(lm.x * frame_w),
                "y_px": int(lm.y * frame_h),
                "visibility": float(vis),
            }
        return extracted

    def calculate_neck_inclination(
        self, keypoints: Dict
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """
        Calculates neck inclination angle (degrees deviation from vertical).
        Uses ear-shoulder vectors. When upright, angle is low (0° - 15°).
        Slouching / forward head causes angle to increase (> 30°).
        
        Returns:
            (angle_degrees, ear_midpoint_px, shoulder_midpoint_px)
        """
        l_ear = keypoints["left_ear"]
        r_ear = keypoints["right_ear"]
        l_sh = keypoints["left_shoulder"]
        r_sh = keypoints["right_shoulder"]

        # Determine reliable ear position (average if both visible, or fallback to visible side)
        valid_ears = []
        if l_ear["visibility"] >= self.min_visibility:
            valid_ears.append((l_ear["x_norm"], l_ear["y_norm"], l_ear["x_px"], l_ear["y_px"]))
        if r_ear["visibility"] >= self.min_visibility:
            valid_ears.append((r_ear["x_norm"], r_ear["y_norm"], r_ear["x_px"], r_ear["y_px"]))

        valid_shoulders = []
        if l_sh["visibility"] >= self.min_visibility:
            valid_shoulders.append((l_sh["x_norm"], l_sh["y_norm"], l_sh["x_px"], l_sh["y_px"]))
        if r_sh["visibility"] >= self.min_visibility:
            valid_shoulders.append((r_sh["x_norm"], r_sh["y_norm"], r_sh["x_px"], r_sh["y_px"]))

        if not valid_ears or not valid_shoulders:
            return 0.0, None, None

        # Calculate midpoints in normalized & pixel space
        ear_norm_x = sum(e[0] for e in valid_ears) / len(valid_ears)
        ear_norm_y = sum(e[1] for e in valid_ears) / len(valid_ears)
        ear_px = (
            int(sum(e[2] for e in valid_ears) / len(valid_ears)),
            int(sum(e[3] for e in valid_ears) / len(valid_ears)),
        )

        sh_norm_x = sum(s[0] for s in valid_shoulders) / len(valid_shoulders)
        sh_norm_y = sum(s[1] for s in valid_shoulders) / len(valid_shoulders)
        sh_px = (
            int(sum(s[2] for s in valid_shoulders) / len(valid_shoulders)),
            int(sum(s[3] for s in valid_shoulders) / len(valid_shoulders)),
        )

        # Delta vector from shoulder to ear
        delta_x = abs(ear_norm_x - sh_norm_x)
        delta_y = max(sh_norm_y - ear_norm_y, 1e-5)

        # Angle with upward vertical vector (0, 1) in degrees
        angle_rad = math.atan2(delta_x, delta_y)
        angle_deg = math.degrees(angle_rad)

        return float(angle_deg), ear_px, sh_px

    def calculate_screen_proximity(
        self, keypoints: Dict
    ) -> Tuple[float, Optional[Tuple[int, int, int, int]]]:
        """
        Calculates relative screen proximity based on head bounding geometry.
        As the user leans toward the camera/monitor, the face bounding box & inter-ear distance expand.
        
        Returns:
            (normalized_proximity_metric, (min_x, min_y, max_x, max_y) in px)
        """
        l_ear = keypoints["left_ear"]
        r_ear = keypoints["right_ear"]
        nose = keypoints["nose"]

        head_points_norm = []
        head_points_px = []

        for pt in [nose, l_ear, r_ear]:
            if pt["visibility"] >= self.min_visibility:
                head_points_norm.append((pt["x_norm"], pt["y_norm"]))
                head_points_px.append((pt["x_px"], pt["y_px"]))

        if len(head_points_norm) < 2:
            return 0.0, None

        # Primary metric: Inter-ear Euclidean distance in normalized coordinates
        if l_ear["visibility"] >= self.min_visibility and r_ear["visibility"] >= self.min_visibility:
            inter_ear_dist = math.hypot(
                l_ear["x_norm"] - r_ear["x_norm"],
                l_ear["y_norm"] - r_ear["y_norm"],
            )
            proximity_metric = inter_ear_dist
        else:
            # Fallback: Distance between nose and visible ear scaled
            ear = l_ear if l_ear["visibility"] >= self.min_visibility else r_ear
            proximity_metric = math.hypot(nose["x_norm"] - ear["x_norm"], nose["y_norm"] - ear["y_norm"]) * 1.8

        # Calculate pixel bounding box for visual overlay
        all_x = [p[0] for p in head_points_px]
        all_y = [p[1] for p in head_points_px]
        pad_x = 35
        pad_y = 45
        bbox_px = (
            max(0, min(all_x) - pad_x),
            max(0, min(all_y) - pad_y),
            max(all_x) + pad_x,
            max(all_y) + pad_y,
        )

        return float(proximity_metric), bbox_px

    def calculate_shoulder_tilt(
        self, keypoints: Dict
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """
        Calculates lateral shoulder tilt (degrees deviation from horizontal).
        Detects resting on one elbow, uneven posture, or lateral spinal slumping.
        Upright/balanced shoulders: 0° - 5°.
        Lateral lean/asymmetry: > 8°.
        
        Returns:
            (tilt_angle_deg, left_shoulder_px, right_shoulder_px)
        """
        l_sh = keypoints["left_shoulder"]
        r_sh = keypoints["right_shoulder"]

        if l_sh["visibility"] < self.min_visibility or r_sh["visibility"] < self.min_visibility:
            return 0.0, None, None

        l_sh_px = (l_sh["x_px"], l_sh["y_px"])
        r_sh_px = (r_sh["x_px"], r_sh["y_px"])

        delta_x = abs(r_sh["x_norm"] - l_sh["x_norm"])
        delta_y = abs(r_sh["y_norm"] - l_sh["y_norm"])

        if delta_x < 1e-4:
            return 0.0, l_sh_px, r_sh_px

        angle_rad = math.atan2(delta_y, delta_x)
        angle_deg = math.degrees(angle_rad)

        return float(angle_deg), l_sh_px, r_sh_px
