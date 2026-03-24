//
//  WebSocketClient.swift
//  WallHacks
//
//  WebSocket client for receiving pose data from MacBook
//

import Foundation
import Combine

class WebSocketClient: NSObject, ObservableObject {
    // MARK: - Published Properties

    @Published var isConnected: Bool = false
    @Published var latestPoseData: PoseData?
    @Published var connectionError: String?
    @Published var packetsReceived: Int = 0

    // MARK: - Private Properties

    private var webSocketTask: URLSessionWebSocketTask?
    private var urlSession: URLSession?
    private let decoder = JSONDecoder()

    // MARK: - Initialization

    override init() {
        super.init()
        urlSession = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
    }

    // MARK: - Public Methods

    /// Connect to WebSocket server
    /// - Parameter urlString: WebSocket URL (e.g., "ws://192.168.0.232:8765")
    func connect(to urlString: String) {
        guard let url = URL(string: urlString) else {
            connectionError = "Invalid URL"
            return
        }

        disconnect() // Disconnect if already connected

        webSocketTask = urlSession?.webSocketTask(with: url)
        webSocketTask?.resume()

        isConnected = true
        connectionError = nil
        packetsReceived = 0

        // Start receiving messages
        receiveMessage()

        print("WebSocket connecting to: \(urlString)")
    }

    /// Disconnect from WebSocket server
    func disconnect() {
        webSocketTask?.cancel(with: .goingAway, reason: nil)
        webSocketTask = nil
        isConnected = false
        latestPoseData = nil

        print("WebSocket disconnected")
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

            DispatchQueue.main.async {
                self.latestPoseData = poseData
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
            self.connectionError = error.localizedDescription

            // Auto-reconnect after 3 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { [weak self] in
                guard let self = self, let task = self.webSocketTask else { return }

                if !self.isConnected {
                    print("Attempting to reconnect...")
                    task.resume()
                    self.receiveMessage()
                }
            }
        }
    }
}

// MARK: - URLSessionWebSocketDelegate

extension WebSocketClient: URLSessionWebSocketDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async {
            self.isConnected = true
            self.connectionError = nil
            print("WebSocket connected")
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async {
            self.isConnected = false
            print("WebSocket closed with code: \(closeCode)")
        }
    }
}
