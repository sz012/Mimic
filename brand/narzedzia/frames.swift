import AVFoundation
import AppKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let outDir = CommandLine.arguments[2]
let asset = AVURLAsset(url: url)
let gen = AVAssetImageGenerator(asset: asset)
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
gen.maximumSize = CGSize(width: 960, height: 540)
let times = CommandLine.arguments.count > 3 ? CommandLine.arguments[3].split(separator: ",").map { Double($0)! } : [2.0, 9.0, 16.5, 22.0, 27.3, 29.2, 34.0]
for t in times {
  let img = try! gen.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil)
  let rep = NSBitmapImageRep(cgImage: img)
  try! rep.representation(using: .jpeg, properties: [:])!.write(to: URL(fileURLWithPath: "\(outDir)/f\(t).jpg"))
}
print("ok", CMTimeGetSeconds(asset.duration))
