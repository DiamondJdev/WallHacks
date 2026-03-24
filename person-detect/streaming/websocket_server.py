"""WebSocket server for streaming pose data to clients."""

import asyncio
import json
import logging
import math
from typing import Set, Dict, Any, Optional, Callable
import websockets
from websockets.server import WebSocketServerProtocol


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PoseStreamServer:
    """WebSocket server for broadcasting pose data to connected clients."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        on_alignment_heading: Optional[Callable[[float], None]] = None
    ):
        """
        Initialize the pose streaming server.

        Args:
            host: Host address to bind to (0.0.0.0 for all interfaces)
            port: Port number for WebSocket server
            on_alignment_heading: Callback invoked on alignment updates from client
        """
        self.host = host
        self.port = port
        self.on_alignment_heading = on_alignment_heading
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server: Optional[websockets.WebSocketServer] = None
        self._running = False

    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port
        )

        self._running = True
        logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")

        # Keep server running
        await asyncio.Future()  # Run forever

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        logger.info("Stopping WebSocket server...")
        self._running = False

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all client connections
        for client in list(self.clients):
            await client.close()

        self.clients.clear()
        logger.info("WebSocket server stopped")

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new client connection.

        Args:
            websocket: WebSocket connection from client
        """
        # Add client to set
        self.clients.add(websocket)
        client_address = websocket.remote_address
        logger.info(f"Client connected: {client_address} (Total: {len(self.clients)})")

        try:
            # Keep connection alive and handle incoming messages
            async for message in websocket:
                await self._handle_message(message, websocket)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_address}")

        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")

        finally:
            # Remove client from set
            self.clients.discard(websocket)
            logger.info(f"Client removed: {client_address} (Remaining: {len(self.clients)})")

    async def _handle_message(
        self,
        message: str,
        websocket: WebSocketServerProtocol
    ) -> None:
        """Handle incoming client control messages."""
        client_address = websocket.remote_address

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON message from {client_address}")
            return

        if data.get("type") != "alignment_heading":
            logger.debug(f"Unhandled message type from {client_address}: {data.get('type')}")
            return

        heading = data.get("heading_radians")
        if not isinstance(heading, (int, float)):
            logger.warning(f"Invalid heading payload from {client_address}: {data}")
            return

        heading_value = float(heading)
        if not math.isfinite(heading_value):
            logger.warning(f"Non-finite heading payload from {client_address}: {data}")
            return

        heading_value = math.atan2(math.sin(heading_value), math.cos(heading_value))

        if self.on_alignment_heading is not None:
            self.on_alignment_heading(heading_value)

        logger.info(
            "Received alignment heading %.4f rad (%.2f deg) from %s",
            heading_value,
            heading_value * 180.0 / 3.141592653589793,
            client_address,
        )

    async def broadcast(self, pose_data: Dict[str, Any]) -> None:
        """
        Broadcast pose data to all connected clients.

        Args:
            pose_data: Pose data dictionary (JSON-serializable)
        """
        if not self.clients:
            return  # No clients connected

        # Serialize to JSON
        try:
            message = json.dumps(pose_data)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize pose data: {e}")
            return

        # Send to all clients
        disconnected_clients = set()

        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected_clients.add(client)

        # Remove disconnected clients
        for client in disconnected_clients:
            self.clients.discard(client)
            logger.info(f"Removed disconnected client (Remaining: {len(self.clients)})")

    def get_client_count(self) -> int:
        """
        Get number of connected clients.

        Returns:
            Number of active connections
        """
        return len(self.clients)

    def is_running(self) -> bool:
        """
        Check if server is running.

        Returns:
            True if server is running, False otherwise
        """
        return self._running


# Convenience function for testing
async def test_server():
    """Test the WebSocket server with dummy data."""
    server = PoseStreamServer()

    # Start server in background
    server_task = asyncio.create_task(server.start())

    # Simulate broadcasting data
    for i in range(10):
        await asyncio.sleep(1)
        test_data = {
            "timestamp": i,
            "person_id": 0,
            "test": f"message_{i}"
        }
        await server.broadcast(test_data)
        print(f"Broadcast: {test_data} to {server.get_client_count()} clients")

    await server.stop()


if __name__ == "__main__":
    # Run test server
    asyncio.run(test_server())
