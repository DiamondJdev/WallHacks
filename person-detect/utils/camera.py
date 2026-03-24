"""Camera capture utility for WallHacks person detection."""

import cv2
from typing import Optional, Tuple
import numpy as np


class Camera:
    """Manages camera initialization and frame capture."""

    def __init__(self, camera_id: int = 0, width: int = 1280, height: int = 720):
        """
        Initialize camera capture.

        Args:
            camera_id: Camera device ID (default 0 for built-in camera)
            width: Frame width in pixels
            height: Frame height in pixels

        Raises:
            RuntimeError: If camera cannot be initialized
        """
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.cap: Optional[cv2.VideoCapture] = None

    def start(self) -> None:
        """Start camera capture."""
        if self.cap is not None:
            return  # Already started

        self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Failed to open camera {self.camera_id}. "
                "Check if camera is available and permissions are granted."
            )

        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # Verify resolution was set
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Camera initialized: {actual_width}x{actual_height}")

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a frame from the camera.

        Returns:
            Tuple of (success, frame) where:
                - success: True if frame was read successfully
                - frame: NumPy array (H, W, 3) in BGR format, or None if failed
        """
        if self.cap is None:
            return False, None

        success, frame = self.cap.read()

        if not success:
            return False, None

        return True, frame

    def stop(self) -> None:
        """Release camera resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            print("Camera released")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False
