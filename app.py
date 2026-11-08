"""
Real-Time Posture & Ergonomics Monitor - Full Suite
Features: Neck Slouch, Screen Proximity, Shoulder Asymmetry, Windows 11 Toasts,
          Sedentary Desk Timer, Session Health Score, and Privacy Wireframe Avatar Mode.
Hardware Target: Windows 11, Intel Core i5-12450HX, 8GB RAM, NVIDIA RTX 3050
"""

import time
import cv2
import numpy as np
import streamlit as st

from src.alert_manager import AlertManager
from src.config import (
    COLOR_AVATAR_BG,
    DEFAULT_NECK_ANGLE_THRESHOLD,
    DEFAULT_PROXIMITY_THRESHOLD,
    DEFAULT_SEDENTARY_LIMIT_MINUTES,
    DEFAULT_SHOULDER_TILT_THRESHOLD,
    DEFAULT_VIOLATION_TIMEOUT,
)
from src.ergonomic_math import ErgonomicCalculator
from src.pose_detector import PoseDetector
from src.stretch_guide import StretchGuide
from src.tracker import PostureTracker

# ---------------------------------------------------------
# Streamlit Page Setup
# ---------------------------------------------------------
st.set_page_config(
    page_title="Posture & Ergonomics Monitor",
    page_icon="🧘",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧘 Real-Time Posture & Ergonomics Monitor")
st.caption(
    "AI Biomechanical telemetry alerting you to slouching, screen crowding, and shoulder asymmetry."
)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "calibrate_requested" not in st.session_state:
    st.session_state.calibrate_requested = False

if "calibration_data" not in st.session_state:
    st.session_state.calibration_data = None

if "reset_sedentary" not in st.session_state:
    st.session_state.reset_sedentary = False

if "active_cap" not in st.session_state:
    st.session_state.active_cap = None

# ---------------------------------------------------------
# Sidebar: Controls & Thresholds
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Device & Hardware Engine")
    cam_index = st.number_input("Webcam Index", min_value=0, max_value=5, value=0, step=1)

    target_width = st.selectbox(
        "Processing Resolution",
        options=[640, 854, 1280],
        index=0,
        help="640x480 maintains lowest CPU & RAM footprint (<150MB overhead).",
    )
    target_height = int(target_width * 3 / 4) if target_width == 640 else int(target_width * 9 / 16)

    model_complexity = st.select_slider(
        "MediaPipe Model Complexity",
        options=[0, 1, 2],
        value=1,
        help="0 = Lite, 1 = Full (Recommended), 2 = Heavy",
    )

    st.markdown("---")
    st.header("📏 Biomechanical Limits")

    neck_thresh = st.slider(
        "Neck Inclination Limit (°)",
        min_value=15.0,
        max_value=55.0,
        value=float(DEFAULT_NECK_ANGLE_THRESHOLD),
        step=1.0,
        help="Deviation from vertical before slouching is flagged.",
    )

    proximity_thresh = st.slider(
        "Screen Proximity Limit",
        min_value=0.10,
        max_value=0.45,
        value=float(DEFAULT_PROXIMITY_THRESHOLD),
        step=0.01,
        help="Normalized ear span. Larger means face is closer to webcam.",
    )

    shoulder_thresh = st.slider(
        "Shoulder Asymmetry / Tilt Limit (°)",
        min_value=4.0,
        max_value=25.0,
        value=float(DEFAULT_SHOULDER_TILT_THRESHOLD),
        step=0.5,
        help="Degrees off horizontal level. Catches leaning on one elbow or scoliotic slumping.",
    )

    timeout_seconds = st.slider(
        "Violation Time Before Alarm (s)",
        min_value=3.0,
        max_value=30.0,
        value=float(DEFAULT_VIOLATION_TIMEOUT),
        step=1.0,
        help="Continuous seconds of bad posture required to trigger alarm chime & toast.",
    )

    st.markdown("---")
    st.header("🚶 Workday Health & Sedentary Alarm")
    sedentary_limit = st.slider(
        "Sedentary Sitting Limit (mins)",
        min_value=0.5,
        max_value=120.0,
        value=float(DEFAULT_SEDENTARY_LIMIT_MINUTES),
        step=0.5,
        help="Continuous sitting time before stretch routine triggers. Set to 0.5 min (30 seconds) for rapid testing. Default: 50.0m.",
    )

    if st.button("I Stood Up / Reset Desk Clock", use_container_width=True):
        st.session_state.reset_sedentary = True

    st.markdown("---")
    st.header("🔔 Alert Modes & Privacy")
    enable_toasts = st.toggle("Windows 11 Desktop Toast Alerts", value=True, help="Sends native Windows notifications when coding with browser minimized.")
    avatar_mode = st.toggle("Privacy Wireframe Avatar Mode", value=False, help="Hides raw webcam feed; renders glowing minimalist skeleton on dark canvas.")

    st.markdown("---")
    st.header("🎯 Calibration")
    st.caption("Sit upright at your desk and click Calibrate to set custom baseline geometry.")
    if st.button("Calibrate Good Posture Baseline", use_container_width=True):
        st.session_state.calibrate_requested = True

    if st.session_state.calibration_data:
        cal = st.session_state.calibration_data
        st.success(f"Baseline: {cal['angle']:.1f}° | Prox: {cal['proximity']:.2f} | Tilt: {cal['shoulder']:.1f}°")
        if st.button("Reset Calibration", use_container_width=True):
            st.session_state.calibration_data = None
            st.rerun()

    st.markdown("---")
    run_monitor = st.toggle("Activate Posture Monitor", value=False)

# ---------------------------------------------------------
# UI Layout: Live Feed & Telemetry Dashboard
# ---------------------------------------------------------
col_feed, col_telemetry = st.columns([3, 1])

with col_feed:
    frame_placeholder = st.empty()

with col_telemetry:
    st.subheader("📊 Posture & Health Telemetry")
    status_card = st.empty()

    metric_score = st.empty()
    metric_neck = st.empty()
    metric_shoulder = st.empty()
    metric_prox = st.empty()
    metric_sedentary = st.empty()
    metric_clock = st.empty()
    progress_bar = st.empty()

    status_card.info("Status: System Idle. Toggle 'Activate' in the sidebar to start monitoring.")
    metric_score.metric(label="Session Ergonomic Score", value="100 %", delta="Goal: >85%")
    metric_neck.metric(label="Neck Inclination", value="-- °", delta="Upright")
    metric_shoulder.metric(label="Shoulder Slant", value="-- °", delta="Balanced")
    metric_prox.metric(label="Screen Proximity", value="--", delta="Normal")
    metric_sedentary.metric(label="Continuous Sitting Time", value="0.0 min")
    metric_clock.metric(label="Violation Duration", value="0.0 s")
    progress_bar.progress(0.0)

# ---------------------------------------------------------
# Engine Instantiations
# ---------------------------------------------------------
calculator = ErgonomicCalculator(min_visibility=0.5)
tracker = PostureTracker(
    neck_threshold=neck_thresh,
    proximity_threshold=proximity_thresh,
    shoulder_threshold=shoulder_thresh,
    violation_timeout=timeout_seconds,
    sedentary_limit_minutes=float(sedentary_limit),
)
alert_manager = AlertManager(enable_toasts=enable_toasts)
stretch_guide = StretchGuide()

# Apply stored calibration if available
if st.session_state.calibration_data:
    cal = st.session_state.calibration_data
    tracker.calibrate(cal["angle"], cal["proximity"], cal.get("shoulder", 0.0))

# ---------------------------------------------------------
# Main Frame Processing Loop
# ---------------------------------------------------------
if run_monitor:
    # Ensure any lingering camera handle from previous run is deterministically closed
    if st.session_state.active_cap is not None:
        try:
            st.session_state.active_cap.release()
        except Exception:
            pass
        st.session_state.active_cap = None

    status_card.success("Live Feed: Initializing camera...")

    # Robust hardware capture: try DirectShow first, fall back to default backend
    cap = None
    try:
        cap = cv2.VideoCapture(int(cam_index), cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(int(cam_index))
    except Exception:
        cap = cv2.VideoCapture(int(cam_index))

    if not cap or not cap.isOpened():
        status_card.error(
            f"Cannot connect to webcam at index {cam_index}. "
            "Please ensure your camera is connected and not currently used by another app (e.g. Teams, Zoom, or Windows Hello)."
        )
        st.stop()

    st.session_state.active_cap = cap

    # Safely apply hardware property hints
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(target_width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(target_height))
    except Exception:
        pass

    detector = PoseDetector(model_complexity=model_complexity)
    consecutive_drops = 0

    try:
        while run_monitor:
            if st.session_state.reset_sedentary:
                tracker.reset_sedentary_timer()
                stretch_guide.reset()
                st.session_state.reset_sedentary = False
                st.toast("🚶 Sedentary desk clock reset!")

            success, frame = cap.read()
            if not success:
                consecutive_drops += 1
                time.sleep(0.04)

                # Never call st.warning in a loop; update the single status placeholder instead
                if consecutive_drops == 1:
                    status_card.warning("Re-acquiring camera feed...")
                elif consecutive_drops > 15:
                    status_card.warning("Camera connection stalled. Auto-recovering driver...")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    time.sleep(0.4)
                    cap = cv2.VideoCapture(int(cam_index))
                    st.session_state.active_cap = cap
                    consecutive_drops = 0
                continue

            consecutive_drops = 0

            # 1. Scale down frame immediately for memory conservation
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)

            # 2. Zero-copy optimization for MediaPipe inference
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_rgb.flags.writeable = False

            landmarks = detector.process(frame_rgb)
            frame_rgb.flags.writeable = True

            ear_px, sh_px, bbox_px, l_sh_px, r_sh_px = None, None, None, None, None

            # Handle Privacy Wireframe Avatar Mode
            if avatar_mode:
                render_canvas = np.full(
                    (target_height, target_width, 3), COLOR_AVATAR_BG, dtype=np.uint8
                )
            else:
                render_canvas = frame_rgb

            if landmarks:
                # Draw skeleton connections
                detector.draw_landmarks(render_canvas, landmarks)

                # Extract keypoint coordinates
                keypoints = calculator.extract_keypoints(landmarks, target_width, target_height)

                # 1. Biomechanical Metric: Neck Inclination
                neck_angle, ear_px, sh_px = calculator.calculate_neck_inclination(keypoints)

                # 2. Biomechanical Metric: Screen Proximity
                proximity, bbox_px = calculator.calculate_screen_proximity(keypoints)

                # 3. Biomechanical Metric: Shoulder Asymmetry / Slant
                shoulder_tilt, l_sh_px, r_sh_px = calculator.calculate_shoulder_tilt(keypoints)

                # Handle User Calibration Event
                if st.session_state.calibrate_requested:
                    st.session_state.calibration_data = {
                        "angle": neck_angle,
                        "proximity": proximity,
                        "shoulder": shoulder_tilt,
                    }
                    tracker.calibrate(neck_angle, proximity, shoulder_tilt)
                    st.session_state.calibrate_requested = False
                    st.toast("✅ Baseline Posture Calibrated Successfully!")

                # Update State Machine, Violation Timers & Health Score
                metrics = tracker.update(neck_angle, proximity, shoulder_tilt)

                # Trigger Guided Stretch Routine if sedentary limit reached
                if metrics.is_sedentary_alert and not stretch_guide.is_active:
                    stretch_guide.start()
                    st.toast("🚶 Sedentary limit reached! Stand up and perform the guided stretch.")

                # Branch: Active Interactive Stretch Routine vs Standard Posture HUD
                if stretch_guide.is_active:
                    is_correct, progress, stretch_name, instruction = stretch_guide.update(landmarks)
                    render_canvas = alert_manager.draw_stretch_overlay(
                        render_canvas,
                        stretch_guide,
                        is_correct,
                        progress,
                        stretch_name,
                        instruction,
                    )

                    if is_correct:
                        status_card.success(f"STRETCHING: Holding {stretch_name} ({int(progress * 100)}%)")
                    else:
                        status_card.error(f"🚨 SIREN ACTIVE: Stand up & perform {stretch_name} to silence alarm!")

                    if stretch_guide.is_completed:
                        alert_manager.trigger_success_chime()
                        tracker.reset_sedentary_timer()
                        stretch_guide.reset()
                        st.toast("🎉 Awesome job! You completed the stretch routine. Sitting clock reset!")
                else:
                    # Render Visual HUD, Shoulder Slant Vectors & Audio / Toast Alerts
                    render_canvas = alert_manager.draw_hud(
                        render_canvas, metrics, ear_px, sh_px, bbox_px, l_sh_px, r_sh_px
                    )

                    # Update Streamlit Telemetry Dashboard
                    if metrics.violation_active:
                        status_card.error(f"🚨 {metrics.status_label}")
                    elif metrics.is_slouching or metrics.is_too_close or metrics.is_shoulder_tilted:
                        status_card.warning(f"⚠️ {metrics.status_label}")
                    else:
                        status_card.success("✅ Good Posture Maintained")

                # Health Score Display
                score_color = "normal" if metrics.session_health_score >= 85 else "inverse"
                metric_score.metric(
                    label="Session Ergonomic Score",
                    value=f"{metrics.session_health_score:.1f} %",
                    delta=f"{metrics.total_violations_count} incidents logged",
                    delta_color=score_color,
                )

                neck_delta = f"{neck_angle - tracker.neck_threshold:+.1f}°" if metrics.is_slouching else "Normal"
                metric_neck.metric(
                    label="Neck Inclination",
                    value=f"{neck_angle:.1f} °",
                    delta=neck_delta,
                    delta_color="inverse",
                )

                sh_delta = f"{shoulder_tilt - tracker.shoulder_threshold:+.1f}°" if metrics.is_shoulder_tilted else "Balanced"
                metric_shoulder.metric(
                    label="Shoulder Slant",
                    value=f"{shoulder_tilt:.1f} °",
                    delta=sh_delta,
                    delta_color="inverse",
                )

                prox_delta = f"{proximity - tracker.proximity_threshold:+.2f}" if metrics.is_too_close else "Normal"
                metric_prox.metric(
                    label="Screen Proximity",
                    value=f"{proximity:.2f}",
                    delta=prox_delta,
                    delta_color="inverse",
                )

                metric_sedentary.metric(
                    label="Continuous Sitting Time",
                    value=f"{metrics.sedentary_duration_min:.1f} min",
                    delta="Limit: " + str(sedentary_limit) + "m",
                )

                metric_clock.metric(
                    label="Violation Duration",
                    value=f"{metrics.violation_duration:.1f} s",
                )

                pct = min(1.0, metrics.violation_duration / tracker.violation_timeout)
                progress_bar.progress(pct)

            # Render frame in Streamlit container
            frame_placeholder.image(render_canvas, channels="RGB", use_container_width=True)

            # Prevent CPU thread pegging and allow Streamlit event loop processing
            time.sleep(0.01)

    finally:
        detector.close()
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        st.session_state.active_cap = None
        cv2.destroyAllWindows()
else:
    if st.session_state.active_cap is not None:
        try:
            st.session_state.active_cap.release()
        except Exception:
            pass
        st.session_state.active_cap = None
    status_card.info("Status: Monitor paused. Toggle 'Activate Posture Monitor' to resume.")
