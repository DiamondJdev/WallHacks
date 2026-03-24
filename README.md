# 👁️ Sensor Fusion AR — Project Brief

**Project Name:** Through-Wall AR Person Tracker  
**Version:** 0.2 — Relative Positioning Architecture  
**Date:** March 2026  
**Hardware:** MacBook (any model) + iPhone 15 Pro

---

## Overview

A two-device sensor fusion system that detects a person in one room using a MacBook laptop camera, then renders a real-time AR silhouette of that person on an iPhone 15 Pro — as if the user could see through the wall. The system uses a **relative positioning approach**: rather than pre-mapping the environment, the iPhone tracks its own pose continuously via ARKit, and the laptop streams the person's position as a direction vector + depth estimate every frame. No room scanning, no anchor maps, and no persistent calibration data is required.

---

## Goals

- Detect and track a person's pose in real time using the MacBook camera
- Stream skeleton/pose data over a local network to an iPhone app at ~30fps
- Render a glowing AR silhouette at the correct relative world position on the iPhone
- Maintain spatial accuracy with **no pre-mapping** — only a 3-second heading alignment on first launch
- Update the silhouette position every frame while the person is in camera view

---

## Technology Stack

| Component | Technology |
|---|---|
| Person detection | Python + MediaPipe (MacBook) |
| Depth estimation | MediaPipe Z landmarks (free, built-in) or Intel RealSense (optional upgrade) |
| Data transport | WebSocket over local Wi-Fi (JSON pose packets, ~30fps) |
| Spatial tracking | ARKit local session tracking — no world map required |
| Heading alignment | One-time manual alignment on app launch (~3 seconds) |
| AR rendering | RealityKit (iPhone) |
| LiDAR usage | iPhone 15 Pro LiDAR — depth masking + faster ARKit init |

---

## Core Concept: Relative Positioning

The key architectural insight is that **absolute world coordinates are not needed**. Instead, every frame computes:

```
Person world position  (laptop camera + depth estimate)
         −
iPhone world position  (ARKit continuous tracking)
         =
Direction vector from iPhone to person  →  render silhouette here
```

ARKit tracks the iPhone's pose in its own local coordinate space from the moment a session starts — no pre-scanning required. The laptop contributes a direction + distance to the person. Combined, these give a precise relative position that updates every frame.

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

No room scanning or persistent map data is needed. A single heading alignment is performed when the app launches:

1. Point the iPhone camera toward the wall separating the two rooms (toward Room A)
2. Press **"Align"** in the app
3. The app records ARKit's current heading as the reference forward direction
4. The laptop camera's forward axis is mathematically mapped to that heading
5. Alignment is complete — the session is live

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

### Step 3 — Render on iPhone

```
Silhouette position = [Xw, Yw, Zw]  (received via WebSocket)
iPhone pose         = ARKit simdWorldTransform (updated every frame)

Final render point  = Silhouette position − iPhone position
                      (expressed in ARKit local space)
```

RealityKit places a 3D entity at this point, which automatically stays anchored in space as the iPhone moves.

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
  "depth_method": "mediapipe_z",
  "keypoints": [
    { "id": 0,  "name": "nose",           "x": 0.12, "y": -0.03, "z": 2.41, "confidence": 0.98 },
    { "id": 11, "name": "left_shoulder",  "x": 0.18, "y": -0.45, "z": 2.38, "confidence": 0.95 },
    { "id": 12, "name": "right_shoulder", "x": 0.07, "y": -0.44, "z": 2.39, "confidence": 0.96 },
    { "id": 23, "name": "left_hip",       "x": 0.17, "y": -0.91, "z": 2.35, "confidence": 0.93 },
    { "id": 24, "name": "right_hip",      "x": 0.08, "y": -0.90, "z": 2.36, "confidence": 0.94 }
  ]
}
```

- `x`, `y`, `z` are in **meters**, expressed in ARKit-aligned world space after heading rotation
- `confidence` gates rendering — keypoints below ~0.6 are skipped
- Full 33-keypoint MediaPipe skeleton is sent; iPhone selects which to render

---

## Depth Estimation Options

Depth accuracy is the primary driver of silhouette placement quality. Options ranked by ease vs. accuracy:

| Method | Accuracy | Cost | Notes |
|---|---|---|---|
| **MediaPipe Z estimate** | ±0.2 – 0.5 m | Free | Built into pose landmarks, best starting point |
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

### Phase 3 — ARKit Relative Tracking ← Current

- Build the iPhone ARKit session (local tracking, no world map configuration)
- Implement the heading alignment UI ("Align" button on launch)
- Store alignment angle and apply rotation matrix to incoming keypoints
- Validate that relative positions update correctly as iPhone moves

### Phase 4 — AR Rendering

- Render a basic 3D skeleton or silhouette using RealityKit entities
- Connect keypoint positions to entity transforms, updated every frame
- Validate that the silhouette stays anchored in space during iPhone movement

### Phase 5 — LiDAR Integration & Polish

- Enable LiDAR-based depth masking in RealityKit for occlusion
- Tune rendering — glow effect, outline style, opacity, smoothing
- Optimize WebSocket latency and packet rate for lowest lag

---

## Accuracy Expectations

| Scenario | Expected Positional Error |
|---|---|
| MediaPipe Z depth, good lighting | ±0.2 – 0.5 m |
| Skeleton height heuristic | ±0.3 – 0.8 m |
| Intel RealSense depth camera | ±0.01 – 0.05 m |
| Heading misaligned by 5° | ~0.2 m lateral drift at 2 m distance |
| iPhone moved freely in Room B | No degradation — ARKit handles it |
| App restarted | 3-second re-alignment, then nominal |

---

## Constraints & Assumptions

- Both devices must be on the **same local Wi-Fi network**
- The MacBook camera is **fixed** after alignment (rotating it requires re-alignment)
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
