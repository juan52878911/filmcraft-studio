// Caras y personas con Apple Vision (sin modelos descargados).
// Uso: vision_detect IMG1 IMG2 ...  -> una línea JSON por imagen:
// {"path":..., "faces":[[x,y,w,h],...], "people":[[x,y,w,h],...]}  (normalizado 0-1, origen arriba-izquierda)
import Foundation
import Vision
import ImageIO

func rects(_ obs: [VNDetectedObjectObservation]?) -> [[Double]] {
    (obs ?? []).map { o in
        let b = o.boundingBox
        return [Double(b.minX), Double(1 - b.maxY), Double(b.width), Double(b.height)].map { ($0 * 10000).rounded() / 10000 }
    }
}

for path in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        print("{\"path\":\"\(path)\",\"error\":\"no se pudo leer\"}")
        continue
    }
    let faces = VNDetectFaceRectanglesRequest()
    let people = VNDetectHumanRectanglesRequest()
    people.upperBodyOnly = false
    let h = VNImageRequestHandler(cgImage: img, options: [:])
    try? h.perform([faces, people])
    let out: [String: Any] = ["path": path, "faces": rects(faces.results), "people": rects(people.results)]
    if let d = try? JSONSerialization.data(withJSONObject: out), let s = String(data: d, encoding: .utf8) {
        print(s)
    }
}
