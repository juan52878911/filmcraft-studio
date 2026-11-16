//! `cine criterios`: comprueba los criterios de aceptación de la biblia contra las medidas.
//!
//! Un criterio `{id, que, como}` se comprueba así:
//! - con `medida` (lista de `{ruta, min?, max?, igual?, archivo?}`), cada una contra las medidas de cada
//!   entregable (`cine medir-video`) o de `verificacion.json` (montaje). `ruta` es un camino con puntos
//!   (`audio.lufs`, `formato.w`); `n:` delante cuenta los elementos (`n:negros`). `archivo` filtra los
//!   entregables por subcadena del nombre;
//! - sin `medida`, se infiere de `que` lo que tiene cifra estándar (WxH, «a–b s», fps, LUFS, dBTP, MB);
//!   cada cláusula (separada por «;») que no se entiende queda para el crítico;
//! - con `juicio: true`, va entero al crítico.
use crate::color::redondear;
use crate::Args;
use serde_json::{json, Map, Value};

#[derive(Clone, Debug, PartialEq)]
pub struct Medida {
    pub ruta: String,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub igual: Option<f64>,
    pub archivo: Option<String>,
    /// solo para los entregables con este tamaño (las cláusulas «WxH de a–b s»)
    pub lienzo: Option<(f64, f64)>,
    /// solo para los entregables con esta proporción («9:16 < 30 MB»)
    pub aspecto: Option<(f64, f64)>,
}

impl Medida {
    fn nueva(ruta: &str) -> Medida { Medida { ruta: ruta.into(), min: None, max: None, igual: None, archivo: None, lienzo: None, aspecto: None } }
    fn json(&self) -> Value {
        let mut m = Map::new();
        m.insert("ruta".into(), json!(self.ruta));
        for (k, v) in [("min", self.min), ("max", self.max), ("igual", self.igual)] { if let Some(v) = v { m.insert(k.into(), json!(v)); } }
        if let Some(a) = &self.archivo { m.insert("archivo".into(), json!(a)); }
        if let Some((w, h)) = self.lienzo { m.insert("lienzo".into(), json!(format!("{w}x{h}"))); }
        if let Some((w, h)) = self.aspecto { m.insert("aspecto".into(), json!(format!("{w}:{h}"))); }
        Value::Object(m)
    }
}

fn num(s: &str) -> Option<f64> { s.replace(',', ".").trim_matches(|c: char| !c.is_ascii_digit() && c != '.' && c != '-').parse().ok() }

/// Tokens numéricos con su posición en caracteres: (inicio, fin, valor). Acepta coma decimal y signo.
fn numeros(t: &[char]) -> Vec<(usize, usize, f64)> {
    let mut out = vec![];
    let mut i = 0;
    while i < t.len() {
        let neg = (t[i] == '-' || t[i] == '−') && t.get(i + 1).map_or(false, |c| c.is_ascii_digit()) && (i == 0 || !t[i - 1].is_ascii_digit());
        if t[i].is_ascii_digit() || neg {
            let ini = i;
            if neg { i += 1 }
            while i < t.len() && (t[i].is_ascii_digit() || ((t[i] == '.' || t[i] == ',') && t.get(i + 1).map_or(false, |c| c.is_ascii_digit()))) { i += 1 }
            let s: String = t[ini..i].iter().map(|c| if *c == '−' { '-' } else if *c == ',' { '.' } else { *c }).collect();
            if let Ok(v) = s.parse() { out.push((ini, i, v)) }
        } else {
            i += 1;
        }
    }
    out
}

fn tras(t: &[char], fin: usize) -> String { t[fin..].iter().collect::<String>().trim_start().to_lowercase() }
fn antes(t: &[char], ini: usize) -> String { t[..ini].iter().collect::<String>().trim_end().to_lowercase() }

