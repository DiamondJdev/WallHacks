//
//  ARTrackingView.swift
//  WallHacks
//
//  Phase 3 - Page 3: Live AR tracking with relative position updates
//

import SwiftUI
import RealityKit
import Combine

struct ARTrackingView: View {
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var webSocket: WebSocketClient
    @EnvironmentObject var arManager: ARSessionManager

    @State private var currentPoseData: PoseData?
    @State private var personWorldPosition: SIMD3<Float>?
    @State private var relativePosition: SIMD3<Float>?
    private let maxRenderableDistanceMeters: Float = 20.0

    var body: some View {
        ZStack {
            ARTrackingContainer(
                arManager: arManager,
                poseData: currentPoseData,
                laptopWorldPosition: appState.laptopWorldPosition,
                personWorldPosition: personWorldPosition
            )
            .ignoresSafeArea()

            VStack {
                HStack {
                    Button("Re-align") {
                        appState.resetAlignment()
                    }
                    .buttonStyle(.bordered)

                    Spacer()

                    Button("Disconnect") {
                        webSocket.disconnect()
                        arManager.stopSession()
                        appState.reset()
                    }
                    .buttonStyle(.bordered)
                }
                .padding()

                Spacer()

                DebugOverlay(
                    connectionState: webSocket.connectionState,
                    packetsReceived: webSocket.packetsReceived,
                    iphonePosition: arManager.getCurrentPosition(),
                    laptopAnchorPosition: appState.laptopWorldPosition,
                    personPosition: personWorldPosition,
                    relativePosition: relativePosition
                )
                .padding()
            }
        }
        .onAppear {
            arManager.startSession()
        }
        .onReceive(webSocket.$renderPoseData.compactMap { $0 }) { poseData in
            currentPoseData = poseData
            updatePersonPosition(from: poseData)
        }
        .onReceive(arManager.$currentCameraTransform) { _ in
            recalculateRelativePosition()
        }
    }

    private func updatePersonPosition(from poseData: PoseData) {
        guard let laptopWorldPosition = appState.laptopWorldPosition else {
            personWorldPosition = nil
            recalculateRelativePosition()
            return
        }

        let keypointById = Dictionary(uniqueKeysWithValues: poseData.keypoints.map { ($0.id, $0) })

        if let leftHip = keypointById[23],
           let rightHip = keypointById[24],
           leftHip.visibility > 0.5,
           rightHip.visibility > 0.5 {
            let candidateLocalPosition = SIMD3(
                Float((leftHip.x + rightHip.x) / 2.0),
                Float((leftHip.y + rightHip.y) / 2.0),
                Float((leftHip.z + rightHip.z) / 2.0)
            )

            guard simd_length(candidateLocalPosition) <= maxRenderableDistanceMeters else {
                personWorldPosition = nil
                recalculateRelativePosition()
                return
            }

            personWorldPosition = convertLaptopLocalToARWorld(
                candidateLocalPosition,
                laptopWorldPosition: laptopWorldPosition
            )
            recalculateRelativePosition()
            return
        }

        guard let nose = keypointById[0] else {
            return
        }

        let fallbackLocalPosition = SIMD3(Float(nose.x), Float(nose.y), Float(nose.z))
        guard simd_length(fallbackLocalPosition) <= maxRenderableDistanceMeters else {
            personWorldPosition = nil
            recalculateRelativePosition()
            return
        }

        personWorldPosition = convertLaptopLocalToARWorld(
            fallbackLocalPosition,
            laptopWorldPosition: laptopWorldPosition
        )

        recalculateRelativePosition()
    }

    private func convertLaptopLocalToARWorld(
        _ localPosition: SIMD3<Float>,
        laptopWorldPosition: SIMD3<Float>
    ) -> SIMD3<Float> {
        // Laptop pipeline uses +Z forward, while ARKit world forward is -Z.
        let arAlignedLocal = SIMD3<Float>(localPosition.x, localPosition.y, -localPosition.z)
        return laptopWorldPosition + arAlignedLocal
    }

    private func recalculateRelativePosition() {
        guard let personWorldPosition else {
            relativePosition = nil
            return
        }

        let iphonePosition = arManager.getCurrentPosition()
        relativePosition = personWorldPosition - iphonePosition
    }
}

private struct ARTrackingContainer: UIViewRepresentable {
    let arManager: ARSessionManager
    let poseData: PoseData?
    let laptopWorldPosition: SIMD3<Float>?
    let personWorldPosition: SIMD3<Float>?

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> ARView {
        let arView = ARView(frame: .zero)
        arManager.configure(arView: arView)
        context.coordinator.skeletonRenderer = ReducedSkeletonRenderer(arView: arView)

        return arView
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        arManager.configure(arView: uiView)
        context.coordinator.skeletonRenderer?.update(
            with: poseData,
            laptopWorldPosition: laptopWorldPosition,
            fallbackPosition: personWorldPosition
        )
    }

    final class Coordinator {
        var skeletonRenderer: ReducedSkeletonRenderer?
    }
}

private final class ReducedSkeletonRenderer {
    private static let jointIds: [Int] = [
        0,
        11, 12,
        13, 14,
        15, 16,
        23, 24,
        25, 26,
        27, 28
    ]

