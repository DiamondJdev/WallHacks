"""WallHacks Phase 1 & 2: Person Detection with MediaPipe and Streaming."""

import cv2
import time
import argparse
import asyncio
import threading
from typing import Optional
from utils.camera import Camera
from detection.person_detector import PersonDetector
from detection.pose_processor import PoseProcessor
from detection.visualizer import Visualizer
from streaming.websocket_server import PoseStreamServer


class WallHacksDetector:
    """Main application for person detection and tracking."""

    def __init__(self, enable_streaming: bool = False, host: str = "0.0.0.0", port: int = 8765):
        """
        Initialize the detection system.

        Args:
            enable_streaming: Enable WebSocket streaming mode
            host: WebSocket server host
            port: WebSocket server port
        """
        print("Initializing WallHacks Person Detector...")

        # Initialize components
        self.camera = Camera(camera_id=0, width=1280, height=720)
        self.detector = PersonDetector(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.processor = PoseProcessor(padding_factor=0.1)
        self.visualizer = Visualizer()

        # FPS tracking
        self.fps = 0.0
        self.frame_times = []
        self.max_frame_times = 30  # Average over last 30 frames

        # Streaming setup
        self.enable_streaming = enable_streaming
        self.stream_server: Optional[PoseStreamServer] = None
        self.server_loop: Optional[asyncio.AbstractEventLoop] = None
        self.server_thread: Optional[threading.Thread] = None

        if self.enable_streaming:
            self._start_stream_server(host, port)

        print("Initialization complete!")
        print("\nKeyboard controls:")
        print("  q / ESC - Quit")
        print("  s - Toggle skeleton overlay")
        print("  b - Toggle bounding box")
        print("  k - Toggle keypoint labels")
        print()

    def run(self) -> None:
        """Run the main detection loop."""
        try:
            # Start camera
            self.camera.start()

            # Main processing loop
            while True:
                frame_start_time = time.time()

                # Capture frame
                success, frame = self.camera.read()
                if not success:
                    print("Failed to read frame from camera")
                    break

                # Detect person and extract pose
                pose_landmarks = self.detector.detect(frame)

                if pose_landmarks is not None:
                    # Process pose data
                    pose_data = self.processor.process(
                        pose_landmarks,
                        PersonDetector.LANDMARK_NAMES
                    )

                    # Stream data if enabled
                    if self.enable_streaming and self.stream_server:
                        self._broadcast_pose_data(pose_data)

                    # Visualize
                    frame = self.visualizer.draw(frame, pose_data, self.fps)
                else:
                    # No person detected - just show the frame with message
                    cv2.putText(
                        frame,
                        "No person detected",
                        (20, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 0, 255),
                        2
                    )

                # Display streaming info if enabled
                if self.enable_streaming and self.stream_server:
                    client_count = self.stream_server.get_client_count()
                    cv2.putText(
                        frame,
                        f"Clients: {client_count}",
                        (frame.shape[1] - 200, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                # Display frame
                cv2.imshow("WallHacks - Person Detection", frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q') or key == 27:  # 'q' or ESC
                    print("Quitting...")
                    break
                elif key == ord('s'):
                    self.visualizer.toggle_skeleton()
                    print(f"Skeleton overlay: {'ON' if self.visualizer.show_skeleton else 'OFF'}")
                elif key == ord('b'):
                    self.visualizer.toggle_box()
                    print(f"Bounding box: {'ON' if self.visualizer.show_box else 'OFF'}")
                elif key == ord('k'):
                    self.visualizer.toggle_keypoints()
                    print(f"Keypoint labels: {'ON' if self.visualizer.show_keypoints else 'OFF'}")

                # Update FPS
                frame_time = time.time() - frame_start_time
                self._update_fps(frame_time)

        except KeyboardInterrupt:
            print("\nInterrupted by user")

        except Exception as e:
            print(f"Error during execution: {e}")
            raise

        finally:
            # Cleanup
            self.cleanup()

    def _update_fps(self, frame_time: float) -> None:
        """
        Update FPS calculation.

        Args:
            frame_time: Time taken to process current frame
        """
        self.frame_times.append(frame_time)

        # Keep only last N frame times
        if len(self.frame_times) > self.max_frame_times:
            self.frame_times.pop(0)

        # Calculate average FPS
        if self.frame_times:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            self.fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0.0

    def _start_stream_server(self, host: str, port: int) -> None:
        """
        Start WebSocket streaming server in background thread.

        Args:
            host: Server host address
            port: Server port
        """
        print(f"\nStarting WebSocket server on {host}:{port}...")

        self.stream_server = PoseStreamServer(host=host, port=port)

        # Create new event loop for server thread
        def run_server():
            self.server_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.server_loop)
            self.server_loop.run_until_complete(self.stream_server.start())

        # Start server in background thread
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give server time to start
        time.sleep(1)
        print(f"WebSocket server started at ws://{host}:{port}")

    def _broadcast_pose_data(self, pose_data) -> None:
        """
        Broadcast pose data to WebSocket clients (non-blocking).

        Args:
            pose_data: PoseData object to broadcast
        """
        if not self.server_loop or not self.stream_server:
            return

        # Convert to dictionary
        pose_dict = self.processor.to_dict(pose_data)

        # Schedule broadcast on server's event loop (non-blocking)
        asyncio.run_coroutine_threadsafe(
            self.stream_server.broadcast(pose_dict),
            self.server_loop
        )

    def cleanup(self) -> None:
        """Clean up resources."""
        print("\nCleaning up...")
        self.camera.stop()
        self.detector.close()
        cv2.destroyAllWindows()

        # Stop streaming server if running
        if self.enable_streaming and self.stream_server and self.server_loop:
            print("Stopping WebSocket server...")
            asyncio.run_coroutine_threadsafe(
                self.stream_server.stop(),
                self.server_loop
            )
            time.sleep(0.5)  # Give server time to close gracefully

        print("Cleanup complete")


def main():
    """Entry point for the application."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="WallHacks Person Detection & Streaming")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable WebSocket streaming mode"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="WebSocket server host (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket server port (default: 8765)"
    )
    args = parser.parse_args()

    # Print header
    phase = "Phase 1 & 2: Detection + Streaming" if args.stream else "Phase 1: Person Detection"
    print("=" * 60)
    print(f"WallHacks {phase}")
    print("=" * 60)
    print()

    if args.stream:
        print(f"Streaming enabled: ws://{args.host}:{args.port}")
        print()

    try:
        app = WallHacksDetector(
            enable_streaming=args.stream,
            host=args.host,
            port=args.port
        )
        app.run()

    except RuntimeError as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("- Ensure camera is connected and not in use by another app")
        print("- Check camera permissions in System Preferences")
        return 1

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
