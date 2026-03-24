//
//  ContentView.swift
//  WallHacks
//
//  Phase 2 minimal UI for testing WebSocket data streaming
//

import SwiftUI

struct ContentView: View {
    @StateObject private var webSocketClient = WebSocketClient()
    @State private var serverURL: String = "ws://192.168.0.232:8765"
    @State private var showingKeypoints = false

    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // Connection Section
                connectionSection

                // Status Section
                statusSection

                // Pose Data Section
                if let poseData = webSocketClient.latestPoseData {
                    poseDataSection(poseData)
                } else {
                    noDataSection
                }

                Spacer()
            }
            .padding()
            .navigationTitle("WallHacks")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    // MARK: - Connection Section

    private var connectionSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Server Connection")
                .font(.headline)

            HStack {
                TextField("ws://IP:PORT", text: $serverURL)
                    .textFieldStyle(RoundedBorderTextFieldStyle())
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .disabled(webSocketClient.isConnected)

                Button(action: toggleConnection) {
                    Text(webSocketClient.isConnected ? "Disconnect" : "Connect")
                        .frame(width: 100)
                }
                .buttonStyle(.borderedProminent)
                .tint(webSocketClient.isConnected ? .red : .green)
            }

            if let error = webSocketClient.connectionError {
                Text("Error: \(error)")
                    .font(.caption)
                    .foregroundColor(.red)
            }
        }
    }

    // MARK: - Status Section

    private var statusSection: some View {
        HStack(spacing: 30) {
            StatusCard(
                title: "Connection",
                value: webSocketClient.isConnected ? "Connected" : "Disconnected",
                color: webSocketClient.isConnected ? .green : .gray
            )

            StatusCard(
                title: "Packets",
                value: "\(webSocketClient.packetsReceived)",
                color: .blue
            )
        }
    }

    // MARK: - Pose Data Section

    private func poseDataSection(_ poseData: PoseData) -> some View {
        VStack(alignment: .leading, spacing: 15) {
            Text("Live Pose Data")
                .font(.headline)

            // Metrics Grid
            LazyVGrid(columns: [GridItem(), GridItem()], spacing: 15) {
                MetricCard(title: "Confidence", value: String(format: "%.1f%%", poseData.confidence * 100))
                MetricCard(title: "Latency", value: String(format: "%.0f ms", poseData.latencyMs))
                MetricCard(title: "Keypoints", value: "\(poseData.visibleKeypoints.count)/33")
                MetricCard(title: "Height", value: String(format: "%.0f px", poseData.heightPixels))
            }

            // Bounding Box
            BoundingBoxView(box: poseData.boundingBox)

            // Keypoints Toggle
            Toggle("Show Keypoints", isOn: $showingKeypoints)
                .padding(.top, 10)

            // Keypoints List
            if showingKeypoints {
                KeypointsListView(keypoints: poseData.keypoints)
            }
        }
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(10)
    }

    private var noDataSection: some View {
        VStack(spacing: 10) {
            Image(systemName: "wifi.slash")
                .font(.system(size: 50))
                .foregroundColor(.gray)

            Text("No pose data received")
                .font(.headline)
                .foregroundColor(.gray)

            if webSocketClient.isConnected {
                Text("Waiting for person detection...")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
    }

    // MARK: - Actions

    private func toggleConnection() {
        if webSocketClient.isConnected {
            webSocketClient.disconnect()
        } else {
            webSocketClient.connect(to: serverURL)
        }
    }
}

// MARK: - Supporting Views

struct StatusCard: View {
    let title: String
    let value: String
    let color: Color

    var body: some View {
        VStack {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)

            Text(value)
                .font(.headline)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(8)
    }
}

struct MetricCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)

            Text(value)
                .font(.title3)
                .bold()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.blue.opacity(0.1))
        .cornerRadius(8)
    }
}

struct BoundingBoxView: View {
    let box: BoundingBox

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("Bounding Box")
                .font(.caption)
                .foregroundColor(.secondary)

            Text("X: \(box.x), Y: \(box.y)")
                .font(.system(.body, design: .monospaced))

            Text("W: \(box.width), H: \(box.height)")
                .font(.system(.body, design: .monospaced))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color.green.opacity(0.1))
        .cornerRadius(8)
    }
}

struct KeypointsListView: View {
    let keypoints: [Keypoint]

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 5) {
                ForEach(keypoints) { keypoint in
                    HStack {
                        Circle()
                            .fill(keypoint.isVisible ? Color.green : Color.red)
                            .frame(width: 8, height: 8)

                        Text(keypoint.name)
                            .font(.caption)
                            .frame(width: 120, alignment: .leading)

                        Text(String(format: "(%.0f, %.0f)", keypoint.x, keypoint.y))
                            .font(.system(.caption, design: .monospaced))
                            .foregroundColor(.secondary)

                        Spacer()

                        Text(String(format: "%.2f", keypoint.visibility))
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundColor(keypoint.isVisible ? .green : .red)
                    }
                }
            }
        }
        .frame(maxHeight: 300)
        .padding()
        .background(Color.secondary.opacity(0.05))
        .cornerRadius(8)
    }
}

// MARK: - Preview

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
