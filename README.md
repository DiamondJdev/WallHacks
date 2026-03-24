# 👁️ Sensor Fusion AR — Project Brief

**Project Name:** Through-Wall AR Person Tracker  
**Version:** 0.3 — MVP (Anchor-Calibrated Relative Tracking)  
**Date:** March 2026  
**Hardware:** MacBook (any model) + iPhone 15 Pro

---

## Overview

A two-device sensor fusion system that detects a person in one room using a MacBook laptop camera, then renders a real-time AR silhouette of that person on an iPhone 15 Pro — as if the user could see through the wall. The system now uses an **anchor-calibrated relative positioning approach**: on launch, the iPhone captures the laptop anchor position and heading, then ARKit tracks the iPhone continuously while the laptop streams the person's keypoints in metric laptop-relative space.

---

## Goals

- Detect and track a person's pose in real time using the MacBook camera
- Stream skeleton/pose data over a local network to an iPhone app at ~30fps
- Render a glowing AR silhouette at the correct relative world position on the iPhone
- Maintain spatial accuracy with **no pre-mapping** — one-time laptop-side calibration on first launch
- Update the silhouette position every frame while the person is in camera view

---

## MVP Status

✅ MVP now working end-to-end with:

- One-time calibration beside the laptop:
  - iPhone captures laptop anchor world position
  - iPhone sends heading to laptop over WebSocket
- Python streams keypoints in metric laptop-relative coordinates
- iOS converts laptop-relative keypoints to AR world coordinates and renders skeleton
- In-app diagnostics:
  - laptop anchor marker in AR scene
  - iPhone/laptop vector + distance readout in debug overlay

---

## Technology Stack

| Component | Technology |
|---|---|
| Person detection | Python + MediaPipe (MacBook) |
| Depth estimation | MediaPipe Z landmarks (free, built-in) or Intel RealSense (optional upgrade) |
| Data transport | WebSocket over local Wi-Fi (JSON pose packets, ~30fps) |
| Spatial tracking | ARKit local session tracking — no world map required |
| Heading alignment | One-time manual calibration beside laptop |
| AR rendering | RealityKit (iPhone) |
| LiDAR usage | iPhone 15 Pro LiDAR — depth masking + faster ARKit init |

---

## Core Concept: Anchor-Calibrated Relative Positioning

The key architectural insight is to capture a single laptop anchor and then stream person coordinates relative to that anchor:

```
Person local position (laptop-relative, meters)
         +
Laptop anchor world position (captured on iPhone)
         =
Person world position for AR rendering
```

ARKit tracks the iPhone's pose in its own local coordinate space from the moment a session starts — no pre-scanning required. The laptop contributes person keypoints in a calibrated metric frame. Combined with the captured laptop anchor, these give stable world placement that updates every frame.

---

## System Architecture

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│           ROOM A             │         │           ROOM B              │
│                              │         │                               │
│  MacBook Camera              │         │  iPhone 15 Pro                │
│  └─> MediaPipe pose detect   │         │  └─> ARKit local tracking     │
│  └─> Extract (x, y, z)       │         │  └─> Continuous pose updates  │
│      keypoints per frame     │         │  └─> LiDAR depth mask         │
│  └─> Apply heading rotation  │────────►│  └─> Receive keypoints [XYZ]  │
│  └─> WebSocket broadcast     │ Wi-Fi   │  └─> Subtract iPhone pose     │
│      ~30fps JSON packets     │         │  └─> Render silhouette        │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## Alignment Process (One-Time Per Session, ~3 Seconds)

No room scanning or persistent map data is needed. A single calibration is performed when the app launches:

1. Stand beside the laptop in Room A
2. Point the iPhone in the same forward direction as the laptop camera
3. Press **"Capture Alignment"** in the app
4. iPhone captures:
  - current ARKit heading
  - current ARKit world position as the laptop anchor
5. iPhone sends heading to the laptop via WebSocket control message
6. Python rotates outgoing keypoints by that heading
7. Move to Room B and start AR tracking

> ⚠️ Re-alignment is only needed if the laptop camera is physically rotated or the iPhone is restarted. Moving around Room B freely does **not** require re-alignment.

