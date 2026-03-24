//
//  WebSocketClient.swift
//  WallHacks
//
//  WebSocket client for receiving pose data from MacBook
//

import Foundation
import Combine

enum WebSocketConnectionState: String {
    case disconnected
    case connecting
    case connected
}

class WebSocketClient: NSObject, ObservableObject {
    // MARK: - Published Properties

    @Published var isConnected: Bool = false
    @Published var latestPoseData: PoseData?
    @Published var renderPoseData: PoseData?
    @Published var connectionError: String?
    @Published var packetsReceived: Int = 0
    @Published var connectionState: WebSocketConnectionState = .disconnected

    // MARK: - Private Properties

    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?
    private let decoder = JSONDecoder()
    private var renderTimer: AnyCancellable?
    private var poseBuffer: [PoseData] = []
    private let interpolationDelaySeconds: Double = 0.08
    private let maxBufferedPoses: Int = 60

    // MARK: - Initialization

    override init() {
        super.init()
        urlSession = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        startRenderLoop()
    }

    // MARK: - Public Methods

    /// Connect to WebSocket server
    /// - Parameter urlString: WebSocket URL (e.g., "ws://192.168.0.232:8765")
    func connect(to urlString: String) {
        guard let url = URL(string: urlString) else {
            connectionError = "Invalid URL"
            connectionState = .disconnected
            return
        }

        disconnect() // Disconnect if already connected

        connectionState = .connecting
        connectionError = nil
        packetsReceived = 0
        poseBuffer = []
        renderPoseData = nil

        webSocketTask = urlSession?.webSocketTask(with: url)
        webSocketTask?.resume()

        // Start receiving messages
        receiveMessage()

        print("WebSocket connecting to: \(urlString)")
    }

    /// Disconnect from WebSocket server
    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
        connectionState = .disconnected
        latestPoseData = nil
        renderPoseData = nil
        poseBuffer = []

