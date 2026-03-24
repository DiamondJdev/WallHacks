//
//  PoseData.swift
//  WallHacks
//
//  Swift data models matching Python JSON schema
//

import Foundation

// MARK: - Main Pose Data Structure

struct PoseData: Codable {
    let timestamp: Double
    let personId: Int
    let boundingBox: BoundingBox
    let keypoints: [Keypoint]
    let heightPixels: Double
    let confidence: Double

    enum CodingKeys: String, CodingKey {
        case timestamp
        case personId = "person_id"
        case boundingBox = "bounding_box"
        case keypoints
        case heightPixels = "height_pixels"
        case confidence
    }
}

// MARK: - Bounding Box

struct BoundingBox: Codable {
    let x: Int
    let y: Int
    let width: Int
    let height: Int
}

// MARK: - Keypoint

struct Keypoint: Codable, Identifiable {
    let id: Int
    let name: String
    let x: Double
    let y: Double
    let z: Double
    let visibility: Double
}

// MARK: - Helper Extensions

extension PoseData {
    /// Calculate latency from timestamp to now
    var latencyMs: Double {
        let now = Date().timeIntervalSince1970
        return (now - timestamp) * 1000
    }

    /// Get visible keypoints only (visibility > 0.5)
    var visibleKeypoints: [Keypoint] {
        keypoints.filter { $0.visibility > 0.5 }
    }
}

extension Keypoint {
    /// Check if keypoint is visible
    var isVisible: Bool {
        visibility > 0.5
    }
}
