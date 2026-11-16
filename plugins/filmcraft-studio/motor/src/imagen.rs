//! Imágenes: carga PNG/JPEG, reducción por promedio de cajas, recorte de la franja con color (como
//! ds_from_image.autocrop), paleta por k-means determinista en OKLab y roles de color de un flyer.
use crate::color::{hls, hsv_sv, oklab, oklab_a_rgb, rgb_a_hex, Rgb};
use serde_json::{json, Value};

pub struct Imagen {
    pub w: usize,
    pub h: usize,
    pub rgb: Vec<[u8; 3]>,
}

pub fn cargar(ruta: &str) -> Result<Imagen, String> {
    let b = std::fs::read(ruta).map_err(|e| format!("{ruta}: {e}"))?;
    if b.starts_with(&[0xFF, 0xD8]) {
        let mut d = jpeg_decoder::Decoder::new(std::io::Cursor::new(&b));
        let px = d.decode().map_err(|e| format!("{ruta}: {e}"))?;
        let info = d.info().ok_or(format!("{ruta}: JPEG sin cabecera"))?;
        let (w, h) = (info.width as usize, info.height as usize);
        let rgb = match info.pixel_format {
            jpeg_decoder::PixelFormat::RGB24 => px.chunks_exact(3).map(|p| [p[0], p[1], p[2]]).collect(),
            jpeg_decoder::PixelFormat::L8 => px.iter().map(|&p| [p; 3]).collect(),
            jpeg_decoder::PixelFormat::L16 => px.chunks_exact(2).map(|p| [p[0]; 3]).collect(),
            jpeg_decoder::PixelFormat::CMYK32 => px.chunks_exact(4).map(|p| {
                let k = 255.0 - p[3] as f64;
                let f = |c: u8| ((255.0 - c as f64) * k / 255.0).round() as u8;
                [f(p[0]), f(p[1]), f(p[2])]
            }).collect(),
        };
        return Ok(Imagen { w, h, rgb });
    }
    let mut dec = png::Decoder::new(std::io::Cursor::new(&b));
    dec.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut lector = dec.read_info().map_err(|e| format!("{ruta}: {e}"))?;
    let mut buf = vec![0; lector.output_buffer_size()];
    let info = lector.next_frame(&mut buf).map_err(|e| format!("{ruta}: {e}"))?;
    let (w, h) = (info.width as usize, info.height as usize);
    let canales = match info.color_type {
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        png::ColorType::Grayscale => 1,
        png::ColorType::GrayscaleAlpha => 2,
        png::ColorType::Indexed => return Err(format!("{ruta}: PNG indexado sin expandir")),
    };
    let rgb = buf[..info.buffer_size()].chunks_exact(canales).map(|p| match canales { 1 | 2 => [p[0]; 3], _ => [p[0], p[1], p[2]] }).collect();
    Ok(Imagen { w, h, rgb })
}

impl Imagen {
    pub fn recortar(&self, y0: usize, y1: usize) -> Imagen {
        Imagen { w: self.w, h: y1 - y0, rgb: self.rgb[y0 * self.w..y1 * self.w].to_vec() }
    }

    /// Reduce a un lado mayor ≤ `lado` con promedio de cajas (sin interpolar entre colores lejanos).
    pub fn reducir(&self, lado: usize) -> Imagen {
        let f = (self.w.max(self.h) as f64 / lado as f64).max(1.0);
        if f <= 1.0 { return Imagen { w: self.w, h: self.h, rgb: self.rgb.clone() } }
        let (nw, nh) = (((self.w as f64 / f).round() as usize).max(1), ((self.h as f64 / f).round() as usize).max(1));
        let mut out = Vec::with_capacity(nw * nh);
        for y in 0..nh {
            let (ya, yb) = (y * self.h / nh, ((y + 1) * self.h / nh).max(y * self.h / nh + 1));
            for x in 0..nw {
                let (xa, xb) = (x * self.w / nw, ((x + 1) * self.w / nw).max(x * self.w / nw + 1));
                let mut s = [0u64; 3];
                for yy in ya..yb {
                    for p in &self.rgb[yy * self.w + xa..yy * self.w + xb] {
                        for i in 0..3 { s[i] += p[i] as u64 }
                    }
                }
                let n = ((yb - ya) * (xb - xa)) as u64;
                out.push([(s[0] + n / 2) / n, (s[1] + n / 2) / n, (s[2] + n / 2) / n].map(|v| v as u8));
            }
        }
        Imagen { w: nw, h: nh, rgb: out }
    }
}