/// Comparador justo antes del número: ≤ < ≥ > o «al menos»/«como mucho».
fn comparador(prev: &str) -> Option<&'static str> {
    if prev.ends_with('≤') || prev.ends_with("<=") || prev.ends_with("como mucho") || prev.ends_with("máximo") { Some("<=") }
    else if prev.ends_with('<') { Some("<") }
    else if prev.ends_with('≥') || prev.ends_with(">=") || prev.ends_with("al menos") || prev.ends_with("mínimo") { Some(">=") }
    else if prev.ends_with('>') { Some(">") }
    else { None }
}

/// Medidas que se entienden en una cláusula; None si queda algo con cifra sin entender.
pub fn inferir(clausula: &str) -> (Vec<Medida>, bool) {
    let c: Vec<char> = clausula.chars().collect();
    let low = clausula.to_lowercase();
    if low.contains(" si ") || low.starts_with("si ") { return (vec![], false) }
    let ns = numeros(&c);
    let mut out: Vec<Medida> = vec![];
    let mut usados = vec![false; ns.len()];
    let mut lienzo_actual: Option<(f64, f64)> = None;
    let mut lienzo_fin = 0usize;
    let mut aspecto: Option<(f64, f64)> = None;
    let mut i = 0;
    while i < ns.len() {
        let (ini, fin, v) = ns[i];
        let resto = tras(&c, fin);
        let prev = antes(&c, ini);
        // 1920x1080
        if (resto.starts_with('x') || resto.starts_with('×')) && i + 1 < ns.len() && ns[i + 1].0 <= fin + 2 {
            let h = ns[i + 1].2;
            let mut mw = Medida::nueva("formato.w"); mw.igual = Some(v); mw.lienzo = Some((v, h));
            let mut mh = Medida::nueva("formato.h"); mh.igual = Some(h); mh.lienzo = Some((v, h));
            out.push(mw); out.push(mh);
            lienzo_actual = Some((v, h));
            lienzo_fin = ns[i + 1].1;
            usados[i] = true; usados[i + 1] = true;
            i += 2;
            continue;
        }
        // 16:9 / 9:16 (aspecto: solo marca la cláusula, el tamaño lo fija WxH)
        if resto.starts_with(':') && i + 1 < ns.len() && ns[i + 1].0 == fin + 1 {
            aspecto = Some((v, ns[i + 1].2));
            usados[i] = true; usados[i + 1] = true;
            i += 2;
            continue;
        }
        // rangos a–b <unidad>
        let rango = if (resto.starts_with('–') || resto.starts_with('-') || resto.starts_with("a ")) && i + 1 < ns.len() {
            let entre: String = c[fin..ns[i + 1].0].iter().collect();
            if entre.trim().chars().count() <= 2 || entre.trim() == "a" { Some(ns[i + 1]) } else { None }
        } else { None };
        let (b, fin2) = match rango { Some((_, f, b)) => (Some(b), f), None => (None, fin) };
        let unidad = tras(&c, fin2);
        let cmp = comparador(&prev);
        let mut pon = |ruta: &str, a: f64, b: Option<f64>, cmp: Option<&str>, tol: Option<f64>| {
            let mut m = Medida::nueva(ruta);
            match (b, cmp, tol) {
                (Some(b), _, _) => { m.min = Some(a.min(b)); m.max = Some(a.max(b)) }
                (None, _, Some(t)) => { m.min = Some(a - t); m.max = Some(a + t) }
                (None, Some("<=" | "<"), _) => m.max = Some(a),
                (None, Some(">=" | ">"), _) => m.min = Some(a),
                _ => m.igual = Some(a),
            }
            // la duración va con el último WxH si no hay una coma entre ellos («1920x1080 de 28–31 s»)
            if ruta == "duracion_s" && !c[lienzo_fin.min(ini)..ini].contains(&',') { m.lienzo = lienzo_actual }
            out.push(m);
        };
        let tol = |u: &str, clave: &str| -> Option<f64> {
            let r = u.strip_prefix(clave)?.trim_start();
            let r = r.strip_prefix('±').or_else(|| r.strip_prefix("+-"))?;
            num(r.split_whitespace().next()?)
        };
        let usado = if unidad.starts_with("lufs") { pon("audio.lufs", v, b, cmp, tol(&unidad, "lufs").or(Some(1.0)).filter(|_| b.is_none())); true }
            else if unidad.starts_with("dbtp") || unidad.starts_with("db tp") { pon("audio.pico_dbtp", v, b, cmp.or(Some("<=")), None); true }
            else if unidad.starts_with("fps") { pon("formato.fps", v, b, cmp, None); true }
            else if unidad.starts_with("mb") { pon("formato.peso_mb", v, b, cmp, None); true }
            else if unidad.starts_with("s ") || unidad == "s" || unidad.starts_with("s,") || unidad.starts_with("s;") || unidad.starts_with("s.") || unidad.starts_with("seg") {
                // solo duración total: «de 28–31 s» o «dura …»; «antes de 4 s» o «≥ 1 s» no son la duración
                let es_dur = b.is_some() && !prev.ends_with("antes de") && !prev.ends_with("después de") && !prev.contains("cada");
                if es_dur { pon("duracion_s", v, b, cmp, None) }
                es_dur
            } else { false };
        if usado {
            usados[i] = true;
            if rango.is_some() { usados[i + 1] = true; i += 1 }
        }
        i += 1;
    }
    // la proporción suelta («9:16 < 30 MB») filtra los entregables solo si la cláusula no da tamaños
    if !out.iter().any(|m| m.lienzo.is_some()) {
        for m in out.iter_mut() { m.aspecto = aspecto }
    }
    // las tolerancias (±1) van con la cifra anterior
    for (k, (ini, _, _)) in ns.iter().enumerate() {
        let p = antes(&c, *ini);
        if p.ends_with('±') || p.ends_with("+-") { usados[k] = true }
    }
    // la cláusula se entiende entera si todas sus cifras se usaron (el texto sin cifras se ignora)
    let entera = !out.is_empty() && usados.iter().all(|u| *u);
    // «pico ≤ -1 dBTP» con la palabra «pico» ya está; las cifras de lienzo sin duración también
    (out, entera)
}

