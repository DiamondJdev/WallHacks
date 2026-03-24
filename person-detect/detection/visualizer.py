"""Visualization utilities for pose detection."""

import cv2
import numpy as np
from detection.pose_processor import PoseData


class Visualizer:
    """Draws pose visualization overlays on frames."""

    # MediaPipe pose connections (skeleton lines)
    POSE_CONNECTIONS = [
        # Face
        (0, 1), (1, 2), (2, 3), (3, 7),  # Left eye to left ear
        (0, 4), (4, 5), (5, 6), (6, 8),  # Right eye to right ear
        (9, 10),  # Mouth
        # Upper body
        (11, 12),  # Shoulders
        (11, 13), (13, 15),  # Left arm
        (12, 14), (14, 16),  # Right arm
        (15, 17), (15, 19), (15, 21),  # Left hand
        (16, 18), (16, 20), (16, 22),  # Right hand
        # Torso
        (11, 23), (12, 24),  # Shoulders to hips
        (23, 24),  # Hips
        # Legs
        (23, 25), (25, 27),  # Left leg
        (24, 26), (26, 28),  # Right leg
        (27, 29), (27, 31),  # Left foot
        (28, 30), (28, 32),  # Right foot
    ]

    # Colors (BGR format for OpenCV)
    COLOR_LEFT = (0, 255, 0)      # Green for left side
    COLOR_RIGHT = (0, 0, 255)     # Red for right side
    COLOR_CENTER = (255, 255, 0)  # Cyan for center
    COLOR_BOX = (255, 0, 255)     # Magenta for bounding box
    COLOR_TEXT = (255, 255, 255)  # White for text

    def __init__(self):
        """Initialize visualizer."""
        self.show_skeleton = True
        self.show_box = True
        self.show_keypoints = False

    def draw(
        self,
        frame: np.ndarray,
        pose_data: PoseData,
        fps: float
    ) -> np.ndarray:
        """
        Draw visualization overlays on frame.

        Args:
            frame: Input image (will not be modified - immutability)
            pose_data: Pose data to visualize
            fps: Current FPS for display

        Returns:
            New frame with overlays (does not modify input)
        """
        # Create a copy to maintain immutability
        output = frame.copy()

        # Draw skeleton
        if self.show_skeleton:
            output = self._draw_skeleton(output, pose_data)

        # Draw bounding box
        if self.show_box:
            output = self._draw_bounding_box(output, pose_data)

        # Draw keypoint coordinates
        if self.show_keypoints:
            output = self._draw_keypoint_coords(output, pose_data)

        # Draw info overlay
        output = self._draw_info(output, pose_data, fps)

        return output

    def _draw_skeleton(
        self,
        frame: np.ndarray,
        pose_data: PoseData
    ) -> np.ndarray:
        """Draw skeleton connections."""
        keypoints = pose_data.keypoints

        # Draw connections
        for start_idx, end_idx in self.POSE_CONNECTIONS:
            start_kp = keypoints[start_idx]
            end_kp = keypoints[end_idx]

            # Only draw if both keypoints are visible
            if start_kp.visibility > 0.5 and end_kp.visibility > 0.5:
                start_point = (int(start_kp.x), int(start_kp.y))
                end_point = (int(end_kp.x), int(end_kp.y))

                # Choose color based on body side
                color = self._get_connection_color(start_idx, end_idx)

                cv2.line(frame, start_point, end_point, color, 2)

        # Draw keypoint circles
        for kp in keypoints:
            if kp.visibility > 0.5:
                center = (int(kp.x), int(kp.y))
                color = self._get_keypoint_color(kp.id)
                cv2.circle(frame, center, 4, color, -1)
                cv2.circle(frame, center, 4, (0, 0, 0), 1)  # Black outline

        return frame

    def _draw_bounding_box(
        self,
        frame: np.ndarray,
        pose_data: PoseData
    ) -> np.ndarray:
        """Draw bounding box around person."""
        bbox = pose_data.bounding_box

        if bbox.width > 0 and bbox.height > 0:
            top_left = (bbox.x, bbox.y)
            bottom_right = (bbox.x + bbox.width, bbox.y + bbox.height)

            cv2.rectangle(frame, top_left, bottom_right, self.COLOR_BOX, 2)

        return frame

    def _draw_keypoint_coords(
        self,
        frame: np.ndarray,
        pose_data: PoseData
    ) -> np.ndarray:
        """Draw keypoint coordinates as text."""
        for kp in pose_data.keypoints:
            if kp.visibility > 0.5:
                text = f"{kp.name[:3]}"
                position = (int(kp.x) + 5, int(kp.y) - 5)

                cv2.putText(
                    frame,
                    text,
                    position,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.3,
                    self.COLOR_TEXT,
                    1
                )

        return frame

    def _draw_info(
        self,
        frame: np.ndarray,
        pose_data: PoseData,
        fps: float
    ) -> np.ndarray:
        """Draw info overlay (FPS, confidence, etc.)."""
        height = frame.shape[0]

        # Create semi-transparent overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, height - 100), (300, height - 10), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Draw text
        y_offset = height - 80
        line_height = 25

        # FPS
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (20, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            self.COLOR_TEXT,
            2
        )

        # Confidence
        cv2.putText(
            frame,
            f"Confidence: {pose_data.confidence:.2f}",
            (20, y_offset + line_height),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            self.COLOR_TEXT,
            2
        )

        # Height
        cv2.putText(
            frame,
            f"Height: {pose_data.height_pixels:.0f}px",
            (20, y_offset + 2 * line_height),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            self.COLOR_TEXT,
            2
        )

        return frame

    def _get_connection_color(self, start_idx: int, end_idx: int) -> tuple:
        """Get color for a skeleton connection based on body side."""
        # Left side landmarks: 1, 2, 3, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31
        left_landmarks = {1, 2, 3, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31}
        # Right side landmarks: 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32
        right_landmarks = {4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}

        if start_idx in left_landmarks and end_idx in left_landmarks:
            return self.COLOR_LEFT
        elif start_idx in right_landmarks and end_idx in right_landmarks:
            return self.COLOR_RIGHT
        else:
            return self.COLOR_CENTER

    def _get_keypoint_color(self, landmark_id: int) -> tuple:
        """Get color for a keypoint based on body side."""
        left_landmarks = {1, 2, 3, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31}
        right_landmarks = {4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32}

        if landmark_id in left_landmarks:
            return self.COLOR_LEFT
        elif landmark_id in right_landmarks:
            return self.COLOR_RIGHT
        else:
            return self.COLOR_CENTER

    def toggle_skeleton(self) -> None:
        """Toggle skeleton overlay on/off."""
        self.show_skeleton = not self.show_skeleton

    def toggle_box(self) -> None:
        """Toggle bounding box on/off."""
        self.show_box = not self.show_box

    def toggle_keypoints(self) -> None:
        """Toggle keypoint coordinates on/off."""
        self.show_keypoints = not self.show_keypoints