/// Franja horizontal más larga con color (≥ 3 % de píxeles saturados por fila), como autocrop().
pub fn franja_con_color(im: &Imagen) -> Option<(usize, usize)> {
    let filas: Vec<bool> = (0..im.h).map(|y| {
        let n = im.rgb[y * im.w..(y + 1) * im.w].iter().filter(|p| {
            let mx = *p.iter().max().unwrap() as f64;
            let mn = *p.iter().min().unwrap() as f64;
            let s = if mx == 0.0 { 0.0 } else { (255.0 * (mx - mn) / mx).floor() / 255.0 };
            s > 0.45 && mx / 255.0 > 0.35
        }).count();
        n as f64 / im.w as f64 > 0.03
    }).collect();
    let n = filas.len();
    let (mut best, mut best_len, mut cur, mut start, mut gap) = ((0, n), 0, 0, 0, 0);
    for i in 0..=n {
        if i < n && filas[i] {
            if cur == 0 { start = i }
            cur = i - start + 1;
            gap = 0;
        } else {
            gap += 1;
            if gap as f64 > n as f64 * 0.04 || i == n {
                if cur > best_len { best_len = cur; best = (start, start + cur) }
                cur = 0;
            }
        }
    }
    if (best_len as f64) < n as f64 * 0.2 { return None }
    let pad = (n as f64 * 0.01) as usize;
    Some((best.0.saturating_sub(pad), (best.1 + pad).min(im.h)))
}

fn d2(a: &[f64; 3], b: &[f64; 3]) -> f64 { (a[0] - b[0]).powi(2) + (a[1] - b[1]).powi(2) + (a[2] - b[2]).powi(2) }

/// k-means determinista en OKLab: semillas = cubos más poblados de un histograma de 4 bits por canal,
/// separados entre sí; 25 iteraciones de Lloyd. Devuelve (centro RGB, área, píxeles del grupo).
pub fn kmeans(im: &Imagen, k: usize) -> Vec<(Rgb, f64, Vec<[u8; 3]>)> {
    let px: Vec<[f64; 3]> = im.rgb.iter().map(|p| oklab((p[0] as f64, p[1] as f64, p[2] as f64))).collect();
    let mut hist = std::collections::BTreeMap::<(u8, u8, u8), (usize, [f64; 3])>::new();
    for (p, c) in im.rgb.iter().zip(&px) {
        let e = hist.entry((p[0] >> 4, p[1] >> 4, p[2] >> 4)).or_insert((0, [0.0; 3]));
        e.0 += 1;
        for i in 0..3 { e.1[i] += c[i] }
    }
    let mut cubos: Vec<_> = hist.into_iter().map(|(clave, (n, s))| (n, clave, [s[0] / n as f64, s[1] / n as f64, s[2] / n as f64])).collect();
    cubos.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
    let mut centros: Vec<[f64; 3]> = vec![];
    for umbral in [0.06_f64, 0.03, 0.0] {
        for c in &cubos {
            if centros.len() >= k { break }
            if centros.iter().all(|x| d2(x, &c.2).sqrt() > umbral) { centros.push(c.2) }
        }
    }
    let mut asign = vec![0usize; px.len()];
    for _ in 0..25 {
        for (i, p) in px.iter().enumerate() {
            let mut m = 0;
            for j in 1..centros.len() { if d2(p, &centros[j]) < d2(p, &centros[m]) { m = j } }
            asign[i] = m;
        }
        let mut suma = vec![([0.0; 3], 0usize); centros.len()];
        for (i, p) in px.iter().enumerate() { let s = &mut suma[asign[i]]; for j in 0..3 { s.0[j] += p[j] } s.1 += 1 }
        let mut mov = 0.0f64;
        for (c, (s, n)) in centros.iter_mut().zip(&suma) {
            if *n > 0 {
                let nc = [s[0] / *n as f64, s[1] / *n as f64, s[2] / *n as f64];
                mov = mov.max(d2(c, &nc));
                *c = nc;
            }
        }
        if mov < 1e-10 { break }
    }
    let mut grupos: Vec<Vec<[u8; 3]>> = vec![vec![]; centros.len()];
    for (i, p) in im.rgb.iter().enumerate() { grupos[asign[i]].push(*p) }
    let n = px.len().max(1) as f64;
    let mut out: Vec<_> = centros.iter().zip(grupos).filter(|(_, g)| !g.is_empty())
        .map(|(c, g)| (oklab_a_rgb(c), g.len() as f64 / n, g)).collect();
    out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap().then(rgb_a_hex(a.0).cmp(&rgb_a_hex(b.0))));
    out
}

