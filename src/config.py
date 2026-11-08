"""
Ergonomics Configuration & Threshold Defaults.
"""

from dataclasses import dataclass

# MediaPipe Pose Landmark Indices (Standard 33-point model)
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24

# Default Ergonomic Thresholds
DEFAULT_NECK_ANGLE_THRESHOLD = 32.0       # Degrees deviation from vertical (higher = severe slouch)
DEFAULT_PROXIMITY_THRESHOLD = 0.22        # Normalized horizontal span between ears (closer = higher)
DEFAULT_SHOULDER_TILT_THRESHOLD = 8.0     # Degrees deviation from horizontal (higher = lateral slump)
DEFAULT_VIOLATION_TIMEOUT = 10.0         # Consecutive seconds before bad posture alarm triggers
DEFAULT_SEDENTARY_LIMIT_MINUTES = 50.0    # Minutes of continuous desk sitting before stretch reminder (default: 50.0, test: 0.5)

# Feedback Timing & Cooldowns
AUDIO_ALERT_COOLDOWN = 3.5                # Minimum seconds between repeated chime beeps
TOAST_ALERT_COOLDOWN = 15.0               # Minimum seconds between repeated Windows desktop toasts
NOISY_ALARM_INTERVAL = 1.6                # Seconds between aggressive siren bursts if user refuses to stand

# OpenCV BGR Color Palette (Optimized for contrast on video feed)
COLOR_GOOD = (70, 200, 70)           # Green
COLOR_WARNING = (0, 215, 255)        # Amber / Gold
COLOR_ALERT = (50, 50, 230)          # Red
COLOR_TEXT = (255, 255, 255)         # White
COLOR_GUIDE = (180, 180, 180)        # Muted Gray
COLOR_BG_DARK = (20, 20, 20)         # Dark Gray for HUD background boxes
COLOR_AVATAR_BG = (15, 17, 23)       # Sleek Dark Slate for Wireframe Avatar Canvas

@dataclass
class PostureMetrics:
    neck_angle: float
    screen_proximity: float
    shoulder_tilt: float
    is_slouching: bool
    is_too_close: bool
    is_shoulder_tilted: bool
    violation_active: bool
    violation_duration: float
    status_label: str
    sedentary_duration_min: float
    is_sedentary_alert: bool
    session_health_score: float
    total_violations_count: int
