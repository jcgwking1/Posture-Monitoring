"""
Posture State Machine, Biomechanical Tracker & Health Analytics.
Tracks continuous violations, sedentary time, and calculates session ergonomic score.
"""

import time
from typing import Optional
from src.config import (
    DEFAULT_NECK_ANGLE_THRESHOLD,
    DEFAULT_PROXIMITY_THRESHOLD,
    DEFAULT_SEDENTARY_LIMIT_MINUTES,
    DEFAULT_SHOULDER_TILT_THRESHOLD,
    DEFAULT_VIOLATION_TIMEOUT,
    PostureMetrics,
)


class PostureTracker:
    """
    Manages consecutive posture violation state, sedentary duration, and session metrics.
    """

    def __init__(
        self,
        neck_threshold: float = DEFAULT_NECK_ANGLE_THRESHOLD,
        proximity_threshold: float = DEFAULT_PROXIMITY_THRESHOLD,
        shoulder_threshold: float = DEFAULT_SHOULDER_TILT_THRESHOLD,
        violation_timeout: float = DEFAULT_VIOLATION_TIMEOUT,
        sedentary_limit_minutes: float = DEFAULT_SEDENTARY_LIMIT_MINUTES,
    ):
        self.neck_threshold = neck_threshold
        self.proximity_threshold = proximity_threshold
        self.shoulder_threshold = shoulder_threshold
        self.violation_timeout = violation_timeout
        self.sedentary_limit_minutes = sedentary_limit_minutes

        self.violation_start_time: Optional[float] = None
        self.calibrated_proximity: Optional[float] = None
        self.calibrated_neck_angle: Optional[float] = None
        self.calibrated_shoulder_tilt: Optional[float] = None

        # Session Analytics
        now = time.monotonic()
        self.session_start_time: float = now
        self.last_frame_time: float = now
        self.sedentary_start_time: float = now
        self.total_monitored_seconds: float = 0.0
        self.total_violation_seconds: float = 0.0
        self.total_violations_count: int = 0
        self._in_violation_previously: bool = False

    def calibrate(self, current_angle: float, current_proximity: float, current_shoulder: float = 0.0):
        """
        Calibrates the user's current baseline seated posture.
        Dynamic thresholds are derived relative to user's camera distance and height.
        """
        self.calibrated_neck_angle = current_angle
        self.calibrated_proximity = current_proximity
        self.calibrated_shoulder_tilt = current_shoulder

        # Proximity threshold set to 30% increase above calibrated distance
        self.proximity_threshold = current_proximity * 1.30
        # Neck threshold set to +12 degrees over calibrated neutral
        self.neck_threshold = max(DEFAULT_NECK_ANGLE_THRESHOLD, current_angle + 12.0)
        # Shoulder threshold set to +5 degrees over baseline
        self.shoulder_threshold = max(DEFAULT_SHOULDER_TILT_THRESHOLD, current_shoulder + 5.0)

    def update(self, neck_angle: float, proximity: float, shoulder_tilt: float = 0.0) -> PostureMetrics:
        """
        Evaluates current metrics against thresholds, updates timers, and computes session score.
        """
        now = time.monotonic()
        dt = max(0.0, min(1.0, now - self.last_frame_time))  # Bound frame delta
        self.last_frame_time = now
        self.total_monitored_seconds += dt

        is_slouching = neck_angle > self.neck_threshold
        is_too_close = proximity > self.proximity_threshold
        is_shoulder_tilted = shoulder_tilt > self.shoulder_threshold

        has_violation = is_slouching or is_too_close or is_shoulder_tilted

        if has_violation:
            self.total_violation_seconds += dt
            if self.violation_start_time is None:
                self.violation_start_time = now
                if not self._in_violation_previously:
                    self.total_violations_count += 1
                    self._in_violation_previously = True
            duration = now - self.violation_start_time
        else:
            self.violation_start_time = None
            duration = 0.0
            self._in_violation_previously = False

        alert_active = duration >= self.violation_timeout

        # Sedentary monitoring
        sedentary_duration_min = (now - self.sedentary_start_time) / 60.0
        is_sedentary_alert = sedentary_duration_min >= self.sedentary_limit_minutes

        # Session Ergonomic Health Score
        if self.total_monitored_seconds > 0:
            health_score = max(0.0, 100.0 * (1.0 - (self.total_violation_seconds / self.total_monitored_seconds)))
        else:
            health_score = 100.0

        # Construct contextual status label
        if alert_active:
            status = "CRITICAL: Bad Posture > 10s!"
        elif has_violation:
            reasons = []
            if is_slouching:
                reasons.append("Slouching")
            if is_too_close:
                reasons.append("Screen Too Close")
            if is_shoulder_tilted:
                reasons.append("Shoulder Slanted")
            status = f"WARNING: {', '.join(reasons)} ({duration:.1f}s)"
        else:
            status = "HEALTHY: Good Posture"

        return PostureMetrics(
            neck_angle=neck_angle,
            screen_proximity=proximity,
            shoulder_tilt=shoulder_tilt,
            is_slouching=is_slouching,
            is_too_close=is_too_close,
            is_shoulder_tilted=is_shoulder_tilted,
            violation_active=alert_active,
            violation_duration=duration,
            status_label=status,
            sedentary_duration_min=sedentary_duration_min,
            is_sedentary_alert=is_sedentary_alert,
            session_health_score=round(health_score, 1),
            total_violations_count=self.total_violations_count,
        )

    def reset_sedentary_timer(self):
        """Resets the sedentary desk clock when user stands up or stretches."""
        self.sedentary_start_time = time.monotonic()

    def reset(self):
        """Resets the violation and session state."""
        now = time.monotonic()
        self.violation_start_time = None
        self.session_start_time = now
        self.sedentary_start_time = now
        self.total_monitored_seconds = 0.0
        self.total_violation_seconds = 0.0
        self.total_violations_count = 0
        self._in_violation_previously = False
