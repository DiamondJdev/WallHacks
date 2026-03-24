# WallHacks iOS Client

Phase 2 WebSocket client for receiving pose data from the MacBook detector.

## Requirements

- Xcode 15.0+
- iOS 17.0+ / iPhone running iOS 17+
- macOS device running the Python detection server

## Setup Instructions

### 1. Open in Xcode

```bash
cd ios-client
open WallHacks.xcodeproj  # Once project is created
```

**Or manually create the Xcode project:**

1. Open Xcode
2. Create New Project → iOS → App
3. Product Name: `WallHacks`
4. Interface: SwiftUI
5. Language: Swift
6. Save to: `ios-client/`
7. Add the Swift files to your project:
   - `PoseData.swift`
   - `WebSocketClient.swift`
   - `ContentView.swift`
   - `WallHacksApp.swift`

### 2. Configure Project

1. Select your project in Xcode
2. Go to "Signing & Capabilities"
3. Select your Team
4. Update Bundle Identifier if needed

### 3. Find MacBook IP Address

On your MacBook, run:

```bash
ifconfig en0 | grep "inet " | awk '{print $2}'
```

Example output: `192.168.0.232`

### 4. Start Python Server

On MacBook:

```bash
cd person-detect
source .venv/bin/activate
python3 main.py --stream
```

You should see:

```
Starting WebSocket server on 0.0.0.0:8765...
WebSocket server started at ws://0.0.0.0:8765
```

### 5. Run iPhone App

1. Connect iPhone to Mac via USB or use same Wi-Fi network
2. Select your iPhone as the run destination in Xcode
3. Press Cmd+R to build and run
4. App will launch on your iPhone

### 6. Connect to Server

1. In the app, enter your MacBook's IP in the format:
   ```
   ws://192.168.0.232:8765
   ```
   (Replace with your actual IP)

2. Tap **Connect**

3. Stand in front of MacBook camera

4. Watch pose data stream to your iPhone in real-time!

## Features

### Connection Status
- Green "Connected" indicator when linked to server
- Red "Disconnected" when offline
- Auto-reconnect on network interruption

### Live Metrics
- **Confidence**: Detection confidence (0-100%)
- **Latency**: End-to-end delay in milliseconds
- **Keypoints**: Number of visible pose keypoints
- **Height**: Person height in pixels

### Pose Data Display
- Bounding box coordinates
- Real-time FPS counter (on MacBook)
- Full keypoint list with visibility scores

## Troubleshooting

### "Cannot connect to server"
- Ensure both devices are on the **same Wi-Fi network**
- Verify MacBook IP address is correct
- Check that Python server is running (`--stream` flag)
- macOS may prompt to allow Python network access - click Allow

### "No pose data received"
- Stand in front of MacBook camera
- Ensure good lighting
- Check MacBook terminal for detection status
- Verify connection shows "Connected" in app

### App crashes on launch
- Make sure all 4 Swift files are added to Xcode project
- Check that deployment target is iOS 17.0+
- Clean build folder (Cmd+Shift+K) and rebuild

## Network Configuration

- **Protocol**: WebSocket (ws://)
- **Default Port**: 8765
- **Data Format**: JSON
- **Packet Size**: ~5-7 KB per frame
- **Target FPS**: 30 FPS
- **Bandwidth**: ~150-210 KB/s

## Testing Without Camera

You can test the iOS app with a mock server:

```bash
# Install wscat (WebSocket CLI tool)
npm install -g wscat

# Run mock server
wscat -l 8765
```

Then manually send JSON packets:

```json
{"timestamp":1774365123.456,"person_id":0,"bounding_box":{"x":320,"y":100,"width":480,"height":620},"keypoints":[{"id":0,"name":"nose","x":640.5,"y":240.2,"z":-0.15,"visibility":0.98}],"height_pixels":612.4,"confidence":0.92}
```

## Phase 3 Preview

In Phase 3, this app will be extended with:
- ARKit world tracking
- 3D AR visualization
- LiDAR integration
- ArUco marker calibration

The current UI is minimal for validating data flow. AR features come next!

## Files

- `PoseData.swift` - Swift data models matching Python JSON
- `WebSocketClient.swift` - WebSocket connection manager
- `ContentView.swift` - SwiftUI interface
- `WallHacksApp.swift` - App entry point

## License

Personal/experimental project. Not for production use.
