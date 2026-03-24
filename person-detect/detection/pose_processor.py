"""Process pose landmarks to extract keypoints and bounding boxes."""

import time
import math
import cv2
import numpy as np
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
    sequence_number: int
    bounding_box: BoundingBox
    keypoints: tuple  # Tuple of Keypoint objects
    height_pixels: float
    confidence: float
    alignment_heading_radians: float


class PoseProcessor:
    """Processes pose landmarks into structured data."""

    def __init__(
        self,
        padding_factor: float = 0.1,
        smoothing_factor: float = 0.35,
        camera_horizontal_fov_degrees: float = 69.0,
        camera_vertical_fov_degrees: float = 43.0,
        assumed_person_height_meters: float = 1.7,
        assumed_shoulder_width_meters: float = 0.38,
        relative_depth_scale_meters: float = 1.25,
        min_depth_meters: float = 0.8,
        max_depth_meters: float = 12.0,
        depth_smoothing_alpha: float = 0.25,
        enable_pnp_depth: bool = True,
    ):
        """
        Initialize pose processor.

        Args:
            padding_factor: Extra padding around bounding box (0.1 = 10%)
            smoothing_factor: Exponential smoothing coefficient in [0, 1]
            camera_horizontal_fov_degrees: Estimated webcam horizontal field of view
            camera_vertical_fov_degrees: Estimated webcam vertical field of view
            assumed_person_height_meters: Used to estimate metric depth from pixel height
            assumed_shoulder_width_meters: Used as secondary depth cue from shoulder width
            relative_depth_scale_meters: Scale factor for MediaPipe relative Z contribution
            min_depth_meters: Minimum clamped depth in meters
            max_depth_meters: Maximum clamped depth in meters
            depth_smoothing_alpha: Temporal smoothing for depth estimate in [0, 1]
            enable_pnp_depth: Use solvePnP with body landmarks for better depth estimates
        """
        self.padding_factor = padding_factor
        self.smoothing_factor = max(0.0, min(1.0, smoothing_factor))
        self.camera_horizontal_fov_degrees = camera_horizontal_fov_degrees
        self.camera_vertical_fov_degrees = camera_vertical_fov_degrees
        self.assumed_person_height_meters = assumed_person_height_meters
        self.assumed_shoulder_width_meters = assumed_shoulder_width_meters
        self.relative_depth_scale_meters = relative_depth_scale_meters
        self.min_depth_meters = min_depth_meters
        self.max_depth_meters = max_depth_meters
        self.depth_smoothing_alpha = max(0.0, min(1.0, depth_smoothing_alpha))
        self.enable_pnp_depth = enable_pnp_depth
        self._alignment_heading_radians = 0.0
        self._sequence_number = 0
        self._previous_smoothed_keypoints: Dict[int, Keypoint] = {}
        self._previous_depth_meters: float | None = None
        self._image_width = 1280
        self._image_height = 720
        # Approximate human body model points (meters), origin near hip center.
        self._pnp_body_model_points: Dict[int, tuple[float, float, float]] = {
            0: (0.0, 0.62, 0.03),
            11: (-0.19, 0.44, 0.0),
            12: (0.19, 0.44, 0.0),
            23: (-0.14, 0.0, 0.0),
            24: (0.14, 0.0, 0.0),
            25: (-0.14, -0.42, 0.03),
            26: (0.14, -0.42, 0.03),
            27: (-0.14, -0.90, 0.08),
            28: (0.14, -0.90, 0.08),
        }

    def set_alignment_heading(self, heading_radians: float) -> None:
        """Update heading used for X/Z rotation on outgoing keypoints."""
        if not math.isfinite(heading_radians):
            return

        wrapped_heading = math.atan2(math.sin(heading_radians), math.cos(heading_radians))
        self._alignment_heading_radians = wrapped_heading

    def get_alignment_heading(self) -> float:
        """Get currently applied heading in radians."""
        return self._alignment_heading_radians

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
        sequence_number = self._next_sequence_number()
        self._image_width = pose_landmarks.image_width
        self._image_height = pose_landmarks.image_height

        # Convert landmarks to keypoints
        keypoints = self._extract_keypoints(
            pose_landmarks,
            landmark_names
        )

        smoothed_keypoints = self._smooth_keypoints(keypoints)

        # Calculate bounding box
        bounding_box = self._calculate_bounding_box(smoothed_keypoints)

        # Calculate person height
        height_pixels = self._calculate_height(smoothed_keypoints)

        # Calculate average confidence
        confidence = self._calculate_confidence(smoothed_keypoints)

        return PoseData(
            timestamp=timestamp,
            person_id=person_id,
            sequence_number=sequence_number,
            bounding_box=bounding_box,
            keypoints=smoothed_keypoints,
            height_pixels=height_pixels,
            confidence=confidence,
            alignment_heading_radians=self._alignment_heading_radians,
        )

    def _next_sequence_number(self) -> int:
        self._sequence_number += 1
        return self._sequence_number

    def _apply_heading_rotation_to_metric_keypoints(
        self,
        keypoints: List[Dict[str, float]],
    ) -> List[Dict[str, float]]:
        """Rotate metric X/Z into alignment frame while keeping Y (up) unchanged."""
        alpha = self._alignment_heading_radians
        if alpha == 0.0:
            return keypoints

        cos_a = math.cos(alpha)
        sin_a = math.sin(alpha)
        rotated_keypoints: List[Dict[str, float]] = []

        for keypoint in keypoints:
            x_camera = keypoint["x"]
            z_camera = keypoint["z"]

            x_world = (x_camera * cos_a) + (z_camera * sin_a)
            z_world = (-x_camera * sin_a) + (z_camera * cos_a)

            rotated_keypoints.append({
                "id": keypoint["id"],
                "name": keypoint["name"],
                "x": x_world,
                "y": keypoint["y"],
                "z": z_world,
                "visibility": keypoint["visibility"],
            })

        return rotated_keypoints

    def _estimate_camera_focal_length_px(self) -> float:
        horizontal_fov_radians = math.radians(self.camera_horizontal_fov_degrees)
        return self._image_width / (2.0 * math.tan(horizontal_fov_radians / 2.0))

    def _estimate_camera_focal_length_y_px(self) -> float:
        vertical_fov_radians = math.radians(self.camera_vertical_fov_degrees)
        return self._image_height / (2.0 * math.tan(vertical_fov_radians / 2.0))

    def _estimate_depth_from_height(
        self,
        height_pixels: float,
        focal_length_y_px: float,
    ) -> float | None:
        if height_pixels <= 1.0:
            return None

        return (self.assumed_person_height_meters * focal_length_y_px) / height_pixels

    def _estimate_depth_from_shoulders(
        self,
        keypoints: tuple,
        focal_length_x_px: float,
    ) -> float | None:
        if len(keypoints) <= 12:
            return None

        left_shoulder = keypoints[11]
        right_shoulder = keypoints[12]
        if left_shoulder.visibility < 0.5 or right_shoulder.visibility < 0.5:
            return None

        shoulder_width_pixels = abs(right_shoulder.x - left_shoulder.x)
        if shoulder_width_pixels <= 1.0:
            return None

        return (self.assumed_shoulder_width_meters * focal_length_x_px) / shoulder_width_pixels

    def _estimate_depth_meters(self, keypoints: tuple, height_pixels: float) -> float:
        focal_length_x_px = self._estimate_camera_focal_length_px()
        focal_length_y_px = self._estimate_camera_focal_length_y_px()

        pnp_depth = self._estimate_depth_with_pnp(keypoints, focal_length_x_px, focal_length_y_px)
        if pnp_depth is not None:
            blended_depth = pnp_depth
        else:
            depth_from_height = self._estimate_depth_from_height(height_pixels, focal_length_y_px)
            depth_from_shoulders = self._estimate_depth_from_shoulders(keypoints, focal_length_x_px)

            depth_candidates: list[float] = []
            if depth_from_height is not None:
                depth_candidates.append(depth_from_height)
            if depth_from_shoulders is not None:
                depth_candidates.append(depth_from_shoulders)

            if depth_candidates:
                if len(depth_candidates) == 2:
                    # Height is usually more stable, shoulder width improves depth response.
                    blended_depth = (depth_from_height * 0.65) + (depth_from_shoulders * 0.35)
                else:
                    blended_depth = depth_candidates[0]
            elif self._previous_depth_meters is not None:
                blended_depth = self._previous_depth_meters
            else:
                blended_depth = 2.5

        clamped_depth = max(self.min_depth_meters, min(self.max_depth_meters, blended_depth))

        if self._previous_depth_meters is None:
            smoothed_depth = clamped_depth
        else:
            alpha = self.depth_smoothing_alpha
            smoothed_depth = self._previous_depth_meters + ((clamped_depth - self._previous_depth_meters) * alpha)

        self._previous_depth_meters = smoothed_depth
        return smoothed_depth

    def _estimate_depth_with_pnp(
        self,
        keypoints: tuple,
        focal_length_x_px: float,
        focal_length_y_px: float,
    ) -> float | None:
        """Estimate camera-to-person depth from multi-landmark PnP fit."""
        if not self.enable_pnp_depth:
            return None

        object_points: list[list[float]] = []
        image_points: list[list[float]] = []

        keypoints_by_id = {kp.id: kp for kp in keypoints}
        for landmark_id, model_point in self._pnp_body_model_points.items():
            kp = keypoints_by_id.get(landmark_id)
            if kp is None or kp.visibility < 0.55:
                continue

            object_points.append([model_point[0], model_point[1], model_point[2]])
            image_points.append([kp.x, kp.y])

        if len(object_points) < 4:
            return None

        object_points_np = np.array(object_points, dtype=np.float32)
        image_points_np = np.array(image_points, dtype=np.float32)

        camera_matrix = np.array(
            [
                [focal_length_x_px, 0.0, self._image_width / 2.0],
                [0.0, focal_length_y_px, self._image_height / 2.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        )
        distortion = np.zeros((4, 1), dtype=np.float32)

        success, _rvec, tvec = cv2.solvePnP(
            object_points_np,
            image_points_np,
            camera_matrix,
            distortion,
            flags=cv2.SOLVEPNP_EPNP,
        )

        if not success:
            return None

        depth = float(tvec[2][0])
        if not math.isfinite(depth):
            return None

        # Keep positive forward depth regardless of PnP sign convention from solver.
        return abs(depth)

    def _convert_keypoints_to_metric_space(
        self,
        keypoints: tuple,
        height_pixels: float,
    ) -> List[Dict[str, float]]:
        focal_length_x_px = self._estimate_camera_focal_length_px()
        focal_length_y_px = self._estimate_camera_focal_length_y_px()
        depth_meters = self._estimate_depth_meters(keypoints, height_pixels)
        center_x = self._image_width / 2.0
        center_y = self._image_height / 2.0

        metric_keypoints: List[Dict[str, float]] = []

        for keypoint in keypoints:
            metric_z = depth_meters + (keypoint.z * self.relative_depth_scale_meters)
            metric_z = max(self.min_depth_meters, min(self.max_depth_meters, metric_z))

            metric_x = ((keypoint.x - center_x) / focal_length_x_px) * metric_z
            metric_y = ((center_y - keypoint.y) / focal_length_y_px) * metric_z

            metric_keypoints.append({
                "id": keypoint.id,
                "name": keypoint.name,
                "x": metric_x,
                "y": metric_y,
                "z": metric_z,
                "visibility": keypoint.visibility,
            })

        return metric_keypoints

    def _smooth_keypoints(self, keypoints: tuple) -> tuple:
        """Apply exponential smoothing to reduce frame-to-frame jitter."""
        if not keypoints:
            self._previous_smoothed_keypoints = {}
            return keypoints

        alpha = self.smoothing_factor
        if alpha <= 0.0:
            self._previous_smoothed_keypoints = {kp.id: kp for kp in keypoints}
            return keypoints

        smoothed_keypoints: list[Keypoint] = []
        next_previous: Dict[int, Keypoint] = {}

        for keypoint in keypoints:
            previous = self._previous_smoothed_keypoints.get(keypoint.id)
            if previous is None:
                smoothed = keypoint
            else:
                smoothed = Keypoint(
                    id=keypoint.id,
                    name=keypoint.name,
                    x=self._lerp(previous.x, keypoint.x, alpha),
                    y=self._lerp(previous.y, keypoint.y, alpha),
                    z=self._lerp(previous.z, keypoint.z, alpha),
                    visibility=self._lerp(previous.visibility, keypoint.visibility, alpha),
                )

            smoothed_keypoints.append(smoothed)
            next_previous[smoothed.id] = smoothed

        self._previous_smoothed_keypoints = next_previous
        return tuple(smoothed_keypoints)

    def _lerp(self, previous_value: float, next_value: float, alpha: float) -> float:
        return previous_value + ((next_value - previous_value) * alpha)

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
        serialized_at = time.time()
        metric_keypoints = self._convert_keypoints_to_metric_space(
            pose_data.keypoints,
            pose_data.height_pixels,
        )
        aligned_metric_keypoints = self._apply_heading_rotation_to_metric_keypoints(metric_keypoints)
        root_depth_meters = self._previous_depth_meters if self._previous_depth_meters is not None else 0.0

        return {
            "timestamp": pose_data.timestamp,
            "person_id": pose_data.person_id,
            "sequence_number": pose_data.sequence_number,
            "alignment_heading_radians": pose_data.alignment_heading_radians,
            "coordinate_space": "meters_camera_aligned",
            "estimated_depth_meters": root_depth_meters,
            "server_timestamp": serialized_at,
            "sent_timestamp": serialized_at,
            "bounding_box": {
                "x": pose_data.bounding_box.x,
                "y": pose_data.bounding_box.y,
                "width": pose_data.bounding_box.width,
                "height": pose_data.bounding_box.height
            },
            "keypoints": [
                {
                    "id": kp["id"],
                    "name": kp["name"],
                    "x": kp["x"],
                    "y": kp["y"],
                    "z": kp["z"],
                    "visibility": kp["visibility"]
                }
                for kp in aligned_metric_keypoints
            ],
            "height_pixels": pose_data.height_pixels,
            "confidence": pose_data.confidence
        }
