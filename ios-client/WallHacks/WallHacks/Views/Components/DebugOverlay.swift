//
//  DebugOverlay.swift
//  WallHacks
//
//  Shared HUD for Phase 3 AR tracking diagnostics
//

import SwiftUI

struct DebugOverlay: View {
    let connectionState: WebSocketConnectionState
    let packetsReceived: Int
    let iphonePosition: SIMD3<Float>
    let laptopAnchorPosition: SIMD3<Float>?
    let personPosition: SIMD3<Float>?
    let relativePosition: SIMD3<Float>?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Circle()
                    .fill(connectionState == .connected ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)

                Text("\(connectionState.rawValue.capitalized) | Packets: \(packetsReceived)")
                    .font(.caption.weight(.semibold))
            }

            Text("iPhone [x y z]: \(format(iphonePosition))")
                .font(.system(.caption, design: .monospaced))

            if let laptopAnchorPosition {
                Text("Laptop anchor [x y z]: \(format(laptopAnchorPosition))")
                    .font(.system(.caption, design: .monospaced))

                let anchorOffset = laptopAnchorPosition - iphonePosition
                Text("iPhone -> laptop: \(format(anchorOffset))")
                    .font(.system(.caption, design: .monospaced))

                Text(String(format: "iPhone-laptop distance: %.2f m", length(anchorOffset)))
                    .font(.system(.caption, design: .monospaced))
            } else {
                Text("Laptop anchor: not captured")
                    .font(.system(.caption, design: .monospaced))
            }

            if let personPosition {
                Text("Person [x y z]: \(format(personPosition))")
                    .font(.system(.caption, design: .monospaced))
            } else {
                Text("Person [x y z]: waiting")
                    .font(.system(.caption, design: .monospaced))
            }

            if let relativePosition {
                Text("Relative [x y z]: \(format(relativePosition))")
                    .font(.system(.caption, design: .monospaced))

                Text(String(format: "Distance: %.2f m", length(relativePosition)))
                    .font(.system(.caption, design: .monospaced))
            } else {
                Text("Distance: --")
                    .font(.system(.caption, design: .monospaced))
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.ultraThinMaterial)
        .cornerRadius(12)
    }

    private func format(_ vector: SIMD3<Float>) -> String {
        String(format: "%.2f %.2f %.2f", vector.x, vector.y, vector.z)
    }

    private func length(_ vector: SIMD3<Float>) -> Float {
        sqrt(
            vector.x * vector.x +
            vector.y * vector.y +
            vector.z * vector.z
        )
    }
}

#Preview {
    DebugOverlay(
        connectionState: .connected,
        packetsReceived: 224,
        iphonePosition: SIMD3(0.24, 1.41, -0.82),
        laptopAnchorPosition: SIMD3(0.00, 1.20, 0.10),
        personPosition: SIMD3(1.20, 0.40, 2.84),
        relativePosition: SIMD3(0.96, -1.01, 3.66)
    )
    .padding()
}
