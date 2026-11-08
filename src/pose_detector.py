"""
Unified Pose Estimation Module.
Supports both modern MediaPipe Tasks API (Python 3.12/3.13/3.14+) and legacy mp.solutions.pose.
"""

import os
import urllib.request
from typing import List, Optional
import numpy as np
import mediapipe as mp


class PoseDetector:
    """
    Adapter providing consistent pose detection across all MediaPipe versions.
    """

    def __init__(self, model_complexity: int = 1, min_detection_confidence: float = 0.5):
        self.model_complexity = model_complexity
        self.min_confidence = min_detection_confidence
        self.use_legacy = hasattr(mp, "solutions") and hasattr(mp.solutions, "pose")

        if self.use_legacy:
            self.mp_pose = mp.solutions.pose
            self.mp_drawing = mp.solutions.drawing_utils
            self.mp_drawing_styles = mp.solutions.drawing_styles
            self.detector = self.mp_pose.Pose(
                min_detection_confidence=self.min_confidence,
                min_tracking_confidence=0.5,
                model_complexity=self.model_complexity,
                smooth_landmarks=True,
            )
        else:
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            self.vision = vision
            self.drawing_utils = vision.drawing_utils
            self.connections = vision.PoseLandmarksConnections.POSE_LANDMARKS

            # Ensure model asset is downloaded
            model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "models")
            os.makedirs(model_dir, exist_ok=True)

            model_filename = "pose_landmarker_lite.task" if model_complexity == 0 else "pose_landmarker_full.task"
            self.model_path = os.path.join(model_dir, model_filename)

            if not os.path.exists(self.model_path):
                variant = "pose_landmarker_lite" if model_complexity == 0 else "pose_landmarker_full"
                url = f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/{variant}/float16/latest/{variant}.task"
                urllib.request.urlretrieve(url, self.model_path)

            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                output_segmentation_masks=False,
                min_pose_detection_confidence=self.min_confidence,
                min_tracking_confidence=0.5,
                running_mode=vision.RunningMode.IMAGE,
            )
            self.detector = vision.PoseLandmarker.create_from_options(options)

    def process(self, frame_rgb: np.ndarray) -> Optional[List]:
        """
        Runs pose inference on an RGB frame.
        Returns a list of 33 normalized landmarks, or None if no pose is detected.
        """
        if self.use_legacy:
            results = self.detector.process(frame_rgb)
            if results and results.pose_landmarks:
                return results.pose_landmarks.landmark
            return None
        else:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            detection_result = self.detector.detect(mp_image)
            if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                return detection_result.pose_landmarks[0]
            return None

    def draw_landmarks(self, frame_rgb: np.ndarray, landmarks: List):
        """
        Draws skeleton connections and joints on the image.
        """
        if not landmarks:
            return

        if self.use_legacy:
            self.mp_drawing.draw_landmarks(
                frame_rgb,
                landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style(),
            )
        else:
            self.drawing_utils.draw_landmarks(
                image=frame_rgb,
                landmark_list=landmarks,
                connections=self.connections,
                landmark_drawing_spec=self.drawing_utils.DrawingSpec(
                    color=(0, 255, 0), thickness=2, circle_radius=2
                ),
                connection_drawing_spec=self.drawing_utils.DrawingSpec(
                    color=(220, 220, 220), thickness=2, circle_radius=2
                ),
            )

    def close(self):
        """Releases detector resources."""
        if hasattr(self.detector, "close"):
            self.detector.close()
