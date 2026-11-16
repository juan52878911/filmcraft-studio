//! Color: hex ↔ RGB, contraste WCAG (como common.contrast), OKLab y ΔE.

pub type Rgb = (f64, f64, f64);

/// '#FF9900' o 'F90' → (255, 153, 0).
pub fn hex_a_rgb(h: &str) -> Option<Rgb> {
    let h = h.trim().trim_start_matches('#');
    let h: String = if h.len() == 3 { h.chars().flat_map(|c| [c, c]).collect() } else { h.to_string() };
    if h.len() != 6 || !h.is_ascii() {
        return None;
    }
    let p = |i: usize| u8::from_str_radix(&h[i..i + 2], 16).ok().map(|x| x as f64);
    Some((p(0)?, p(2)?, p(4)?))
}

/// RGB 0–255 → '#RRGGBB' en mayúsculas (como common.rgb2hex, redondeo de Python: a par).
pub fn rgb_a_hex(c: Rgb) -> String {
    let f = |x: f64| redondeo_par(x).clamp(0.0, 255.0) as u8;
    format!("#{:02X}{:02X}{:02X}", f(c.0), f(c.1), f(c.2))
}

/// round() de Python: mitad a par.
pub fn redondeo_par(x: f64) -> f64 {
    let r = x.round();
    if (x - x.trunc()).abs() == 0.5 && r % 2.0 != 0.0 { r - x.signum() } else { r }
}

/// ¿Es un '#RRGGBB' exacto (el patrón HEX de ds_validate)?
pub fn es_hex6(s: &str) -> bool {
    s.len() == 7 && s.starts_with('#') && s[1..].chars().all(|c| c.is_ascii_hexdigit())
}

/// Luminancia relativa WCAG 2 con el umbral 0.03928 de common.lum.
pub fn lum(c: Rgb) -> f64 {
    let ch = |c: f64| {
        let c = c / 255.0;
        if c <= 0.03928 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
    };
    0.2126 * ch(c.0) + 0.7152 * ch(c.1) + 0.0722 * ch(c.2)
}

/// Contraste WCAG (1 a 21).
pub fn contraste(a: Rgb, b: Rgb) -> f64 {
    let (la, lb) = (lum(a), lum(b));
    let (hi, lo) = if la >= lb { (la, lb) } else { (lb, la) };
    (hi + 0.05) / (lo + 0.05)
}

fn lin(c: f64) -> f64 {
    let c = c / 255.0;
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}

/// sRGB 0–255 → OKLab.
pub fn oklab(c: Rgb) -> [f64; 3] {
    let (r, g, b) = (lin(c.0), lin(c.1), lin(c.2));
    let l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b).cbrt();
    let m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b).cbrt();
    let s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b).cbrt();
    [
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    ]
}

/// OKLab → sRGB 0–255 (recortado al gamut).
pub fn oklab_a_rgb(c: &[f64; 3]) -> Rgb {
    let l_ = c[0] + 0.3963377774 * c[1] + 0.2158037573 * c[2];
    let m_ = c[0] - 0.1055613458 * c[1] - 0.0638541728 * c[2];
    let s_ = c[0] - 0.0894841775 * c[1] - 1.2914855480 * c[2];
    let (l, m, s) = (l_.powi(3), m_.powi(3), s_.powi(3));
    let r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
    let g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
    let b = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s;
    let f = |x: f64| {
        let x = x.clamp(0.0, 1.0);
        255.0 * if x <= 0.0031308 { 12.92 * x } else { 1.055 * x.powf(1.0 / 2.4) - 0.055 }
    };
    (f(r), f(g), f(b))
}

/// ΔE = 100 × distancia euclídea en OKLab (≈2 apenas se nota; ≥10 es otro color).
pub fn delta_e(a: Rgb, b: Rgb) -> f64 {
    let (x, y) = (oklab(a), oklab(b));
    100.0 * ((x[0] - y[0]).powi(2) + (x[1] - y[1]).powi(2) + (x[2] - y[2]).powi(2)).sqrt()
}

/// HLS y HSV de colorsys (r, g, b en 0–1): (tono 0–1, luz, saturación HLS) y (sat HSV, valor).
pub fn hls(c: Rgb) -> (f64, f64, f64) {
    let (r, g, b) = (c.0 / 255.0, c.1 / 255.0, c.2 / 255.0);
    let (maxc, minc) = (r.max(g).max(b), r.min(g).min(b));
    let l = (minc + maxc) / 2.0;
    if minc == maxc {
        return (0.0, l, 0.0);
    }
    let s = if l <= 0.5 { (maxc - minc) / (maxc + minc) } else { (maxc - minc) / (2.0 - maxc - minc) };
    let (rc, gc, bc) = ((maxc - r) / (maxc - minc), (maxc - g) / (maxc - minc), (maxc - b) / (maxc - minc));
    let h = if r == maxc { bc - gc } else if g == maxc { 2.0 + rc - bc } else { 4.0 + gc - rc };
    ((h / 6.0).rem_euclid(1.0), l, s)
}

pub fn hsv_sv(c: Rgb) -> (f64, f64) {
    let (r, g, b) = (c.0 / 255.0, c.1 / 255.0, c.2 / 255.0);
    let (maxc, minc) = (r.max(g).max(b), r.min(g).min(b));
    if maxc == 0.0 { (0.0, 0.0) } else { ((maxc - minc) / maxc, maxc) }
}

/// Suma compensada (Neumaier), la misma que sum() de Python ≥ 3.12.
pub fn suma(xs: impl IntoIterator<Item = f64>) -> f64 {
    let (mut s, mut c) = (0.0f64, 0.0f64);
    for x in xs {
        let t = s + x;
        c += if s.abs() >= x.abs() { (s - t) + x } else { (x - t) + s };
        s = t;
    }
    s + c
}

/// round(x, n) de Python (sobre el decimal exacto del doble).
pub fn redondear(x: f64, n: usize) -> f64 {
    format!("{x:.n$}").parse().unwrap_or(x)
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn contraste_y_delta() {
        let b = hex_a_rgb("#FFFFFF").unwrap();
        let n = hex_a_rgb("#000").unwrap();
        assert!((contraste(b, n) - 21.0).abs() < 1e-9);
        assert!(delta_e(b, b).abs() < 1e-12);
        assert!(delta_e(b, n) > 99.0);
        assert_eq!(rgb_a_hex((255.0, 153.0, 0.4)), "#FF9900");
        assert!(es_hex6("#a1B2c3") && !es_hex6("#abc") && !es_hex6("a1b2c3x"));
        assert_eq!(redondeo_par(2.5), 2.0);
        assert_eq!(redondeo_par(3.5), 4.0);
        assert_eq!(suma([0.1, 0.2, 0.3]), 0.6);
    }
}
