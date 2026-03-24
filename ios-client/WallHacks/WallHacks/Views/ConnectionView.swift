//
//  ConnectionView.swift
//  WallHacks
//
//  Phase 3 - Page 1: WebSocket connection setup
//

import SwiftUI

struct ConnectionView: View {
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var webSocket: WebSocketClient

    @State private var serverURL = "ws://192.168.0.232:8765"

    var body: some View {
        VStack(spacing: 40) {
            Spacer()

            // App Icon/Logo
            Image(systemName: "wifi.circle.fill")
                .font(.system(size: 100))
                .foregroundColor(.blue)
                .symbolRenderingMode(.hierarchical)

            // Title
            VStack(spacing: 10) {
                Text("WallHacks - Setup")
                    .font(.largeTitle)
                    .bold()

                Text("Connect to your MacBook pose stream")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Connection Form
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Server Address")
                        .font(.headline)

                    TextField("ws://IP:PORT", text: $serverURL)
                        .textFieldStyle(.roundedBorder)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        .disabled(webSocket.connectionState == .connecting || webSocket.isConnected)
                        .keyboardType(.URL)
                }

                StatusIndicator(state: webSocket.connectionState)

                // Connection Button
                Button(action: connect) {
                    HStack {
                        if webSocket.connectionState == .connecting {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        } else {
                            Image(systemName: webSocket.isConnected ? "checkmark.circle.fill" : "antenna.radiowaves.left.and.right")
                        }

                        Text(buttonText)
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(buttonColor)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                }
                .disabled(webSocket.connectionState == .connecting || webSocket.isConnected)

                // Error Message
                if let error = webSocket.connectionError {
                    HStack(spacing: 8) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundColor(.orange)

                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                }

                // Connection Info
                if webSocket.isConnected {
                    VStack(spacing: 12) {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)

                            Text("Successfully connected")
                                .font(.subheadline)
                                .foregroundColor(.green)

                            Spacer()

                            Text("\(webSocket.packetsReceived) packets")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding()
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(8)

                        // Continue Button
                        Button {
                            appState.transitionTo(.alignment(connected: true))
                        } label: {
                            HStack {
                                Text("Continue to Alignment")
                                    .fontWeight(.semibold)

                                Image(systemName: "arrow.right.circle.fill")
                            }
                            .frame(maxWidth: .infinity)
                            .padding()
                            .background(Color.green)
                            .foregroundColor(.white)
                            .cornerRadius(12)
                        }
                    }
                }
            }
            .padding(.horizontal)

            Spacer()
        }
        .padding()
    }

    // MARK: - Actions

    private var buttonText: String {
        switch webSocket.connectionState {
        case .disconnected:
            return "Connect"
        case .connecting:
            return "Connecting..."
        case .connected:
            return "Connected"
        }
    }

    private var buttonColor: Color {
        switch webSocket.connectionState {
        case .disconnected:
            return .blue
        case .connecting:
            return .orange
        case .connected:
            return .green
        }
    }

    private func connect() {
        webSocket.connect(to: serverURL)
    }
}

// MARK: - Preview

#Preview {
    ConnectionView()
        .environmentObject(AppStateManager())
        .environmentObject(WebSocketClient())
}