---

## Spatial Math

### Step 1 — Person Direction from Laptop Camera

Given a detected keypoint at pixel `(u, v)` in a frame of size `W × H`:

```
Horizontal angle:  θx = atan((u - W/2) / f)
Vertical angle:    θy = atan((v - H/2) / f)
Depth:             d  = from MediaPipe Z estimate (or RealSense)

Person in camera space:
  Xc = d · tan(θx)
  Yc = d · tan(θy)
  Zc = d
```

Where `f` is the camera focal length in pixels (approximated from field-of-view or measured via OpenCV calibration).

### Step 2 — Apply Heading Rotation

Rotate the camera-space vector by the stored heading alignment angle `α` to bring it into ARKit's coordinate space:

```
Xw =  Xc · cos(α) + Zc · sin(α)
Yw =  Yc                           (vertical axis unchanged)
Zw = -Xc · sin(α) + Zc · cos(α)
```

### Step 3 — Convert to AR World Coordinates on iPhone

```
Laptop anchor world position = [Ax, Ay, Az]  (captured during calibration)
Streamed person local point  = [Xw, Yw, Zw]  (laptop-relative)

Render world point = [Ax, Ay, Az] + [Xw, Yw, Zw]
```

RealityKit places entities at this world point, which stays anchored as the iPhone moves.

---

## Data Flow (Per Frame)

```
MediaPipe detects person in camera frame
          │
          ▼
Extract (x, y, z) per keypoint  ← z from MediaPipe built-in depth estimate
          │
          ▼
Convert pixel (u,v) → camera-space [Xc, Yc, Zc]
          │
          ▼
Apply heading rotation matrix → ARKit-space [Xw, Yw, Zw]
          │
          └──── JSON over WebSocket (~30fps) ────►  iPhone receives keypoints
                                                            │
                                                            ▼
                                                 ARKit provides iPhone pose
                                                 (position + orientation)
                                                            │
                                                            ▼
                                                 Compute relative position:
                                                 person_pos − iphone_pos
                                                            │
                                                            ▼
                                                 RealityKit renders silhouette
                                                 anchored at relative point ✓
```

---

## WebSocket Packet Format

Each frame sends a lightweight JSON packet:

```json
{
  "timestamp": 1711234567.891,
  "sequence_number": 1024,
  "coordinate_space": "meters_camera_aligned",
  "estimated_depth_meters": 2.36,
  "keypoints": [
    { "id": 0,  "name": "nose",           "x": 0.12, "y": -0.03, "z": 2.41, "confidence": 0.98 },
    { "id": 11, "name": "left_shoulder",  "x": 0.18, "y": -0.45, "z": 2.38, "confidence": 0.95 },
    { "id": 12, "name": "right_shoulder", "x": 0.07, "y": -0.44, "z": 2.39, "confidence": 0.96 },
    { "id": 23, "name": "left_hip",       "x": 0.17, "y": -0.91, "z": 2.35, "confidence": 0.93 },
    { "id": 24, "name": "right_hip",      "x": 0.08, "y": -0.90, "z": 2.36, "confidence": 0.94 }
  ]
}
```

- `x`, `y`, `z` are in **meters**, expressed in laptop-relative aligned space after heading rotation
- `confidence` gates rendering — keypoints below ~0.6 are skipped
- Full 33-keypoint MediaPipe skeleton is sent; iPhone selects which to render

---

## Depth Estimation Options

Depth accuracy is the primary driver of silhouette placement quality. Options ranked by ease vs. accuracy:

| Method | Accuracy | Cost | Notes |
|---|---|---|---|
| **PnP + MediaPipe landmarks (current MVP)** | ±0.2 – 0.5 m (scene dependent) | Free | Multi-landmark solvePnP with fallback heuristics |
| **MediaPipe Z estimate** | ±0.2 – 0.5 m | Free | Used as fallback cue |
| **Skeleton height heuristic** | ±0.3 – 0.8 m | Free | Compare pixel height to known avg human height (1.7m) |
| **Stereo webcams** | ±0.05 – 0.2 m | ~$0 (2 webcams) | Requires baseline measurement between cameras |
| **Intel RealSense** | ±0.01 – 0.05 m | ~$200 | USB depth camera, highest accuracy upgrade |