pub fn get<'a>(v: &'a Value, ruta: &str) -> Option<Value> {
    let (contar, ruta) = match ruta.strip_prefix("n:") { Some(r) => (true, r), None => (false, ruta) };
    let mut x = v;
    for k in ruta.split('.') {
        x = match x { Value::Object(o) => o.get(k)?, Value::Array(a) => a.get(k.parse::<usize>().ok()?)?, _ => return None };
    }
    if contar {
        return match x { Value::Array(a) => Some(json!(a.len())), Value::Object(o) => Some(json!(o.len())), _ => None };
    }
    Some(x.clone())
}

fn cumple(m: &Medida, v: f64) -> bool {
    let e = 1e-9;
    m.min.map_or(true, |a| v >= a - e) && m.max.map_or(true, |b| v <= b + e) && m.igual.map_or(true, |x| (v - x).abs() <= 0.01_f64.max(x.abs() * 0.001))
}

fn texto_rango(m: &Medida) -> String {
    match (m.min, m.max, m.igual) {
        (_, _, Some(x)) => format!("= {x}"),
        (Some(a), Some(b), _) => format!("{a}–{b}"),
        (Some(a), None, _) => format!("≥ {a}"),
        (None, Some(b), _) => format!("≤ {b}"),
        _ => "?".into(),
    }
}