        print("WebSocket disconnected")
    }

    /// Send captured alignment heading to the MacBook server.
    /// - Parameter headingRadians: iPhone camera yaw in radians from ARKit.
    func sendAlignmentHeading(_ headingRadians: Float) {
        guard isConnected, let webSocketTask else {
            return
        }

        let payload: [String: Any] = [
            "type": "alignment_heading",
            "heading_radians": Double(headingRadians),
            "timestamp": Date().timeIntervalSince1970
        ]

        guard JSONSerialization.isValidJSONObject(payload) else {
            return
        }

        do {
            let data = try JSONSerialization.data(withJSONObject: payload, options: [])
            guard let text = String(data: data, encoding: .utf8) else {
                return
            }

            webSocketTask.send(.string(text)) { [weak self] error in
                if let error {
                    DispatchQueue.main.async {
                        self?.connectionError = "Failed to send alignment heading: \(error.localizedDescription)"
                    }
                    return
                }

                print("Sent alignment heading: \(headingRadians) rad")
            }
        } catch {
            DispatchQueue.main.async {
                self.connectionError = "Failed to encode alignment heading"
            }
        }
    }

    // MARK: - Private Methods

    /// Recursive receive loop
    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let message):
                self.handleMessage(message)
                self.receiveMessage() // Continue receiving

            case .failure(let error):
                self.handleError(error)
            }
        }
    }

    /// Handle received WebSocket message
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        switch message {
        case .string(let text):
            self.decodeAndPublish(text)

        case .data(let data):
            if let text = String(data: data, encoding: .utf8) {
                self.decodeAndPublish(text)
            }

        @unknown default:
            break
        }
    }

    /// Decode JSON and publish pose data
    private func decodeAndPublish(_ jsonString: String) {
        guard let jsonData = jsonString.data(using: .utf8) else {
            return
        }

        do {
            let poseData = try decoder.decode(PoseData.self, from: jsonData)
            let stampedPoseData = poseData.withReceiveTimestamp(Date().timeIntervalSince1970)

            DispatchQueue.main.async {
                self.latestPoseData = stampedPoseData
                self.poseBuffer.append(stampedPoseData)
                if self.poseBuffer.count > self.maxBufferedPoses {
                    self.poseBuffer.removeFirst(self.poseBuffer.count - self.maxBufferedPoses)
                }
                self.packetsReceived += 1
            }
        } catch {
            print("JSON decode error: \(error)")
            DispatchQueue.main.async {
                self.connectionError = "Invalid data format"
            }
        }
    }

    /// Handle WebSocket error
    private func handleError(_ error: Error) {
        print("WebSocket error: \(error.localizedDescription)")

        DispatchQueue.main.async {
            self.isConnected = false
            self.connectionState = .disconnected
            self.connectionError = error.localizedDescription
            self.renderPoseData = nil
            self.poseBuffer = []
        }
    }

    private func startRenderLoop() {
        renderTimer = Timer.publish(every: 1.0 / 30.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.publishInterpolatedPose()
            }
    }

    private func publishInterpolatedPose() {
        guard !poseBuffer.isEmpty else {
            renderPoseData = nil
            return
        }

        let now = Date().timeIntervalSince1970
        let targetTime = now - interpolationDelaySeconds

        var previousPose: PoseData?
        var nextPose: PoseData?

        for pose in poseBuffer {
            if pose.timestamp <= targetTime {
                previousPose = pose
            }
            if pose.timestamp >= targetTime {
                nextPose = pose
                break
            }
        }

        if let previousPose, let nextPose {
            let timeDelta = nextPose.timestamp - previousPose.timestamp
            if timeDelta <= 0.0001 {
                renderPoseData = nextPose
                return
            }

            let alpha = min(max((targetTime - previousPose.timestamp) / timeDelta, 0.0), 1.0)
            renderPoseData = interpolatePose(from: previousPose, to: nextPose, alpha: alpha)
            return
        }

        renderPoseData = poseBuffer.last
    }

    private func interpolatePose(from previousPose: PoseData, to nextPose: PoseData, alpha: Double) -> PoseData {
        let keypoints = zip(previousPose.keypoints, nextPose.keypoints).map { previousKeypoint, nextKeypoint in
            guard previousKeypoint.id == nextKeypoint.id else {
                return nextKeypoint
            }

            return Keypoint(
                id: previousKeypoint.id,
                name: previousKeypoint.name,
                x: interpolate(previousKeypoint.x, nextKeypoint.x, alpha),
                y: interpolate(previousKeypoint.y, nextKeypoint.y, alpha),
                z: interpolate(previousKeypoint.z, nextKeypoint.z, alpha),
                visibility: interpolate(previousKeypoint.visibility, nextKeypoint.visibility, alpha)
            )
        }

        return PoseData(
            timestamp: interpolate(previousPose.timestamp, nextPose.timestamp, alpha),
            personId: nextPose.personId,
            boundingBox: BoundingBox(
                x: Int(interpolate(Double(previousPose.boundingBox.x), Double(nextPose.boundingBox.x), alpha)),
                y: Int(interpolate(Double(previousPose.boundingBox.y), Double(nextPose.boundingBox.y), alpha)),
                width: Int(interpolate(Double(previousPose.boundingBox.width), Double(nextPose.boundingBox.width), alpha)),
                height: Int(interpolate(Double(previousPose.boundingBox.height), Double(nextPose.boundingBox.height), alpha))
            ),
            keypoints: keypoints,
            heightPixels: interpolate(previousPose.heightPixels, nextPose.heightPixels, alpha),
            confidence: interpolate(previousPose.confidence, nextPose.confidence, alpha),
            sequenceNumber: nextPose.sequenceNumber,
            alignmentHeadingRadians: nextPose.alignmentHeadingRadians,
            serverTimestamp: nextPose.serverTimestamp,
            sentTimestamp: nextPose.sentTimestamp,
            receiveTimestamp: Date().timeIntervalSince1970
        )
    }

    private func interpolate(_ lhs: Double, _ rhs: Double, _ alpha: Double) -> Double {
        lhs + ((rhs - lhs) * alpha)
    }
}

// MARK: - URLSessionWebSocketDelegate

extension WebSocketClient: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async {
            self.isConnected = true
            self.connectionState = .connected
            self.connectionError = nil
            print("WebSocket connected")
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async {
            self.isConnected = false
            self.connectionState = .disconnected
            print("WebSocket closed with code: \(closeCode)")
        }
    }
}
