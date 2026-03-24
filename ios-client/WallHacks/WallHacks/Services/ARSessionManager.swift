//
//  ARSessionManager.swift
//  WallHacks
//
//  Phase 3: ARKit session wrapper for continuous tracking
//

import Foundation
import ARKit
import RealityKit
import Combine

/// Manages ARKit session and provides camera transform updates
class ARSessionManager: NSObject, ObservableObject {
    // MARK: - Published Properties

    @Published var currentCameraTransform: simd_float4x4 = matrix_identity_float4x4
    @Published var currentHeading: Float = 0.0  // Yaw angle in radians
    @Published var isSessionRunning: Bool = false
    @Published var sessionError: String?

    // MARK: - Private Properties

    private let arSession: ARSession

    override init() {
        arSession = ARSession()
        super.init()
        arSession.delegate = self
    }

    // MARK: - Session Lifecycle

    /// Start ARKit session with world tracking configuration
    func startSession(resetTracking: Bool = false) {
        if isSessionRunning && !resetTracking {
            return
        }

        print("ARSessionManager: Starting ARKit session")

        let config = ARWorldTrackingConfiguration()
        config.planeDetection = []  // No plane detection needed for Phase 3
        config.worldAlignment = .gravity  // Y-up, gravity-aligned coordinate system

        let runOptions: ARSession.RunOptions = resetTracking
            ? [.resetTracking, .removeExistingAnchors]
            : []

        arSession.run(config, options: runOptions)

        isSessionRunning = true
        sessionError = nil

        print("ARSessionManager: Session started with gravity alignment")
    }

    /// Pause ARKit session
    func stopSession() {
        print("ARSessionManager: Stopping ARKit session")
        arSession.pause()
        isSessionRunning = false
    }

    /// Reset session tracking (useful for re-alignment)
    func resetSession() {
        print("ARSessionManager: Resetting session tracking")
        startSession(resetTracking: true)
    }

    /// Bind shared ARSession to an ARView instance.
    func configure(arView: ARView) {
        arView.session = arSession
    }

    // MARK: - Transform Extraction

    /// Extract current heading (yaw angle) from camera transform
    /// - Returns: Yaw angle in radians (-π to π)
    func getCurrentHeading() -> Float {
        let transform = currentCameraTransform

        // Extract yaw from camera's forward direction (-Z axis in ARKit)
        // atan2 gives angle of forward vector projected onto XZ plane
        let yaw = atan2(-transform.columns.2.x, -transform.columns.2.z)

        return yaw
    }

    /// Extract current camera position in ARKit world space
    /// - Returns: Position as SIMD3<Float> in meters
    func getCurrentPosition() -> SIMD3<Float> {
        return SIMD3(
            currentCameraTransform.columns.3.x,
            currentCameraTransform.columns.3.y,
            currentCameraTransform.columns.3.z
        )
    }

    /// Get camera's forward direction vector (where camera is pointing)
    /// - Returns: Normalized forward vector
    func getForwardDirection() -> SIMD3<Float> {
        let forward = -simd_float3(
            currentCameraTransform.columns.2.x,
            currentCameraTransform.columns.2.y,
            currentCameraTransform.columns.2.z
        )
        return normalize(forward)
    }

    // MARK: - Debugging

    /// Format transform as readable string
    func getTransformDebugString() -> String {
        let pos = getCurrentPosition()
        let heading = getCurrentHeading() * 180.0 / .pi  // Convert to degrees

        return String(format: "Pos: (%.2f, %.2f, %.2f), Heading: %.1f°",
                     pos.x, pos.y, pos.z, heading)
    }
}

// MARK: - ARSessionDelegate

extension ARSessionManager: ARSessionDelegate {
    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        // Update on main thread for SwiftUI bindings
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }

            self.currentCameraTransform = frame.camera.transform
            self.currentHeading = self.getCurrentHeading()
        }
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        DispatchQueue.main.async { [weak self] in
            self?.sessionError = error.localizedDescription
            print("ARSessionManager: Session failed with error: \(error.localizedDescription)")
        }
    }

    func sessionWasInterrupted(_ session: ARSession) {
        DispatchQueue.main.async { [weak self] in
            self?.isSessionRunning = false
            print("ARSessionManager: Session interrupted")
        }
    }

    func sessionInterruptionEnded(_ session: ARSession) {
        DispatchQueue.main.async { [weak self] in
            self?.isSessionRunning = true
            print("ARSessionManager: Session resumed after interruption")
        }
    }
}
