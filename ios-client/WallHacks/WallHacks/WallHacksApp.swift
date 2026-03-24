//
//  WallHacksApp.swift
//  WallHacks
//
//  Main app entry point
//

import SwiftUI

@main
struct WallHacksApp: App {
    @StateObject private var appState = AppStateManager()
    @StateObject private var webSocket = WebSocketClient()
    @StateObject private var arSessionManager = ARSessionManager()

    var body: some Scene {
        WindowGroup {
            Group {
                switch appState.currentState {
                case .connection:
                    ConnectionView()

                case .alignment:
                    AlignmentView()

                case .arTracking:
                    ARTrackingView()
                }
            }
            .environmentObject(appState)
            .environmentObject(webSocket)
            .environmentObject(arSessionManager)
        }
    }
}