/// Evalúa una medida en cada entregable que le toca. (cumple, evidencias, medidos)
fn evaluar(m: &Medida, entregas: &[(String, Value)]) -> (bool, Vec<String>, usize) {
    let mut ev = vec![];
    let mut ok = true;
    let mut n = 0;
    for (nombre, med) in entregas {
        if let Some(a) = &m.archivo { if !nombre.contains(a.as_str()) { continue } }
        if let Some((w, h)) = m.lienzo {
            // una medida atada a un tamaño solo vale para los entregables de ese tamaño (y no se puede
            // decidir si el entregable no dice el suyo)
            let (mw, mh) = (get(med, "formato.w").and_then(|x| x.as_f64()), get(med, "formato.h").and_then(|x| x.as_f64()));
            if m.ruta != "formato.w" && m.ruta != "formato.h" && (mw != Some(w) || mh != Some(h)) { continue }
        }
        if let Some((a, b)) = m.aspecto {
            let (mw, mh) = (get(med, "formato.w").and_then(|x| x.as_f64()), get(med, "formato.h").and_then(|x| x.as_f64()));
            if let (Some(w), Some(h)) = (mw, mh) { if ((w / h) / (a / b) - 1.0).abs() > 0.02 { continue } }
        }
        let Some(x) = get(med, &m.ruta).and_then(|x| x.as_f64().or_else(|| x.as_bool().map(|b| b as u8 as f64))) else { continue };
        n += 1;
        let c = cumple(m, x);
        ok &= c;
        ev.push(format!("{nombre}: {} = {} ({}) {}", m.ruta, redondear(x, 2), texto_rango(m), if c { "✓" } else { "✗" }));
    }
    (ok, ev, n)
}

/// Los lienzos WxH de un criterio son alternativas (un entregable cumple si es uno de ellos).
fn evaluar_lienzos(ms: &[Medida], entregas: &[(String, Value)]) -> Option<(bool, Vec<String>)> {
    let lz: Vec<(f64, f64)> = ms.iter().filter(|m| m.ruta == "formato.w").filter_map(|m| m.lienzo).collect();
    if lz.is_empty() { return None }
    let mut ok = true;
    let mut ev = vec![];
    for (nombre, med) in entregas {
        let (w, h) = (get(med, "formato.w").and_then(|x| x.as_f64()), get(med, "formato.h").and_then(|x| x.as_f64()));
        let (Some(w), Some(h)) = (w, h) else { continue };
        let c = lz.contains(&(w, h));
        ok &= c;
        ev.push(format!("{nombre}: {w}x{h} ({}) {}", lz.iter().map(|(a, b)| format!("{a}x{b}")).collect::<Vec<_>>().join(" o "), if c { "✓" } else { "✗" }));
    }
    Some((ok, ev))
}

fn medidas_explicitas(c: &Value) -> Vec<Medida> {
    c["medida"].as_array().into_iter().flatten().filter_map(|m| {
        Some(Medida {
            ruta: m["ruta"].as_str()?.into(),
            min: m["min"].as_f64(), max: m["max"].as_f64(), igual: m["igual"].as_f64(),
            archivo: m["archivo"].as_str().map(String::from), lienzo: None, aspecto: None,
        })
    }).collect()
}

pub fn comprobar(biblia: &Value, entregas: &[(String, Value)]) -> Value {
    let mut filas = vec![];
    let (mut si, mut no, mut sin, mut juicio) = (0, 0, 0, 0);
    for c in biblia["criterios"].as_array().into_iter().flatten() {
        let id = c["id"].as_str().unwrap_or("?");
        let que = c["que"].as_str().unwrap_or("");
        if c["juicio"] == true {
            juicio += 1;
            filas.push(json!({"id": id, "que": que, "estado": "juicio", "evidencia": [], "falta": [que]}));
            continue;
        }
        let explicitas = medidas_explicitas(c);
        let (ms, falta): (Vec<Medida>, Vec<String>) = if !explicitas.is_empty() {
            (explicitas, vec![])
        } else {
            let mut ms = vec![];
            let mut falta = vec![];
            for cl in que.split(';').map(str::trim).filter(|s| !s.is_empty()) {
                let (m, entera) = inferir(cl);
                if !entera { falta.push(cl.to_string()) }
                if entera { ms.extend(m) }
            }
            (ms, falta)
        };
        let mut ev = vec![];
        let mut ok = true;
        let mut medidas_hechas = 0;
        if let Some((o, e)) = evaluar_lienzos(&ms, entregas) { ok &= o; ev.extend(e); medidas_hechas += 1 }
        for m in ms.iter().filter(|m| m.lienzo.is_none() || (m.ruta != "formato.w" && m.ruta != "formato.h")) {
            let (o, e, n) = evaluar(m, entregas);
            if n == 0 {
                let para = m.lienzo.map(|(w, h)| format!(" para {w}x{h}")).or(m.aspecto.map(|(w, h)| format!(" para {w}:{h}"))).unwrap_or_default();
                ev.push(format!("{}{para}: ningún entregable con esa medida: sin medida", m.ruta));
                ok = false;
                continue;
            }
            ok &= o;
            ev.extend(e);
            medidas_hechas += 1;
        }
        let sin_medir = ev.iter().any(|e| e.ends_with("sin medida"));
        let estado = if ms.is_empty() { "sin comprobar" }
            else if !ok && !sin_medir { "no cumple" }
            else if sin_medir && ev.iter().all(|e| e.ends_with("sin medida") || e.ends_with('✓')) { "sin comprobar" }
            else if !ok { "no cumple" }
            else if !falta.is_empty() { "cumple en lo medido" }
            else { "cumple" };
        match estado { "cumple" => si += 1, "no cumple" => no += 1, "cumple en lo medido" => { si += 1; juicio += 1 } _ => sin += 1 }
        let _ = medidas_hechas;
        filas.push(json!({"id": id, "que": que, "estado": estado, "evidencia": ev,
            "medidas": ms.iter().map(|m| m.json()).collect::<Vec<_>>(), "falta": falta, "inferido": c["medida"].is_null() && !ms.is_empty()}));
    }
    json!({"criterios": filas, "resumen": {"cumple": si, "no_cumple": no, "sin_comprobar": sin, "para_el_critico": juicio}})
}

