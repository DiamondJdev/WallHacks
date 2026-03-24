"""Process pose landmarks to extract keypoints and bounding boxes."""

import time
from typing import List, Dict, Any
from dataclasses import dataclass
from detection.person_detector import PoseLandmarks


@dataclass(frozen=True)
class BoundingBox:
    """Immutable bounding box representation."""
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class Keypoint:
    """Immutable keypoint representation."""
    id: int
    name: str
    x: float
    y: float
    z: float
    visibility: float


@dataclass(frozen=True)
class PoseData:
    """
    Immutable pose data structure ready for JSON serialization.

    This structure is designed for Phase 2 WebSocket streaming.
    """
    timestamp: float
    person_id: int
    bounding_box: BoundingBox
    keypoints: tuple  # Tuple of Keypoint objects
    height_pixels: float
    confidence: float


class PoseProcessor:
    """Processes pose landmarks into structured data."""

    def __init__(self, padding_factor: float = 0.1):
        """
        Initialize pose processor.

        Args:
            padding_factor: Extra padding around bounding box (0.1 = 10%)
        """
        self.padding_factor = padding_factor

    def process(
        self,
        pose_landmarks: PoseLandmarks,
        landmark_names: List[str]
    ) -> PoseData:
        """
        Process pose landmarks into structured pose data.

        Args:
            pose_landmarks: Raw landmarks from MediaPipe
            landmark_names: List of landmark names (33 items)

        Returns:
            PoseData object with keypoints and bounding box
        """
        timestamp = time.time()
        person_id = 0  # Single person tracking for Phase 1

        # Convert landmarks to keypoints
        keypoints = self._extract_keypoints(
            pose_landmarks,
            landmark_names
        )

        # Calculate bounding box
        bounding_box = self._calculate_bounding_box(keypoints)

        # Calculate person height
        height_pixels = self._calculate_height(keypoints)

        # Calculate average confidence
        confidence = self._calculate_confidence(keypoints)

        return PoseData(
            timestamp=timestamp,
            person_id=person_id,
            bounding_box=bounding_box,
            keypoints=keypoints,
            height_pixels=height_pixels,
            confidence=confidence
        )

    def _extract_keypoints(
        self,
        pose_landmarks: PoseLandmarks,
        landmark_names: List[str]
    ) -> tuple:
        """
        Extract keypoints from MediaPipe landmarks.

        Args:
            pose_landmarks: Raw landmarks from MediaPipe
            landmark_names: List of landmark names

        Returns:
            Tuple of Keypoint objects (immutable)
        """
        keypoints = []

        for idx, landmark in enumerate(pose_landmarks.landmarks):
            # Convert normalized coordinates to pixels
            x = landmark.x * pose_landmarks.image_width
            y = landmark.y * pose_landmarks.image_height
            z = landmark.z  # Relative depth from MediaPipe

            keypoint = Keypoint(
                id=idx,
                name=landmark_names[idx],
                x=x,
                y=y,
                z=z,
                visibility=landmark.visibility
            )
            keypoints.append(keypoint)

        return tuple(keypoints)

    def _calculate_bounding_box(self, keypoints: tuple) -> BoundingBox:
        """
        Calculate bounding box around all visible keypoints.

        Args:
            keypoints: Tuple of Keypoint objects

        Returns:
            BoundingBox object
        """
        # Filter visible keypoints (visibility > 0.5)
        visible_points = [kp for kp in keypoints if kp.visibility > 0.5]

        if not visible_points:
            # Return empty box if no visible points
            return BoundingBox(x=0, y=0, width=0, height=0)

        # Find min/max coordinates
        xs = [kp.x for kp in visible_points]
        ys = [kp.y for kp in visible_points]

        x_min = min(xs)
        x_max = max(xs)
        y_min = min(ys)
        y_max = max(ys)

        # Calculate dimensions
        width = x_max - x_min
        height = y_max - y_min

        # Add padding
        padding_w = width * self.padding_factor
        padding_h = height * self.padding_factor

        x_min = max(0, x_min - padding_w)
        y_min = max(0, y_min - padding_h)
        width = width + (2 * padding_w)
        height = height + (2 * padding_h)

        return BoundingBox(
            x=int(x_min),
            y=int(y_min),
            width=int(width),
            height=int(height)
        )

    def _calculate_height(self, keypoints: tuple) -> float:
        """
        Calculate person height in pixels.

        Uses distance from nose to average of feet.

        Args:
            keypoints: Tuple of Keypoint objects

        Returns:
            Height in pixels
        """
        # Find nose (index 0)
        nose = keypoints[0]

        # Find feet (left_foot_index=31, right_foot_index=32)
        left_foot = keypoints[31]
        right_foot = keypoints[32]

        # Average foot position
        avg_foot_y = (left_foot.y + right_foot.y) / 2

        # Height is vertical distance
        height = abs(avg_foot_y - nose.y)

        return height

    def _calculate_confidence(self, keypoints: tuple) -> float:
        """
        Calculate average confidence across all keypoints.

        Args:
            keypoints: Tuple of Keypoint objects

        Returns:
            Average visibility (0-1)
        """
        if not keypoints:
            return 0.0

        total_visibility = sum(kp.visibility for kp in keypoints)
        return total_visibility / len(keypoints)

    def to_dict(self, pose_data: PoseData) -> Dict[str, Any]:
        """
        Convert PoseData to dictionary for JSON serialization.

        Args:
            pose_data: PoseData object

        Returns:
            Dictionary ready for JSON serialization
        """
        return {
            "timestamp": pose_data.timestamp,
            "person_id": pose_data.person_id,
            "bounding_box": {
                "x": pose_data.bounding_box.x,
                "y": pose_data.bounding_box.y,
                "width": pose_data.bounding_box.width,
                "height": pose_data.bounding_box.height
            },
            "keypoints": [
                {
                    "id": kp.id,
                    "name": kp.name,
                    "x": kp.x,
                    "y": kp.y,
                    "z": kp.z,
                    "visibility": kp.visibility
                }
                for kp in pose_data.keypoints
            ],
            "height_pixels": pose_data.height_pixels,
            "confidence": pose_data.confidence
        }
