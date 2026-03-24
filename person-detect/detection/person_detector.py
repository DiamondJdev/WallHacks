"""MediaPipe-based person detection and pose estimation."""

import cv2
import numpy as np
from typing import Optional
from dataclasses import dataclass
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import Image, ImageFormat


@dataclass(frozen=True)
class PoseLandmarks:
    """
    Immutable container for pose landmarks from MediaPipe.

    Attributes:
        landmarks: List of 33 landmark objects from MediaPipe
        image_width: Width of the source image
        image_height: Height of the source image
    """
    landmarks: tuple  # MediaPipe landmark list (made immutable via tuple)
    image_width: int
    image_height: int


class PersonDetector:
    """Detects persons and extracts pose keypoints using MediaPipe."""

    # MediaPipe landmark names (33 total)
    LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index"
    ]

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_path: str = "models/pose_landmarker_lite.task"
    ):
        """
        Initialize MediaPipe Pose detector.

        Args:
            model_complexity: Model complexity (0=lite, 1=full, 2=heavy) - unused in new API
            min_detection_confidence: Minimum confidence for person detection
            min_tracking_confidence: Minimum confidence for landmark tracking
            model_path: Path to the pose landmarker model file
        """
        # Configure PoseLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path)

        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            num_poses=1  # Track single person for Phase 1
        )

        self.detector = vision.PoseLandmarker.create_from_options(options)
        self.frame_timestamp_ms = 0

    def detect(self, frame: np.ndarray) -> Optional[PoseLandmarks]:
        """
        Detect person and extract pose landmarks from frame.

        Args:
            frame: BGR image from OpenCV (H, W, 3)

        Returns:
            PoseLandmarks object if person detected, None otherwise
        """
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Create MediaPipe Image
        mp_image = Image(
            image_format=ImageFormat.SRGB,
            data=rgb_frame
        )

        # Increment timestamp for video mode
        self.frame_timestamp_ms += 33  # ~30 FPS

        # Detect pose landmarks
        detection_result = self.detector.detect_for_video(
            mp_image,
            self.frame_timestamp_ms
        )

        # Check if person was detected
        if not detection_result.pose_landmarks:
            return None

        # Get first person's landmarks (single person tracking)
        landmarks_list = detection_result.pose_landmarks[0]

        # Extract image dimensions
        height, width = frame.shape[:2]

        # Convert landmark list to tuple for immutability
        landmarks_tuple = tuple(landmarks_list)

        return PoseLandmarks(
            landmarks=landmarks_tuple,
            image_width=width,
            image_height=height
        )

    def close(self) -> None:
        """Release MediaPipe resources."""
        if self.detector is not None:
            self.detector.close()
            self.detector = None
            print("MediaPipe detector closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
