"""
Alert & Feedback Subsystem.
Renders real-time HUD overlays, triggers non-blocking Windows chimes and native Desktop Toasts.
"""

import os
import subprocess
import sys
import threading
import time
from typing import Optional, Tuple
import cv2
import numpy as np

from src.config import (
    AUDIO_ALERT_COOLDOWN,
    COLOR_ALERT,
    COLOR_BG_DARK,
    COLOR_GOOD,
    COLOR_GUIDE,
    COLOR_TEXT,
    COLOR_WARNING,
    NOISY_ALARM_INTERVAL,
    PostureMetrics,
    TOAST_ALERT_COOLDOWN,
)


class AlertManager:
    """
    Manages non-blocking audio alerts, Windows 11 desktop toasts, and visual HUD overlays.
    """

    def __init__(self, enable_toasts: bool = True):
        self.enable_toasts = enable_toasts
        self.last_chime_time: float = 0.0
        self.last_toast_time: float = 0.0
        self.toast_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "send_toast.ps1")
        )
        self.toast_window_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "toast_window.py")
        )
        self.last_noisy_alarm_time: float = 0.0

    def trigger_noisy_alarm(self):
        """
        Triggers an intense, aggressive pulsating siren (1800Hz - 2600Hz)
        to compel the user to stand up when sedentary limits are exceeded.
        """
        now = time.monotonic()
        if now - self.last_noisy_alarm_time < NOISY_ALARM_INTERVAL:
            return

        self.last_noisy_alarm_time = now

        def _play_siren():
            try:
                if sys.platform == "win32":
                    import winsound
                    # Sharp dual-frequency emergency pulse
                    winsound.Beep(1800, 100)
                    winsound.Beep(2600, 140)
                    winsound.Beep(1800, 100)
                    winsound.Beep(2600, 160)
                else:
                    for _ in range(3):
                        print("\a", end="", flush=True)
                        time.sleep(0.1)
            except Exception:
                pass

        threading.Thread(target=_play_siren, daemon=True).start()

    def trigger_success_chime(self):
        """Plays a pleasant 3-tone victory chime upon completing stretch routine."""
        def _play_success():
            try:
                if sys.platform == "win32":
                    import winsound
                    winsound.Beep(523, 100)  # C5
                    winsound.Beep(659, 100)  # E5
                    winsound.Beep(784, 250)  # G5
            except Exception:
                pass

        threading.Thread(target=_play_success, daemon=True).start()

    def trigger_audio_chime(self):
        """
        Triggers a non-blocking audio alert. On Windows, uses winsound with debouncing.
        Spawns a daemon thread to guarantee zero frame-rate drop in the CV loop.
        """
        now = time.monotonic()
        if now - self.last_chime_time < AUDIO_ALERT_COOLDOWN:
            return

        self.last_chime_time = now

        def _play_sound():
            try:
                if sys.platform == "win32":
                    import winsound
                    winsound.Beep(750, 150)
                    winsound.Beep(950, 200)
                else:
                    print("\a", end="", flush=True)
            except Exception:
                pass

        threading.Thread(target=_play_sound, daemon=True).start()

    def trigger_windows_toast(self, title: str, message: str):
        """
        Pops up a guaranteed top-most floating toast card in the bottom-right corner
        of the Windows desktop (directly visible on top of Antigravity, VS Code, etc.)
        and registers a Windows Action Center notification.
        """
        if not self.enable_toasts:
            return

        now = time.monotonic()
        if now - self.last_toast_time < TOAST_ALERT_COOLDOWN:
            return  # Throttle notifications to prevent notification spam

        self.last_toast_time = now

        def _send():
            try:
                # 1. Guaranteed Top-Most Bottom-Right Desktop Overlay Toast (Visible over all apps)
                if os.path.exists(self.toast_window_script):
                    subprocess.Popen(
                        [sys.executable, self.toast_window_script, title, message, "4500"],
                        creationflags=0x08000000 if sys.platform == "win32" else 0,
                    )

                # 2. Windows 11 Action Center Notification Dispatch
                if os.path.exists(self.toast_script):
                    subprocess.Popen(
                        [
                            "powershell",
                            "-ExecutionPolicy",
                            "Bypass",
                            "-File",
                            self.toast_script,
                            "-Title",
                            title,
                            "-Message",
                            message,
                        ],
                        creationflags=0x08000000 if sys.platform == "win32" else 0,
                    )
            except Exception:
                pass

        threading.Thread(target=_send, daemon=True).start()

    def draw_hud(
        self,
        frame: np.ndarray,
        metrics: PostureMetrics,
        ear_px: Optional[Tuple[int, int]],
        sh_px: Optional[Tuple[int, int]],
        bbox_px: Optional[Tuple[int, int, int, int]],
        l_sh_px: Optional[Tuple[int, int]] = None,
        r_sh_px: Optional[Tuple[int, int]] = None,
    ) -> np.ndarray:
        """
        Renders HUD overlays: status banners, vector lines, shoulder slant guides,
        head bounding box, and violation progress.
        """
        h, w, _ = frame.shape

        # Select state colors and trigger actions
        if metrics.violation_active:
            theme_color = COLOR_ALERT
            self.trigger_audio_chime()

            # Direct, action-oriented alerts without numbers
            if metrics.is_slouching and metrics.is_too_close:
                action_text = "Sit upright and step back from the screen!"
            elif metrics.is_slouching:
                action_text = "You're slouching! Sit back and align your spine."
            elif metrics.is_too_close:
                action_text = "Too close to the monitor! Lean back."
            elif metrics.is_shoulder_tilted:
                action_text = "You're leaning to one side! Level your shoulders."
            else:
                action_text = "Sit upright and align your posture!"

            self.trigger_windows_toast("⚠️ Posture Alert!", action_text)
        elif metrics.is_slouching or metrics.is_too_close or metrics.is_shoulder_tilted:
            theme_color = COLOR_WARNING
        else:
            theme_color = COLOR_GOOD
            # Reset toast cooldown once healthy posture has been restored
            if self.last_toast_time > 0 and (time.monotonic() - self.last_toast_time > 10.0):
                self.last_toast_time = 0.0

        # 1. Draw Neck Inclination Vector & Vertical Guide
        if ear_px and sh_px:
            cv2.line(frame, sh_px, ear_px, theme_color, 2, cv2.LINE_AA)
            vert_guide_top = (sh_px[0], max(0, sh_px[1] - 80))
            cv2.line(frame, sh_px, vert_guide_top, COLOR_GUIDE, 1, cv2.LINE_AA)
            cv2.circle(frame, ear_px, 5, theme_color, -1, cv2.LINE_AA)
            cv2.circle(frame, sh_px, 5, theme_color, -1, cv2.LINE_AA)

        # 2. Draw Shoulder Alignment & Horizontal Level Guide
        if l_sh_px and r_sh_px:
            sh_color = COLOR_ALERT if metrics.is_shoulder_tilted else theme_color
            cv2.line(frame, l_sh_px, r_sh_px, sh_color, 2, cv2.LINE_AA)
            # Horizontal guideline through midpoint
            mid_sh_x = (l_sh_px[0] + r_sh_px[0]) // 2
            mid_sh_y = (l_sh_px[1] + r_sh_px[1]) // 2
            cv2.line(frame, (mid_sh_x - 60, mid_sh_y), (mid_sh_x + 60, mid_sh_y), COLOR_GUIDE, 1, cv2.LINE_AA)
            cv2.circle(frame, l_sh_px, 4, sh_color, -1, cv2.LINE_AA)
            cv2.circle(frame, r_sh_px, 4, sh_color, -1, cv2.LINE_AA)

        # 3. Draw Head Bounding Box
        if bbox_px:
            x1, y1, x2, y2 = bbox_px
            cv2.rectangle(frame, (x1, y1), (x2, y2), theme_color, 2)

        # 4. Top Telemetry HUD Header Bar
        hud_bg_height = 70
        cv2.rectangle(frame, (0, 0), (w, hud_bg_height), COLOR_BG_DARK, -1)
        cv2.rectangle(frame, (0, 0), (w, 5), theme_color, -1)

        cv2.putText(
            frame,
            metrics.status_label,
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            theme_color,
            2,
            cv2.LINE_AA,
        )

        detail_text = (
            f"Neck: {metrics.neck_angle:.1f}deg | Proximity: {metrics.screen_proximity:.2f} | "
            f"Shoulder Tilt: {metrics.shoulder_tilt:.1f}deg"
        )
        cv2.putText(
            frame,
            detail_text,
            (16, 54),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            COLOR_TEXT,
            1,
            cv2.LINE_AA,
        )

        # 5. Violation Progress Countdown Bar
        if metrics.violation_duration > 0 and not metrics.violation_active:
            bar_w = 170
            bar_h = 13
            bar_x = w - bar_w - 20
            bar_y = 18
            progress = min(1.0, metrics.violation_duration / 10.0)

            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 50), -1)
            cv2.rectangle(
                frame,
                (bar_x, bar_y),
                (bar_x + int(bar_w * progress), bar_y + bar_h),
                theme_color,
                -1,
            )
            cv2.putText(
                frame,
                f"Alert in: {10.0 - metrics.violation_duration:.1f}s",
                (bar_x, bar_y + bar_h + 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.38,
                COLOR_TEXT,
                1,
                cv2.LINE_AA,
            )

        # 6. Critical Alert Overlay when > 10s Violation
        if metrics.violation_active:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOR_ALERT, 6)

            banner_y = h // 2
            banner_h = 55
            sub_overlay = frame.copy()
            cv2.rectangle(
                sub_overlay,
                (0, banner_y - banner_h // 2),
                (w, banner_y + banner_h // 2),
                COLOR_ALERT,
                -1,
            )
            cv2.addWeighted(sub_overlay, 0.75, frame, 0.25, 0, frame)

            alert_msg = "POOR POSTURE ALERT: SIT UPRIGHT & PULL BACK!"
            text_size = cv2.getTextSize(alert_msg, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
            text_x = (w - text_size[0]) // 2
            cv2.putText(
                frame,
                alert_msg,
                (text_x, banner_y + 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                COLOR_TEXT,
                2,
                cv2.LINE_AA,
            )

        # 7. Sedentary Alert Toast & Warning Strip
        if metrics.is_sedentary_alert:
            self.trigger_windows_toast(
                "🚶 Sedentary Break",
                "Time to stand up, walk around, and stretch!",
            )
            # Display bottom banner
            bot_y = h - 28
            cv2.rectangle(frame, (0, bot_y), (w, h), (0, 100, 200), -1)
            sed_msg = "SEDENTARY ALERT: Time to stand up & stretch!"
            s_size = cv2.getTextSize(sed_msg, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
            cv2.putText(
                frame,
                sed_msg,
                ((w - s_size[0]) // 2, bot_y + 19),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                COLOR_TEXT,
                1,
                cv2.LINE_AA,
            )

        return frame

    def draw_stretch_overlay(
        self,
        frame: np.ndarray,
        stretch_guide,
        is_correct: bool,
        progress: float,
        stretch_name: str,
        instruction: str,
    ) -> np.ndarray:
        """
        Renders the interactive Guided Stretching HUD:
        Shows target stretch, humanoid stick-figure demonstration on the side,
        real-time pose verification, progress countdown, and siren warning.
        """
        h, w, _ = frame.shape

        # 1. Semi-transparent backdrop for high contrast
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (15, 15, 20), -1)
        cv2.addWeighted(overlay, 0.40, frame, 0.60, 0, frame)

        # 2. Top Warning Banner
        cv2.rectangle(frame, (0, 0), (w, 46), (0, 80, 220), -1)
        top_title = f"TIME TO STAND UP & STRETCH! (Exercise {stretch_guide.current_stretch_idx + 1}/{len(stretch_guide.STRETCHES)})"
        t_size = cv2.getTextSize(top_title, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)[0]
        cv2.putText(
            frame,
            top_title,
            ((w - t_size[0]) // 2, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            COLOR_TEXT,
            2,
            cv2.LINE_AA,
        )

        # 3. Side Humanoid Stick-Figure Demonstration Card
        demo_w = 150
        demo_h = 205
        demo_x = w - demo_w - 20
        demo_y = 56
        stretch_guide.draw_demonstration_avatar(
            frame, demo_x, demo_y, demo_w, demo_h, stretch_guide.current_stretch_idx, is_correct
        )

        # 4. Exercise Name Box (Left of Demo Avatar)
        cv2.rectangle(frame, (20, 56), (demo_x - 14, 94), (35, 35, 48), -1)
        cv2.putText(
            frame,
            f"TARGET: {stretch_name.upper()}",
            (30, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            COLOR_WARNING,
            2,
            cv2.LINE_AA,
        )

        # 5. Instruction Banner (Left of Demo Avatar)
        cv2.putText(
            frame,
            instruction,
            (30, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.41,
            COLOR_TEXT,
            1,
            cv2.LINE_AA,
        )

        # 6. Live Pose Status Card & Progress Bar (Bottom)
        card_y = h - 105
        card_h = 90
        cv2.rectangle(frame, (20, card_y), (w - 20, card_y + card_h), (25, 25, 34), -1)

        if is_correct:
            status_text = "PERFECT! KEEP HOLDING POSE..."
            badge_color = COLOR_GOOD
        else:
            status_text = "POSE NOT MATCHED - FOLLOW THE DEMO ON THE RIGHT"
            badge_color = COLOR_ALERT
            # User refusing to stretch -> Sound aggressive siren
            self.trigger_noisy_alarm()
            cv2.putText(
                frame,
                "SIREN ACTIVE UNTIL YOU STRETCH",
                (w - 280, card_y + 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                COLOR_ALERT,
                1,
                cv2.LINE_AA,
            )

        cv2.putText(
            frame,
            status_text,
            (36, card_y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            badge_color,
            2,
            cv2.LINE_AA,
        )

        # Progress bar
        bar_x = 36
        bar_y = card_y + 40
        bar_w = w - 72
        bar_h = 22
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (50, 50, 60), -1)
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), badge_color, -1)

        pct_label = f"Hold Progress: {int(progress * 100)}%"
        cv2.putText(
            frame,
            pct_label,
            (bar_x + 12, bar_y + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            COLOR_TEXT,
            1,
            cv2.LINE_AA,
        )

        return frame