pub fn markdown(r: &Value) -> String {
    let mut s = String::from("| Criterio | Qué | Estado | Evidencia |\n|---|---|---|---|\n");
    for f in r["criterios"].as_array().into_iter().flatten() {
        let mut ev: Vec<String> = f["evidencia"].as_array().into_iter().flatten().filter_map(|x| x.as_str().map(String::from)).collect();
        for x in f["falta"].as_array().into_iter().flatten().filter_map(|x| x.as_str()) { ev.push(format!("falta juicio: {x}")) }
        s += &format!("| {} | {} | {} | {} |\n", f["id"].as_str().unwrap_or(""), f["que"].as_str().unwrap_or("").replace('|', "/"), f["estado"].as_str().unwrap_or(""), ev.join("<br>").replace('|', "/"));
    }
    s
}

pub fn cargar_entregas(a: &Args) -> Result<Vec<(String, Value)>, String> {
    let mut entregas = cargar_medidas(a)?;
    if let Some(p) = a.opt("verificacion") {
        let v = crate::catalogo::leer_json(std::path::Path::new(p))?;
        let comp = a.opt("compiled").map(|c| crate::catalogo::leer_json(std::path::Path::new(c))).transpose()?;
        entregas.push(("montaje".into(), montaje(v, comp.as_ref())));
    }
    Ok(entregas)
}

/// verificacion.json como entregable: el lienzo y los fps salen del compilado (verify no los mide).
pub fn montaje(mut v: Value, comp: Option<&Value>) -> Value {
    if v["formato"].is_null() {
        let lz = comp.map(|c| c["lienzo"].clone()).unwrap_or(Value::Null);
        v["formato"] = json!({"w": lz["ancho"], "h": lz["alto"], "fps": comp.map(|c| c["fps"].clone()).unwrap_or(Value::Null)});
    }
    v
}

