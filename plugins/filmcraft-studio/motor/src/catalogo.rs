//! Catálogo de design systems (como common.py): carpetas, carga con rutas resueltas, fuentes instaladas
//! y tamaño de imágenes sin decodificarlas.
use serde_json::Value;
use std::path::{Path, PathBuf};

pub fn casa() -> PathBuf {
    std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")).map(PathBuf::from).unwrap_or_else(|| PathBuf::from("/"))
}

pub fn expandir(s: &str) -> PathBuf {
    if s == "~" { return casa() }
    match s.strip_prefix("~/") {
        Some(r) => casa().join(r),
        None => PathBuf::from(s),
    }
}

/// Raíz del plugin: FILMCRAFT_STUDIO_ROOT, CLAUDE_PLUGIN_ROOT o la carpeta que contiene el ejecutable
/// (bin/<so>-<arq>/cine o motor/target/<perfil>/cine) y tiene design-systems/.
pub fn raiz() -> PathBuf {
    for v in ["FILMCRAFT_STUDIO_ROOT", "CLAUDE_PLUGIN_ROOT"] {
        if let Some(p) = std::env::var_os(v) {
            let p = PathBuf::from(p);
            if p.join("design-systems").is_dir() { return p }
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        let exe = exe.canonicalize().unwrap_or(exe);
        for a in exe.ancestors().skip(1) {
            if a.join("design-systems").is_dir() && a.join("schemas").is_dir() { return a.to_path_buf() }
        }
    }
    PathBuf::from(".")
}

pub fn datos() -> PathBuf {
    match std::env::var_os("CLAUDE_PLUGIN_DATA").filter(|v| !v.is_empty()) {
        Some(p) => PathBuf::from(p),
        None => casa().join(".cache/filmcraft-studio"),
    }
}

pub fn ds_dirs() -> Vec<PathBuf> {
    let user = match std::env::var_os("FILMCRAFT_DS_CATALOGO").filter(|v| !v.is_empty()) {
        Some(p) => PathBuf::from(p),
        None => datos().join("design-systems"),
    };
    vec![user, raiz().join("design-systems")]
}

pub fn borradores() -> PathBuf { datos().join("borradores") }

pub fn ds_dir(id: &str) -> Result<PathBuf, String> {
    let p = expandir(id);
    if p.is_dir() && p.join("ds.json").exists() { return Ok(p) }
    if p.file_name().map_or(false, |n| n == "ds.json") && p.exists() {
        return Ok(p.parent().map(Path::to_path_buf).unwrap_or_default());
    }
    let mut todas = ds_dirs();
    todas.push(borradores());
    for d in &todas {
        if d.join(id).join("ds.json").exists() { return Ok(d.join(id)) }
    }
    Err(format!("no encuentro el DS '{id}' en {}", todas.iter().map(|d| d.display().to_string()).collect::<Vec<_>>().join(", ")))
}

/// Carpetas de los DS aprobados, una por id: la del usuario tapa a la precargada con el mismo id.
pub fn lista_ds() -> Vec<PathBuf> {
    let mut out = vec![];
    let mut vistos = std::collections::HashSet::new();
    for d in ds_dirs() {
        let Ok(rd) = std::fs::read_dir(&d) else { continue };
        let mut cs: Vec<PathBuf> = rd.flatten().map(|e| e.path()).collect();
        cs.sort();
        for c in cs {
            let n = c.file_name().unwrap_or_default().to_string_lossy().to_string();
            if c.join("ds.json").exists() && !n.contains(".anterior-") && vistos.insert(n) {
                out.push(c);
            }
        }
    }
    out
}

pub fn leer_json(p: &Path) -> Result<Value, String> {
    let t = std::fs::read_to_string(p).map_err(|e| format!("{}: {e}", p.display()))?;
    serde_json::from_str(&t).map_err(|e| format!("{}: {e}", p.display()))
}

/// ds.json con rutas resueltas (assets/… y ~/…). Devuelve (ds resuelto, ds.json tal cual, carpeta).
pub fn cargar_ds(id: &str) -> Result<(Value, Value, PathBuf), String> {
    let d = ds_dir(id)?;
    let raw = leer_json(&d.join("ds.json"))?;
    let mut ds = raw.clone();
    let res = |v: &Value| -> Value {
        match v.as_str() {
            Some(s) if s.starts_with("assets/") => Value::String(d.join(s).display().to_string()),
            Some(s) if s.starts_with("~/") => Value::String(expandir(s).display().to_string()),
            _ => v.clone(),
        }
    };
    if !ds.is_object() { return Err("ds.json no es un objeto".into()) }
    for k in ["fondos", "mattes"] {
        if let Some(o) = ds.get_mut(k).and_then(|x| x.as_object_mut()) {
            for v in o.values_mut() { *v = res(v) }
        }
    }
    let sfx_dir = ds.get("sfx").and_then(|s| s.get("dir")).and_then(|x| x.as_str()).filter(|s| !s.is_empty()).map(|s| res(&Value::String(s.into())));
    let base = match sfx_dir { Some(Value::String(s)) => PathBuf::from(s), _ => d.clone() };
    let mut mapa_abs = serde_json::Map::new();
    if let Some(m) = ds.get("sfx").and_then(|s| s.get("mapa")).and_then(|m| m.as_object()) {
        for (n, v) in m {
            mapa_abs.insert(n.clone(), Value::String(base.join(v.as_str().unwrap_or("")).display().to_string()));
        }
    }
    if let Some(s) = ds.get_mut("sfx").and_then(|s| s.as_object_mut()) {
        s.insert("_mapa_abs".into(), Value::Object(mapa_abs));
    }
    if let Some(fs) = ds.get_mut("fuentes").and_then(|f| f.as_object_mut()) {
        for f in fs.values_mut() {
            if let Some(a) = f.get("archivo").filter(|a| a.as_str().map_or(false, |s| !s.is_empty())).cloned() {
                f["archivo"] = res(&a);
            }
        }
    }
    if let Some(fl) = ds.get("match").and_then(|m| m.get("flyer")).filter(|f| f.as_str().map_or(false, |s| !s.is_empty())).cloned() {
        ds["match"]["flyer"] = res(&fl);
    }
    Ok((ds, raw, d))
}

fn es_macos() -> bool { cfg!(target_os = "macos") }

fn ficheros_fuente() -> Vec<PathBuf> {
    let h = casa();
    let mut out = vec![];
    for d in [h.join("Library/Fonts"), "/Library/Fonts".into(), "/System/Library/Fonts".into(), "/System/Library/Fonts/Supplemental".into()] {
        if let Ok(rd) = std::fs::read_dir(&d) { out.extend(rd.flatten().map(|e| e.path())) }
    }
    if !es_macos() {
        let win = std::env::var("WINDIR").unwrap_or_else(|_| "C:/Windows".into());
        for d in [h.join(".local/share/fonts"), h.join(".fonts"), "/usr/share/fonts".into(), "/usr/local/share/fonts".into(), PathBuf::from(win).join("Fonts")] {
            recorrer(&d, &mut out);
        }
    }
    out
}

fn recorrer(d: &Path, out: &mut Vec<PathBuf>) {
    let Ok(rd) = std::fs::read_dir(d) else { return };
    for e in rd.flatten() {
        let p = e.path();
        out.push(p.clone());
        if p.is_dir() { recorrer(&p, out) }
    }
}

/// Archivo de la fuente: 'archivo' del DS o búsqueda por familia y estilo (como common.font_file).
pub fn archivo_fuente(f: &Value) -> Option<String> {
    if let Some(a) = f.get("archivo").and_then(|a| a.as_str()).filter(|a| !a.is_empty()) {
        if Path::new(a).exists() { return Some(a.into()) }
    }
    let fam = f.get("familia")?.as_str()?.replace(' ', "").to_lowercase();
    let sty = f.get("estilo").and_then(|s| s.as_str()).unwrap_or("Regular").to_lowercase();
    let pref: String = fam.chars().take(6).collect();
    let cands: Vec<PathBuf> = ficheros_fuente().into_iter().filter(|p| {
        let n = p.file_name().unwrap_or_default().to_string_lossy().to_lowercase().replace(' ', "");
        let ext = p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
        matches!(ext.as_str(), "ttf" | "otf" | "ttc") && n.starts_with(&pref)
    }).collect();
    for p in &cands {
        let n = p.file_stem().unwrap_or_default().to_string_lossy().to_lowercase().replace(' ', "");
        if n.replace('-', "").contains(&fam) && n.ends_with(&sty) { return Some(p.display().to_string()) }
    }
    if fam == "menlo" { return Some("/System/Library/Fonts/Menlo.ttc".into()) }
    cands.first().map(|p| p.display().to_string())
}

/// (ancho, alto) de un PNG, JPEG, GIF, BMP o WebP leyendo solo la cabecera.
pub fn tam_imagen(p: &Path) -> Result<(u64, u64), String> {
    let b = std::fs::read(p).map_err(|e| e.to_string())?;
    let be32 = |i: usize| b.get(i..i + 4).map(|x| u32::from_be_bytes([x[0], x[1], x[2], x[3]]) as u64);
    let le16 = |i: usize| b.get(i..i + 2).map(|x| u16::from_le_bytes([x[0], x[1]]) as u64);
    let le32 = |i: usize| b.get(i..i + 4).map(|x| u32::from_le_bytes([x[0], x[1], x[2], x[3]]) as u64);
    if b.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Ok((be32(16).ok_or("PNG corto")?, be32(20).ok_or("PNG corto")?));
    }
    if b.starts_with(b"GIF8") { return Ok((le16(6).ok_or("GIF corto")?, le16(8).ok_or("GIF corto")?)) }
    if b.starts_with(b"BM") { return Ok((le32(18).ok_or("BMP corto")?, (le32(22).ok_or("BMP corto")? as i32).unsigned_abs() as u64)) }
    if b.starts_with(&[0xFF, 0xD8]) {
        let mut i = 2;
        while i + 9 < b.len() {
            if b[i] != 0xFF { i += 1; continue }
            let m = b[i + 1];
            if (0xC0..=0xCF).contains(&m) && m != 0xC4 && m != 0xC8 && m != 0xCC {
                let h = u16::from_be_bytes([b[i + 5], b[i + 6]]) as u64;
                let w = u16::from_be_bytes([b[i + 7], b[i + 8]]) as u64;
                return Ok((w, h));
            }
            let l = u16::from_be_bytes([b[i + 2], b[i + 3]]) as usize;
            i += 2 + l;
        }
        return Err("JPEG sin cabecera SOF".into());
    }
    if b.len() > 30 && &b[0..4] == b"RIFF" && &b[8..12] == b"WEBP" {
        match &b[12..16] {
            b"VP8X" => return Ok((1 + (le32(24).unwrap() & 0xFFFFFF), 1 + (le32(27).unwrap() & 0xFFFFFF))),
            b"VP8 " => return Ok((le16(26).unwrap() & 0x3FFF, le16(28).unwrap() & 0x3FFF)),
            b"VP8L" => {
                let v = le32(21).unwrap();
                return Ok((1 + (v & 0x3FFF), 1 + ((v >> 14) & 0x3FFF)));
            }
            _ => {}
        }
    }
    Err("cannot identify image file".into())
}
