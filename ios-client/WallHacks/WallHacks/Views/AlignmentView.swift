//
//  AlignmentView.swift
//  WallHacks
//
//  Phase 3 - Page 2: One-time heading alignment capture
//

import SwiftUI
import RealityKit

struct AlignmentView: View {
    @EnvironmentObject var appState: AppStateManager
    @EnvironmentObject var arManager: ARSessionManager
    @EnvironmentObject var webSocket: WebSocketClient

    var body: some View {
        ZStack {
            AlignmentARView(arManager: arManager)
                .ignoresSafeArea()

            VStack(spacing: 16) {
                Text("Align Camera Heading")
                    .font(.title2)
                    .bold()

                Text("Stand beside the MacBook, aim iPhone in the same direction as the MacBook camera, then capture alignment")
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            .padding()
            .background(.ultraThinMaterial)
            .cornerRadius(14)
            .padding(.horizontal)
            .frame(maxHeight: .infinity, alignment: .top)
            .padding(.top, 32)

            Image(systemName: "plus")
                .font(.system(size: 42, weight: .semibold))
                .foregroundStyle(.white)
                .shadow(radius: 8)

            VStack(spacing: 12) {
                Text(appState.isAlignmentSet ? "Alignment captured" : "Alignment not set")
                    .font(.headline)
                    .foregroundStyle(appState.isAlignmentSet ? .green : .orange)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial)
                    .cornerRadius(10)

                Button(action: captureAlignment) {
                    Text("Capture Alignment")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                }
                .buttonStyle(.borderedProminent)

                if appState.isAlignmentSet {
                    Button("Start AR Tracking") {
                        appState.transitionTo(.arTracking(aligned: true))
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.green)
                }

                Button("Back") {
                    appState.transitionTo(.connection)
                }
                .buttonStyle(.bordered)
            }
            .padding()
            .background(.ultraThinMaterial)
            .cornerRadius(14)
            .padding()
            .frame(maxHeight: .infinity, alignment: .bottom)
        }
        .onAppear {
            arManager.startSession()
        }
    }

    private func captureAlignment() {
        let heading = arManager.getCurrentHeading()
        let laptopWorldPosition = arManager.getCurrentPosition()
        appState.captureAlignment(heading: heading, laptopWorldPosition: laptopWorldPosition)
        webSocket.sendAlignmentHeading(heading)
    }
}

private struct AlignmentARView: UIViewRepresentable {
    let arManager: ARSessionManager

    func makeUIView(context: Context) -> ARView {
        let arView = ARView(frame: .zero)
        arManager.configure(arView: arView)
        return arView
    }

    func updateUIView(_ uiView: ARView, context: Context) {
        arManager.configure(arView: uiView)
    }
}
