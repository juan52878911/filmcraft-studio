//! `cine elegir-ds`: ranking de design systems para un material (antes brief_infer.match_ds).
//! Señales: rutas (palabras enteras de `match.rutas` en los nombres de carpeta del material) y parecido
//! de la paleta del flyer con `match.paleta_ref`, ahora con ΔE en OKLab en vez de distancia RGB.
use crate::catalogo::{cargar_ds, expandir, lista_ds};
use crate::color::{delta_e, hex_a_rgb, redondear, suma};
use crate::{imagen, Args};
use serde_json::{json, Value};
use std::path::{Component, Path, PathBuf};

/// ΔE (×100 OKLab) a partir del cual dos colores no se parecen nada: color = 1 − ΔE medio / TOPE.
pub const TOPE_DE: f64 = 60.0;

pub fn sin_tildes(s: &str) -> String {
    s.chars().map(|c| match c {
        'á' | 'à' | 'ä' | 'â' | 'ã' | 'å' => 'a', 'é' | 'è' | 'ë' | 'ê' => 'e', 'í' | 'ì' | 'ï' | 'î' => 'i',
        'ó' | 'ò' | 'ö' | 'ô' | 'õ' => 'o', 'ú' | 'ù' | 'ü' | 'û' => 'u', 'ñ' => 'n', 'ç' => 'c', 'ý' | 'ÿ' => 'y',
        'Á' | 'À' | 'Ä' | 'Â' | 'Ã' | 'Å' => 'A', 'É' | 'È' | 'Ë' | 'Ê' => 'E', 'Í' | 'Ì' | 'Ï' | 'Î' => 'I',
        'Ó' | 'Ò' | 'Ö' | 'Ô' | 'Õ' => 'O', 'Ú' | 'Ù' | 'Ü' | 'Û' => 'U', 'Ñ' => 'N', 'Ç' => 'C',
        c => c,
    }).collect()
}

fn palabras(s: &str) -> Vec<String> {
    sin_tildes(&s.to_lowercase()).split(|c: char| !(c.is_ascii_lowercase() || c.is_ascii_digit()))
        .filter(|t| !t.is_empty()).map(String::from).collect()
}

/// ¿El término aparece como palabras ENTERAS y seguidas en algún componente?
pub fn casa_ruta(termino: &str, comps: &[String]) -> bool {
    let q = palabras(termino);
    if q.is_empty() { return false }
    comps.iter().any(|c| { let w = palabras(c); w.len() >= q.len() && (0..=w.len() - q.len()).any(|i| w[i..i + q.len()] == q[..]) })
}

fn partes(p: &Path) -> Vec<String> {
    p.components().filter_map(|c| match c {
        Component::Normal(x) => Some(x.to_string_lossy().to_string()),
        _ => None,
    }).collect()
}

fn normalizar(p: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            Component::CurDir => {}
            Component::ParentDir => { out.pop(); }
            c => out.push(c),
        }
    }
    out
}

/// Nombres de carpeta y fichero del material bajo su carpeta común, más `arriba` carpetas por encima.
pub fn componentes(rutas: &[String], arriba: usize) -> Vec<String> {
    let ps: Vec<PathBuf> = rutas.iter().filter(|r| !r.trim().is_empty()).map(|r| expandir(r)).collect();
    if ps.is_empty() { return vec![] }
    let bases: Vec<PathBuf> = ps.iter().map(|p| if p.extension().is_some() || p.is_file() { p.parent().map(Path::to_path_buf).unwrap_or_default() } else { p.clone() }).map(|p| normalizar(&p)).collect();
    let abs = bases[0].is_absolute();
    let mut out: Vec<String> = vec![];
    if bases.iter().all(|b| b.is_absolute() == abs) {
        let mut base: Vec<Component> = bases[0].components().collect();
        for b in &bases[1..] {
            let c: Vec<Component> = b.components().collect();
            let n = base.iter().zip(&c).take_while(|(x, y)| x == y).count();
            base.truncate(n);
        }
        let base: PathBuf = base.iter().collect();
        let bp = partes(&base);
        out.extend(bp[bp.len().saturating_sub(arriba)..].iter().cloned());
        for p in &ps {
            match normalizar(p).strip_prefix(&base) {
                Ok(r) => out.extend(partes(r)),
                Err(_) => out.push(p.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default()),
            }
        }
    } else {
        for p in &ps {
            let pp = partes(p);
            out.extend(pp[pp.len().saturating_sub(arriba + 1)..].iter().cloned());
        }
    }
    let mut vistos = std::collections::HashSet::new();
    out.into_iter().filter(|x| vistos.insert(x.clone())).collect()
}

fn mismo_fichero(a: &str, b: &str) -> bool {
    let (pa, pb) = (Path::new(a), Path::new(b));
    if let (Ok(x), Ok(y)) = (pa.canonicalize(), pb.canonicalize()) { if x == y { return true } }
    match (std::fs::read(pa), std::fs::read(pb)) { (Ok(x), Ok(y)) => x == y, _ => false }
}

/// Parecido de dos paletas: 1 − media de la ΔE de cada color de `pal` a su más cercano en `refp` / TOPE.
pub fn parecido(pal: &[String], refp: &[String]) -> Option<f64> {
    let refs: Vec<_> = refp.iter().filter_map(|h| hex_a_rgb(h)).collect();
    if refs.is_empty() || pal.is_empty() { return None }
    let ds: Vec<f64> = pal.iter().filter_map(|h| hex_a_rgb(h)).map(|a| refs.iter().map(|b| delta_e(a, *b).min(TOPE_DE)).fold(f64::MAX, f64::min)).collect();
    Some(1.0 - suma(ds.iter().copied()) / ds.len() as f64 / TOPE_DE)
}

