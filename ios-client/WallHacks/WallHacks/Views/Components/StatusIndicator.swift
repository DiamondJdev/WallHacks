//
//  StatusIndicator.swift
//  WallHacks
//
//  Shared connection status chip used across Phase 3 pages
//

import SwiftUI

struct StatusIndicator: View {
    let state: WebSocketConnectionState

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(dotColor)
                .frame(width: 10, height: 10)

            Text(label)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundStyle(.primary)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(backgroundColor)
        .cornerRadius(10)
    }

    private var label: String {
        switch state {
        case .disconnected:
            return "Disconnected"
        case .connecting:
            return "Connecting"
        case .connected:
            return "Connected"
        }
    }

    private var dotColor: Color {
        switch state {
        case .disconnected:
            return .gray
        case .connecting:
            return .orange
        case .connected:
            return .green
        }
    }

    private var backgroundColor: Color {
        switch state {
        case .disconnected:
            return Color.gray.opacity(0.15)
        case .connecting:
            return Color.orange.opacity(0.15)
        case .connected:
            return Color.green.opacity(0.15)
        }
    }
}

#Preview {
    VStack {
        StatusIndicator(state: .disconnected)
        StatusIndicator(state: .connecting)
        StatusIndicator(state: .connected)
    }
    .padding()
}