/// Medidas de los entregables (`--medidas a.json,b.json`, salidas de `cine medir-video`).
pub fn cargar_medidas(a: &Args) -> Result<Vec<(String, Value)>, String> {
    let mut entregas = vec![];
    for p in a.opt("medidas").into_iter().flat_map(|s| s.split(',')).map(str::trim).filter(|s| !s.is_empty()) {
        let v = crate::catalogo::leer_json(std::path::Path::new(p))?;
        let nombre = v["video"].as_str().map(|s| std::path::Path::new(s).file_name().unwrap_or_default().to_string_lossy().to_string()).unwrap_or_else(|| p.to_string());
        entregas.push((nombre, v));
    }
    Ok(entregas)
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let biblia = crate::catalogo::leer_json(std::path::Path::new(a.req("biblia")?))?;
    let entregas = cargar_entregas(a)?;
    let r = comprobar(&biblia, &entregas);
    if a.flag("md") { print!("{}", markdown(&r)) } else { println!("{}", serde_json::to_string_pretty(&r).unwrap()) }
    Ok(if r["resumen"]["no_cumple"].as_u64().unwrap_or(0) > 0 { 1 } else { 0 })
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn infiere_cifras_estandar() {
        let (m, e) = inferir("-14 LUFS ±1, pico ≤ -1 dBTP");
        assert!(e);
        assert_eq!(m[0].ruta, "audio.lufs");
        assert_eq!((m[0].min, m[0].max), (Some(-15.0), Some(-13.0)));
        assert_eq!((m[1].ruta.as_str(), m[1].max), ("audio.pico_dbtp", Some(-1.0)));
        let (m, e) = inferir("16:9 1920x1080 de 28–31 s y 9:16 1080x1920 de 24–27 s, 30 fps");
        assert!(e);
        let d: Vec<_> = m.iter().filter(|x| x.ruta == "duracion_s").collect();
        assert_eq!(d.len(), 2);
        assert_eq!(d[0].lienzo, Some((1920.0, 1080.0)));
        assert_eq!((d[1].min, d[1].max), (Some(24.0), Some(27.0)));
        assert!(m.iter().any(|x| x.ruta == "formato.fps" && x.igual == Some(30.0)));
        let (m, e) = inferir("1080x1350 y 1080x1920, 60 fps, 39-41 s");
        assert!(e);
        let d = m.iter().find(|x| x.ruta == "duracion_s").unwrap();
        assert_eq!((d.min, d.max, d.lienzo), (Some(39.0), Some(41.0), None));
        let (m, e) = inferir("9:16 < 30 MB");
        assert!(e && m[0].ruta == "formato.peso_mb" && m[0].max == Some(30.0) && m[0].aspecto == Some((9.0, 16.0)));
        assert!(!inferir("copia ligera < 30 MB si el máster pasa de 30 MB").1);
        assert!(!inferir("'máquina virtual' y '39 ms' legibles antes de 4 s").1);
        assert!(!inferir("la música cambia de género en cada transición").1);
    }

    #[test]
    fn comprueba_contra_entregas() {
        let b = json!({"criterios": [
            {"id": "c1", "que": "16:9 1920x1080 de 28–31 s y 9:16 1080x1920 de 24–27 s, 30 fps", "como": "ffprobe"},
            {"id": "c2", "que": "-14 LUFS ±1, pico ≤ -1 dBTP; la música cambia de género", "como": "ebur128"},
            {"id": "c3", "que": "sin negros", "como": "x", "medida": [{"ruta": "n:negros", "max": 0}]},
            {"id": "c4", "que": "solo el elegido caliente", "como": "hoja", "juicio": true}]});
        let h = json!({"formato": {"w": 1920, "h": 1080, "fps": 30.0}, "duracion_s": 30.0, "audio": {"lufs": -14.2, "pico_dbtp": -1.2}, "negros": []});
        let v = json!({"formato": {"w": 1080, "h": 1920, "fps": 30.0}, "duracion_s": 29.0, "audio": {"lufs": -16.0, "pico_dbtp": -0.5}, "negros": [[3.0, 3.2]]});
        let r = comprobar(&b, &[("h.mp4".into(), h), ("v.mp4".into(), v)]);
        let e: Vec<&str> = r["criterios"].as_array().unwrap().iter().map(|f| f["estado"].as_str().unwrap()).collect();
        assert_eq!(e, vec!["no cumple", "no cumple", "no cumple", "juicio"]);
        let ev = r["criterios"][0]["evidencia"].as_array().unwrap();
        assert!(ev.iter().any(|x| x.as_str().unwrap().contains("v.mp4: duracion_s = 29 (24–27) ✗")));
        assert!(ev.iter().any(|x| x.as_str().unwrap().contains("h.mp4: duracion_s = 30 (28–31) ✓")));
    }
}