pub fn paleta_de_flyer(flyer: &str) -> Result<Vec<String>, String> {
    let cl = imagen::paleta_flyer(flyer)?;
    let r = imagen::roles(&cl);
    Ok(["fondo", "acento1", "acento2", "acento3", "claro"].iter().map(|k| r[*k].as_str().unwrap().to_string()).collect())
}

/// [(score, id, ruta, color)] ordenado de más a menos.
pub fn ranking(flyer: Option<&str>, paleta: Option<Vec<String>>, rutas: &[String], para: &str) -> Result<Vec<Value>, String> {
    let pal = match (paleta, flyer.filter(|f| Path::new(f).exists())) {
        (Some(p), _) => Some(p),
        (None, Some(f)) => Some(paleta_de_flyer(f)?),
        _ => None,
    };
    let comps = componentes(rutas, 2);
    let mut out = vec![];
    for d in lista_ds() {
        let Ok((ds, _, _)) = cargar_ds(&d.display().to_string()) else { continue };
        let promo = crate::validar::verdad(ds.get("promo"));
        if (para == "camara" && promo) || (para == "promo" && !promo) { continue }
        let m = &ds["match"];
        let r = if m["rutas"].as_array().into_iter().flatten().filter_map(|x| x.as_str()).filter(|x| !x.is_empty()).any(|x| casa_ruta(x, &comps)) { 1.0 } else { 0.0 };
        let mut c = None;
        if let Some(p) = &pal {
            let refp: Vec<String> = m["paleta_ref"].as_array().into_iter().flatten().filter_map(|x| x.as_str().map(String::from)).collect();
            if !refp.is_empty() { c = parecido(p, &refp) }
            if let (Some(f), Some(mf)) = (flyer, m["flyer"].as_str().filter(|s| !s.is_empty())) {
                if mismo_fichero(f, mf) { c = Some(1.0) }
            }
        }
        let (wr, wc) = (if comps.is_empty() { 0.0 } else { 1.0 }, if pal.is_some() { 1.0 } else { 0.0 });
        let score = if wr + wc > 0.0 { (wr * r + wc * c.unwrap_or(0.0)) / (wr + wc) } else { 0.0 };
        out.push(json!({"score": redondear(score, 3), "id": ds["id"], "ruta": r, "color": c.map(|x| redondear(x, 3))}));
    }
    out.sort_by(|a, b| b["score"].as_f64().partial_cmp(&a["score"].as_f64()).unwrap().then(b["id"].as_str().cmp(&a["id"].as_str())));
    Ok(out)
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let mut rutas: Vec<String> = a.opt("ruta").map(|r| vec![r.to_string()]).unwrap_or_default();
    if let Some(j) = a.opt("rutas-json") {
        rutas.extend(serde_json::from_str::<Vec<String>>(j).map_err(|e| format!("--rutas-json: {e}"))?);
    }
    let paleta = a.opt("paleta").map(|p| p.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect());
    let para = a.opt("para").unwrap_or("todos");
    if !["todos", "camara", "promo"].contains(&para) { return Err("--para: todos, camara o promo".into()) }
    let rk = ranking(a.opt("flyer"), paleta, &rutas, para)?;
    if a.flag("json") {
        println!("{}", serde_json::to_string_pretty(&rk).unwrap());
    } else {
        for r in &rk {
            let color = if r["color"].is_null() { "None".to_string() } else { r["color"].to_string() };
            println!("{:5.2}  {:28} ruta={:.1} color={color}", r["score"].as_f64().unwrap(), r["id"].as_str().unwrap_or(""), r["ruta"].as_f64().unwrap());
        }
    }
    Ok(0)
}

#[cfg(test)]
mod pruebas {
    use super::*;
    fn v(xs: &[&str]) -> Vec<String> { xs.iter().map(|x| x.to_string()).collect() }

    #[test]
    fn componentes_no_suben_hasta_la_raiz() {
        let c = componentes(&v(&["/private/tmp/x-Users-juan-Documents-GitHub-kindling/abc/e2e/material/videos/charla.mp4"]), 2);
        assert_eq!(c, v(&["material", "videos", "charla.mp4"]));
        let c = componentes(&v(&["/a/Reto de certificacion S5/videos/1.mp4", "/a/Reto de certificacion S5/fotos/2.jpg"]), 2);
        for x in ["Reto de certificacion S5", "videos", "fotos", "a"] { assert!(c.contains(&x.to_string()), "{c:?}") }
    }

    #[test]
    fn casa_ruta_por_palabra_entera() {
        assert!(casa_ruta("kindling", &v(&["kindling-1.0", "videos"])));
        assert!(!casa_ruta("kindling", &v(&["-Users-juan-GitHub-kindlingx"])));
        assert!(!casa_ruta("promo", &v(&["promocion"])));
        assert!(casa_ruta("Reto de certificación", &v(&["Reto de certificacion S5"])));
        assert!(!casa_ruta("Reto de certificacion", &v(&["Reto", "de certificacion"])));
        assert!(casa_ruta("RetoCertEAN", &v(&["RetoCertEAN-2025"])));
    }

    #[test]
    fn parecido_en_oklab() {
        let p = v(&["#161D27", "#FF9900", "#AD5CFF", "#FF52EA", "#FFFFFF"]);
        assert!((parecido(&p, &p).unwrap() - 1.0).abs() < 1e-12);
        let lejos = parecido(&v(&["#00FF00"]), &v(&["#FF00FF"])).unwrap();
        assert!(lejos.abs() < 1e-12);           // ΔE ≥ TOPE: parecido 0
    }
}
