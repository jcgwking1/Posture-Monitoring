"""
Computer Vision Guided Stretch Routine & Pose Verifier.
Implements the 4-Step Biomechanical Reset (Neck Tilt, Overhead Reach, Chest Opener, Standing Hip Extension)
with humanoid pose demonstrations.
"""

import time
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np

from src.config import (
    LEFT_EAR,
    LEFT_ELBOW,
    LEFT_HIP,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NOSE,
    RIGHT_EAR,
    RIGHT_ELBOW,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
)


class StretchGuide:
    """
    Manages interactive 4-step stretch states, body geometry verification,
    and humanoid demonstration figures.
    """

    STRETCHES = [
        {
            "id": 1,
            "name": "1/4: Lateral Neck Release",
            "instruction": "Tilt your head toward your shoulder to release neck tension.",
            "target_seconds": 4.0,
        },
        {
            "id": 2,
            "name": "2/4: Overhead Sky Reach",
            "instruction": "Reach both arms straight up to decompress your spine.",
            "target_seconds": 4.0,
        },
        {
            "id": 3,
            "name": "3/4: Chest Opener (Cactus Arms)",
            "instruction": "Pull elbows wide at shoulder height and pinch shoulder blades.",
            "target_seconds": 4.0,
        },
        {
            "id": 4,
            "name": "4/4: Standing Hip Extension",
            "instruction": "Stand up tall, put hands on hips, and push pelvis forward.",
            "target_seconds": 4.0,
        },
    ]

    def __init__(self):
        self.is_active: bool = False
        self.current_stretch_idx: int = 0
        self.hold_duration: float = 0.0
        self.last_update_time: Optional[float] = None
        self.is_completed: bool = False
        self.is_holding_correct_pose: bool = False

    def start(self):
        """Activates the guided stretching mode."""
        self.is_active = True
        self.current_stretch_idx = 0
        self.hold_duration = 0.0
        self.last_update_time = time.monotonic()
        self.is_completed = False
        self.is_holding_correct_pose = False

    def update(self, landmarks: List) -> Tuple[bool, float, str, str]:
        """
        Analyzes pose landmarks against current stretch criteria.
        
        Returns:
            (is_pose_correct, progress_ratio [0.0 - 1.0], current_stretch_name, instruction_text)
        """
        if not self.is_active or self.is_completed or not landmarks:
            return False, 0.0, "", ""

        now = time.monotonic()
        dt = max(0.0, min(0.5, now - (self.last_update_time or now)))
        self.last_update_time = now

        current_stretch = self.STRETCHES[self.current_stretch_idx]
        is_correct = self._check_pose(self.current_stretch_idx, landmarks)
        self.is_holding_correct_pose = is_correct

        if is_correct:
            self.hold_duration += dt
            if self.hold_duration >= current_stretch["target_seconds"]:
                if self.current_stretch_idx < len(self.STRETCHES) - 1:
                    self.current_stretch_idx += 1
                    self.hold_duration = 0.0
                    self.is_holding_correct_pose = False
                else:
                    self.is_completed = True
                    self.is_active = False
        else:
            # Gentle decay rather than instant penalty
            self.hold_duration = max(0.0, self.hold_duration - dt * 0.5)

        progress = min(1.0, self.hold_duration / current_stretch["target_seconds"])
        return is_correct, progress, current_stretch["name"], current_stretch["instruction"]

    def _check_pose(self, stretch_idx: int, landmarks: List) -> bool:
        """
        Validates biomechanics against the target exercise.
        """
        nose = landmarks[NOSE]
        l_ear = landmarks[LEFT_EAR]
        r_ear = landmarks[RIGHT_EAR]
        l_sh = landmarks[LEFT_SHOULDER]
        r_sh = landmarks[RIGHT_SHOULDER]
        l_elbow = landmarks[LEFT_ELBOW]
        r_elbow = landmarks[RIGHT_ELBOW]
        l_wrist = landmarks[LEFT_WRIST]
        r_wrist = landmarks[RIGHT_WRIST]

        # Stretch 1: Lateral Neck Release (Head tilted to side)
        if stretch_idx == 0:
            ear_dx = abs(r_ear.x - l_ear.x)
            ear_dy = abs(r_ear.y - l_ear.y)
            neck_tilt_deg = np.degrees(np.arctan2(ear_dy, max(1e-4, ear_dx)))
            ear_sh_dist_l = abs(l_ear.y - l_sh.y)
            ear_sh_dist_r = abs(r_ear.y - r_sh.y)
            return bool(neck_tilt_deg > 14.0 or ear_sh_dist_l < 0.12 or ear_sh_dist_r < 0.12)

        # Stretch 2: Overhead Sky Reach (Both hands above head/nose)
        elif stretch_idx == 1:
            hands_above_head = (l_wrist.y < nose.y) and (r_wrist.y < nose.y)
            return bool(hands_above_head)

        # Stretch 3: Chest Opener / Cactus Arms (Elbows wide at shoulder height, wrists up)
        elif stretch_idx == 2:
            wrists_up = (l_wrist.y < l_sh.y) and (r_wrist.y < r_sh.y)
            elbows_flared = abs(l_elbow.x - r_elbow.x) > abs(l_sh.x - r_sh.x) * 1.25
            return bool(wrists_up and elbows_flared)

        # Stretch 4: Standing Hip Extension (User standing + hands on hips/waist)
        elif stretch_idx == 3:
            # Standing check: Shoulders elevated into upper half of camera view
            user_standing = (l_sh.y < 0.48) and (r_sh.y < 0.48)
            # Hands placed near waist/hips
            hands_on_hips = (l_wrist.y > l_sh.y + 0.10) and (r_wrist.y > r_sh.y + 0.10)
            return bool(user_standing and hands_on_hips)

        return False

    def draw_demonstration_avatar(
        self,
        frame: np.ndarray,
        box_x: int,
        box_y: int,
        box_w: int,
        box_h: int,
        stretch_idx: int,
        is_correct: bool,
    ):
        """
        Renders a sleek, high-contrast humanoid stick-figure demonstration
        illustrating exactly how to perform the current stretch.
        """
        # Outer PiP container
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), (24, 24, 32), -1)
        border_color = (0, 255, 120) if is_correct else (0, 215, 255)
        cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), border_color, 2)

        # Title strip
        cv2.putText(
            frame,
            "HOW TO DO IT",
            (box_x + 22, box_y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            border_color,
            1,
            cv2.LINE_AA,
        )

        cx = box_x + box_w // 2
        cy = box_y + box_h // 2 + 10

        c_bone = (230, 230, 230)
        c_accent = (0, 215, 255)
        c_glow = (0, 255, 150) if is_correct else (0, 200, 255)

        # 1. Torso Spine & Hips
        cv2.line(frame, (cx, cy - 24), (cx, cy + 18), c_bone, 3, cv2.LINE_AA)
        cv2.line(frame, (cx - 16, cy + 18), (cx + 16, cy + 18), c_bone, 2, cv2.LINE_AA)

        # 2. Legs
        cv2.line(frame, (cx - 12, cy + 18), (cx - 14, cy + 72), (170, 170, 170), 2, cv2.LINE_AA)
        cv2.line(frame, (cx + 12, cy + 18), (cx + 14, cy + 72), (170, 170, 170), 2, cv2.LINE_AA)

        # 3. Head & Arms Per Specific Stretch
        if stretch_idx == 0:
            # --- STRETCH 1: Neck Tilt ---
            # Tilted Head
            head_center = (cx + 12, cy - 46)
            cv2.line(frame, (cx, cy - 24), head_center, c_bone, 2, cv2.LINE_AA)
            cv2.circle(frame, head_center, 12, c_glow, -1, cv2.LINE_AA)
            # Neck tilt curved arrow
            cv2.ellipse(frame, (cx, cy - 44), (22, 14), 0, -30, 45, (0, 255, 255), 2, cv2.LINE_AA)
            # Relaxed arms
            cv2.line(frame, (cx - 18, cy - 22), (cx - 24, cy + 22), c_bone, 2, cv2.LINE_AA)
            cv2.line(frame, (cx + 18, cy - 22), (cx + 24, cy + 22), c_bone, 2, cv2.LINE_AA)

        elif stretch_idx == 1:
            # --- STRETCH 2: Overhead Sky Reach ---
            head_center = (cx, cy - 48)
            cv2.circle(frame, head_center, 12, c_bone, -1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 36), (cx, cy - 24), c_bone, 2, cv2.LINE_AA)

            # Both arms reaching straight UP
            cv2.line(frame, (cx - 18, cy - 24), (cx - 14, cy - 78), c_glow, 3, cv2.LINE_AA)
            cv2.line(frame, (cx + 18, cy - 24), (cx + 14, cy - 78), c_glow, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx - 14, cy - 78), 5, c_glow, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx + 14, cy - 78), 5, c_glow, -1, cv2.LINE_AA)
            # Upward arrows
            cv2.arrowedLine(frame, (cx - 14, cy - 50), (cx - 14, cy - 74), (0, 255, 255), 2, tipLength=0.35)
            cv2.arrowedLine(frame, (cx + 14, cy - 50), (cx + 14, cy - 74), (0, 255, 255), 2, tipLength=0.35)

        elif stretch_idx == 2:
            # --- STRETCH 3: Chest Opener (Cactus Arms) ---
            head_center = (cx, cy - 48)
            cv2.circle(frame, head_center, 12, c_bone, -1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 36), (cx, cy - 24), c_bone, 2, cv2.LINE_AA)

            # Horizontal upper arms, vertical forearms (Goalpost)
            cv2.line(frame, (cx - 18, cy - 24), (cx - 42, cy - 24), c_glow, 3, cv2.LINE_AA)
            cv2.line(frame, (cx - 42, cy - 24), (cx - 42, cy - 65), c_glow, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx - 42, cy - 24), 4, c_accent, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx - 42, cy - 65), 5, c_glow, -1, cv2.LINE_AA)

            cv2.line(frame, (cx + 18, cy - 24), (cx + 42, cy - 24), c_glow, 3, cv2.LINE_AA)
            cv2.line(frame, (cx + 42, cy - 24), (cx + 42, cy - 65), c_glow, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx + 42, cy - 24), 4, c_accent, -1, cv2.LINE_AA)
            cv2.circle(frame, (cx + 42, cy - 65), 5, c_glow, -1, cv2.LINE_AA)

            # Lateral spread indicator
            cv2.arrowedLine(frame, (cx - 20, cy - 45), (cx - 38, cy - 45), (0, 255, 255), 2, tipLength=0.4)
            cv2.arrowedLine(frame, (cx + 20, cy - 45), (cx + 38, cy - 45), (0, 255, 255), 2, tipLength=0.4)

        elif stretch_idx == 3:
            # --- STRETCH 4: Standing Hip Extension ---
            head_center = (cx, cy - 48)
            cv2.circle(frame, head_center, 12, c_glow, -1, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 36), (cx, cy - 24), c_bone, 2, cv2.LINE_AA)

            # Hands on hips (elbows flared out, wrists on hips)
            cv2.line(frame, (cx - 18, cy - 24), (cx - 36, cy - 2), c_glow, 3, cv2.LINE_AA)
            cv2.line(frame, (cx - 36, cy - 2), (cx - 14, cy + 18), c_glow, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx - 14, cy + 18), 5, c_glow, -1, cv2.LINE_AA)

            cv2.line(frame, (cx + 18, cy - 24), (cx + 36, cy - 2), c_glow, 3, cv2.LINE_AA)
            cv2.line(frame, (cx + 36, cy - 2), (cx + 14, cy + 18), c_glow, 3, cv2.LINE_AA)
            cv2.circle(frame, (cx + 14, cy + 18), 5, c_glow, -1, cv2.LINE_AA)

            # Forward pelvic push arrow
            cv2.arrowedLine(frame, (cx, cy + 18), (cx, cy + 4), (0, 255, 255), 2, tipLength=0.45)

    def reset(self):
        """Resets the stretching guide."""
        self.is_active = False
        self.current_stretch_idx = 0
        self.hold_duration = 0.0
        self.is_completed = False
        self.is_holding_correct_pose = False
