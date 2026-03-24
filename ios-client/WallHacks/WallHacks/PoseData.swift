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
    let sequenceNumber: Int?
    let alignmentHeadingRadians: Double?
    let serverTimestamp: Double?
    let sentTimestamp: Double?
    let receiveTimestamp: Double?

    enum CodingKeys: String, CodingKey {
        case timestamp
        case personId = "person_id"
        case boundingBox = "bounding_box"
        case keypoints
        case heightPixels = "height_pixels"
        case confidence
        case sequenceNumber = "sequence_number"
        case alignmentHeadingRadians = "alignment_heading_radians"
        case serverTimestamp = "server_timestamp"
        case sentTimestamp = "sent_timestamp"
        case receiveTimestamp = "receive_timestamp"
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
    /// Return a copy with local receive timestamp set.
    func withReceiveTimestamp(_ receiveTimestamp: Double) -> PoseData {
        PoseData(
            timestamp: timestamp,
            personId: personId,
            boundingBox: boundingBox,
            keypoints: keypoints,
            heightPixels: heightPixels,
            confidence: confidence,
            sequenceNumber: sequenceNumber,
            alignmentHeadingRadians: alignmentHeadingRadians,
            serverTimestamp: serverTimestamp,
            sentTimestamp: sentTimestamp,
            receiveTimestamp: receiveTimestamp
        )
    }

    /// Calculate latency from timestamp to now
    var latencyMs: Double {
        let now = Date().timeIntervalSince1970
        let baseline = sentTimestamp ?? serverTimestamp ?? timestamp
        return (now - baseline) * 1000
    }

    /// Get visible keypoints only (visibility > 0.5)
    var visibleKeypoints: [Keypoint] {
        keypoints.filter { $0.visibility > 0.5 }
    }

    var effectiveSequenceNumber: Int {
        sequenceNumber ?? -1
    }
}

extension Keypoint {
    /// Check if keypoint is visible
    var isVisible: Bool {
        visibility > 0.5
    }
}
