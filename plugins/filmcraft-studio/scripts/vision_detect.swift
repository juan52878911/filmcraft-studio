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

func emit(_ obj: [String: Any]) {
    // JSON siempre con JSONSerialization (una comilla en la ruta no rompe la línea)
    if let d = try? JSONSerialization.data(withJSONObject: obj), let s = String(data: d, encoding: .utf8) {
        print(s)
    }
}

for path in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        emit(["path": path, "error": "no se pudo leer"])
        continue
    }
    // orientación EXIF: las cajas salen en la imagen tal como se ve
    var orient = CGImagePropertyOrientation.up
    if let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any],
       let o = props[kCGImagePropertyOrientation] as? UInt32, let oo = CGImagePropertyOrientation(rawValue: o) {
        orient = oo
    }
    let faces = VNDetectFaceRectanglesRequest()
    let people = VNDetectHumanRectanglesRequest()
    people.upperBodyOnly = false
    let h = VNImageRequestHandler(cgImage: img, orientation: orient, options: [:])
    do {
        try h.perform([faces, people])
    } catch {
        emit(["path": path, "error": "Vision: \(error.localizedDescription)"])   // no es «sin caras»
        continue
    }
    emit(["path": path, "faces": rects(faces.results), "people": rects(people.results)])
}