/// Color vivo de un grupo: mediana por canal del 30 % de píxeles más saturados (como vivid()).
fn vivo(g: &[[u8; 3]]) -> Rgb {
    let sat = |p: &[u8; 3]| { let mx = *p.iter().max().unwrap() as f64; let mn = *p.iter().min().unwrap() as f64; (mx - mn) / mx.max(1.0) };
    let mut s: Vec<f64> = g.iter().map(sat).collect();
    s.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let q = cuantil(&s, 0.7);
    let top: Vec<&[u8; 3]> = g.iter().filter(|p| sat(p) >= q).collect();
    let med = |i: usize| { let mut v: Vec<f64> = top.iter().map(|p| p[i] as f64).collect(); v.sort_by(|a, b| a.partial_cmp(b).unwrap()); cuantil(&v, 0.5) };
    (med(0), med(1), med(2))
}

/// Cuantil con interpolación lineal (numpy por defecto) de una lista ordenada.
fn cuantil(v: &[f64], q: f64) -> f64 {
    if v.is_empty() { return 0.0 }
    let pos = q * (v.len() - 1) as f64;
    let (i, f) = (pos.floor() as usize, pos - pos.floor());
    if i + 1 < v.len() { v[i] + (v[i + 1] - v[i]) * f } else { v[i] }
}

pub struct Grupo { pub hex: String, pub area: f64, pub tono: f64, pub luz: f64, pub sat: f64, pub v: f64, pub vivo: String }

/// Paleta de un flyer (recorte automático de la franja con color, 240 px, k = 12).
pub fn paleta_flyer(ruta: &str) -> Result<Vec<Grupo>, String> {
    let im = cargar(ruta)?;
    let im = match franja_con_color(&im) { Some((a, b)) => im.recortar(a, b), None => im };
    let im = im.reducir(240);
    Ok(kmeans(&im, 12).into_iter().map(|(c, area, g)| {
        let (h, l, _) = hls(c);
        let (s, v) = hsv_sv(c);
        Grupo { hex: rgb_a_hex(c), area, tono: (h * 360.0).round(), luz: l, sat: s, v, vivo: rgb_a_hex(vivo(&g)) }
    }).collect())
}

fn hls_a_rgb(h: f64, l: f64, s: f64) -> Rgb {
    if s == 0.0 { return (l * 255.0, l * 255.0, l * 255.0) }
    let m2 = if l <= 0.5 { l * (1.0 + s) } else { l + s - l * s };
    let m1 = 2.0 * l - m2;
    let v = |hue: f64| {
        let hue = hue.rem_euclid(1.0);
        255.0 * if hue < 1.0 / 6.0 { m1 + (m2 - m1) * hue * 6.0 } else if hue < 0.5 { m2 } else if hue < 2.0 / 3.0 { m1 + (m2 - m1) * (2.0 / 3.0 - hue) * 6.0 } else { m1 }
    };
    (v(h + 1.0 / 3.0), v(h), v(h - 1.0 / 3.0))
}

/// Roles de color (fondo, claro, 3 acentos) como ds_from_image.roles().
pub fn roles(cl: &[Grupo]) -> Value {
    let fondo = cl.iter().filter(|c| c.luz < 0.22).max_by(|a, b| a.area.partial_cmp(&b.area).unwrap())
        .or_else(|| cl.iter().min_by(|a, b| a.luz.partial_cmp(&b.luz).unwrap())).unwrap();
    let claro = cl.iter().filter(|c| c.luz > 0.85).max_by(|a, b| a.luz.partial_cmp(&b.luz).unwrap()).map(|c| c.hex.clone()).unwrap_or("#FFFFFF".into());
    let mut acc: Vec<&Grupo> = cl.iter().filter(|c| c.sat > 0.45 && c.v > 0.45 && 0.25 < c.luz && c.luz < 0.88).collect();
    let peso = |c: &Grupo| -(c.area.sqrt()) * (c.sat * c.v).powi(2);
    acc.sort_by(|a, b| peso(a).partial_cmp(&peso(b)).unwrap());
    let mut elegidos: Vec<(String, f64)> = vec![];
    for c in acc {
        if elegidos.iter().all(|(_, t)| { let d = (c.tono - t).abs(); d.min(360.0 - d) >= 25.0 }) { elegidos.push((c.vivo.clone(), c.tono)) }
        if elegidos.len() == 3 { break }
    }
    if elegidos.is_empty() { elegidos.push((claro.clone(), 0.0)) }
    let base = elegidos[0].0.clone();
    while elegidos.len() < 3 {
        let (h, l, s) = hls(crate::color::hex_a_rgb(&base).unwrap());
        let rot = (h + elegidos.len() as f64 * 0.33).rem_euclid(1.0);
        elegidos.push((rgb_a_hex(hls_a_rgb(rot, l, s)), (rot * 360.0).round()));
    }
    json!({"fondo": fondo.hex, "claro": claro, "acento1": elegidos[0].0, "acento2": elegidos[1].0, "acento3": elegidos[2].0})
}
