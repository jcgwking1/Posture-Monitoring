# Real-Time Posture & Ergonomics Monitor

An AI-powered computer vision ergonomics monitor for desk workers. It computes real-time neck inclination angles, monitor proximity, and lateral shoulder asymmetry, alerting the user visually, auditorily, and via native Windows 11 desktop notifications when poor posture is held for more than 10 continuous seconds.

Includes a **4-Step Biomechanical Stretch Routine** with an interactive **Humanoid Demonstration Avatar** and an anti-sedentary siren alarm.

## System Requirements
- **OS**: Windows 11
- **CPU**: Intel Core i5-12450HX or equivalent
- **RAM**: 8GB (optimized with low-memory frame downscaling and zero-copy buffers)
- **Webcam**: Standard 720p or 1080p camera

---

## Quickstart

### Launch with 1-Click
Double-click `run_monitor.bat` in the project folder.

### Or Run via Terminal
```powershell
cd C:\Users\user\OneDrive\Desktop\AI
python -m streamlit run app.py
```

---

## Implemented Features

### 1. Biomechanical Monitoring
- **Neck Inclination (Forward Head / Slouching)**:
  - Vector ear midpoint $\rightarrow$ shoulder midpoint projected against the vertical reference.
- **Screen Proximity (Monitor Crowding)**:
  - Normalized inter-ear Euclidean distance and face bounding box tracking.
- **Shoulder Asymmetry & Lateral Slump**:
  - Horizontal tilt angle between left and right shoulders. Catches resting on one elbow, uneven desk height, or lateral spinal curvature.

### 2. Guided 4-Step Biomechanical Stretch Routine & Humanoid Avatar Demo
When continuous sitting time is reached (default: 50.0m, test: 0.5m / 30s):
- **Side Humanoid Avatar ("HOW TO DO IT")**:
  - A vector-rendered humanoid stick figure displays on the side of the video feed, demonstrating the exact target pose for each exercise.
- **AI Body Pose Verification**:
  - **1/4: Lateral Neck Release**: Measures cervical lateral angle ($>14^\circ$). Hold 4s.
  - **2/4: Overhead Sky Reach**: Verifies both wrists are lifted above head/nose. Hold 4s.
  - **3/4: Chest Opener (Cactus Arms)**: Verifies wrists above shoulders and elbows flared wide apart. Hold 4s.
  - **4/4: Standing Hip Extension**: Verifies user is standing tall with hands placed on hips/waist. Hold 4s.
- **Anti-Sedentary Siren Alarm**:
  - Blasts an aggressive emergency siren (`1800Hz ⇄ 2600Hz`) if you remain seated or do not perform the stretch.
  - The moment you match the target pose, the siren **silences immediately**.
  - Completing all 4 exercises plays an upbeat victory chime and resets your sitting clock.

### 3. Ambient UX & Feedback
- **Windows 11 Native Desktop Toast Notifications**:
  - Always-on-top bottom-right desktop card (`⚠️ Posture Alert!`) so you receive warnings even while coding in full-screen IDEs or Antigravity.
- **Privacy Wireframe Avatar Mode**:
  - Toggle in the sidebar to black out the live webcam background and render a sleek, glowing neon skeletal avatar instead.