**Recommended starting point:** MediaPipe Z — zero setup, already computed as part of pose detection.

---

## Role of LiDAR (iPhone 15 Pro)

LiDAR is not required for the core positioning system, but enhances the experience in two ways:

- **Depth masking** — objects in Room B that are closer to the iPhone than the silhouette distance can occlude/clip the rendering, making the effect more realistic
- **Faster ARKit initialization** — LiDAR accelerates plane detection and session startup, reducing the time before the AR scene is stable

> Note: Full occlusion (silhouette hidden behind furniture in Room B) is a Phase 5 polish feature and not required for a working demo.

---

## Build Phases

### Phase 1 — Person Detection (MacBook) ✅ ./person-detect

- Set up Python environment with MediaPipe and OpenCV
- Detect person and extract pose keypoints from live camera feed
- Visualize skeleton overlay locally to validate detection quality

### Phase 2 — Data Streaming ✅ ./ios-client

- Implement a WebSocket server on the MacBook
- Define JSON packet format (see above)
- Build a basic iPhone receiver app and confirm data arrives correctly

### Phase 3 — ARKit Relative Tracking ✅ ./ios-client

- Build the iPhone ARKit session (local tracking, no world map configuration)
- Implement the heading alignment UI ("Align" button on launch)
- Store alignment angle and apply rotation matrix to incoming keypoints
- Validate that relative positions update correctly as iPhone moves

### Phase 4 — AR Rendering ✅ ./ios-client + ./person-detect

- Render reduced 3D skeleton using RealityKit entities
- Interpolate/smooth incoming packets for stable rendering
- Convert laptop-relative keypoints into AR world coordinates via laptop anchor
- Add diagnostics (anchor marker + vector/distance HUD)

### Phase 5 — LiDAR Integration & Polish

- Enable LiDAR-based depth masking in RealityKit for occlusion
- Tune rendering — glow effect, outline style, opacity, smoothing
- Optimize WebSocket latency and packet rate for lowest lag

---

## Accuracy Expectations

| Scenario | Expected Positional Error |
|---|---|
| PnP + fallback depth, good lighting | ±0.2 – 0.5 m |
| Skeleton height heuristic | ±0.3 – 0.8 m |
| Intel RealSense depth camera | ±0.01 – 0.05 m |
| Heading misaligned by 5° | ~0.2 m lateral drift at 2 m distance |
| iPhone moved freely in Room B | No degradation — ARKit handles it |
| App restarted | 3-second re-alignment, then nominal |

---

## Constraints & Assumptions

- Both devices must be on the **same local Wi-Fi network**
- The MacBook camera is **fixed** after calibration (rotating it requires re-alignment)
- Person is assumed to be **upright** for pose estimation heuristics
- ARKit requires reasonable ambient light in Room B to maintain tracking
- Single person tracking in Phase 1 (multi-person is a future enhancement)
- No line-of-sight required between devices at any point after alignment

---

## Future Enhancements

- Multi-person tracking
- Full LiDAR occlusion — silhouette hidden behind foreground objects in Room B
- UWB positioning upgrade for sub-10cm accuracy (requires anchor hardware)
- Android support via ARCore
- Intel RealSense depth camera integration for higher accuracy
- Automatic heading alignment using compass + shared orientation reference
- Edge-case handling: person partially occluded, low light, camera motion blur

---

## Key Dependencies

**MacBook (Python)**

- `mediapipe` — pose detection + built-in Z depth estimates
- `opencv-python` — camera capture
- `numpy` — coordinate math + rotation matrix
- `websockets` — data streaming

**iPhone (Swift/Xcode)**

- `ARKit` — local session tracking (no world map configuration needed)
- `RealityKit` — AR rendering + LiDAR depth masking
- `simd` — fast vector/matrix math for relative position calculation
- `Network` framework — WebSocket client

---

*This is a personal/experimental project. Not intended for production use.*