    private static let bones: [(Int, Int)] = [
        (11, 12),
        (11, 13), (13, 15),
        (12, 14), (14, 16),
        (11, 23), (12, 24),
        (23, 24),
        (23, 25), (25, 27),
        (24, 26), (26, 28),
        (0, 11), (0, 12)
    ]

    private let anchor: AnchorEntity
    private let visibilityThreshold: Double = 0.55
    private let laptopAnchorMarker: ModelEntity
    private var jointEntities: [Int: ModelEntity] = [:]
    private var boneEntities: [String: ModelEntity] = [:]

    init(arView: ARView) {
        anchor = AnchorEntity(world: .zero)
        let markerMesh = MeshResource.generateSphere(radius: 0.08)
        let markerMaterial = SimpleMaterial(color: .red, roughness: 0.2, isMetallic: false)
        laptopAnchorMarker = ModelEntity(mesh: markerMesh, materials: [markerMaterial])
        laptopAnchorMarker.name = "laptop-anchor-marker"
        laptopAnchorMarker.isEnabled = false

        arView.scene.addAnchor(anchor)
        anchor.addChild(laptopAnchorMarker)
        setupEntities()
    }

    func update(with poseData: PoseData?, laptopWorldPosition: SIMD3<Float>?, fallbackPosition: SIMD3<Float>?) {
        guard let poseData, let laptopWorldPosition else {
            laptopAnchorMarker.isEnabled = false
            setAllEntitiesEnabled(false)
            return
        }

        laptopAnchorMarker.position = laptopWorldPosition
        laptopAnchorMarker.isEnabled = true

        let keypointById = Dictionary(uniqueKeysWithValues: poseData.keypoints.map { ($0.id, $0) })
        var resolvedPositions: [Int: SIMD3<Float>] = [:]

        for jointId in Self.jointIds {
            guard let keypoint = keypointById[jointId], keypoint.visibility > visibilityThreshold else {
                jointEntities[jointId]?.isEnabled = false
                continue
            }

            let localPoint = SIMD3<Float>(Float(keypoint.x), Float(keypoint.y), Float(keypoint.z))
            let point = convertLaptopLocalToARWorld(localPoint, laptopWorldPosition: laptopWorldPosition)
            resolvedPositions[jointId] = point

            if let jointEntity = jointEntities[jointId] {
                jointEntity.position = point
                jointEntity.isEnabled = true
            }
        }

        if let fallbackPosition, resolvedPositions[0] == nil {
            if let noseEntity = jointEntities[0] {
                noseEntity.position = fallbackPosition
                noseEntity.isEnabled = true
                resolvedPositions[0] = fallbackPosition
            }
        }

        for (jointA, jointB) in Self.bones {
            let boneKey = Self.boneKey(jointA, jointB)
            guard let boneEntity = boneEntities[boneKey],
                  let pointA = resolvedPositions[jointA],
                  let pointB = resolvedPositions[jointB] else {
                boneEntities[boneKey]?.isEnabled = false
                continue
            }

            updateBone(entity: boneEntity, from: pointA, to: pointB)
        }
    }

    private func setupEntities() {
        let jointMesh = MeshResource.generateSphere(radius: 0.03)
        let boneMesh = MeshResource.generateBox(width: 0.015, height: 0.015, depth: 1.0)
        let jointMaterial = SimpleMaterial(color: .green, roughness: 0.4, isMetallic: false)
        let boneMaterial = SimpleMaterial(color: .cyan, roughness: 0.35, isMetallic: false)

        for jointId in Self.jointIds {
            let joint = ModelEntity(mesh: jointMesh, materials: [jointMaterial])
            joint.isEnabled = false
            jointEntities[jointId] = joint
            anchor.addChild(joint)
        }

        for (jointA, jointB) in Self.bones {
            let key = Self.boneKey(jointA, jointB)
            let bone = ModelEntity(mesh: boneMesh, materials: [boneMaterial])
            bone.isEnabled = false
            boneEntities[key] = bone
            anchor.addChild(bone)
        }
    }

    private func updateBone(entity: ModelEntity, from start: SIMD3<Float>, to end: SIMD3<Float>) {
        let direction = end - start
        let length = simd_length(direction)

        guard length > 0.0001 else {
            entity.isEnabled = false
            return
        }

        entity.position = (start + end) * 0.5
        entity.orientation = simd_quatf(from: SIMD3<Float>(0, 0, 1), to: simd_normalize(direction))
        entity.scale = SIMD3<Float>(1, 1, length)
        entity.isEnabled = true
    }

    private static func boneKey(_ jointA: Int, _ jointB: Int) -> String {
        "\(jointA)-\(jointB)"
    }

    private func convertLaptopLocalToARWorld(
        _ localPosition: SIMD3<Float>,
        laptopWorldPosition: SIMD3<Float>
    ) -> SIMD3<Float> {
        let arAlignedLocal = SIMD3<Float>(localPosition.x, localPosition.y, -localPosition.z)
        return laptopWorldPosition + arAlignedLocal
    }

    private func setAllEntitiesEnabled(_ isEnabled: Bool) {
        jointEntities.values.forEach { $0.isEnabled = isEnabled }
        boneEntities.values.forEach { $0.isEnabled = isEnabled }
    }
}
