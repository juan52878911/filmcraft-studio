//! `cine validar-ds`: valida design systems de video (antes ds_validate.py). Mismas comprobaciones y
//! mensajes; el esquema (schemas/ds.schema.json) se aplica con el subconjunto propio de esquema.rs.
use crate::catalogo::{self, archivo_fuente, cargar_ds, lista_ds, tam_imagen};
use crate::color::{contraste, es_hex6, hex_a_rgb};
use crate::{esquema, patron, Args};
use serde_json::{json, Value};
use std::path::Path;

const ESQUEMA: &str = include_str!("../../schemas/ds.schema.json");
const REQ: [&str; 18] = ["id", "gramatica", "lienzo", "paleta", "fuentes", "marca", "pistas", "roles_texto", "animaciones",
    "continuidad", "transiciones", "fondos", "mattes", "sfx", "musica", "grade", "audio", "estructura"];
const REQ_ANIDADAS: [&str; 34] = ["continuidad.entrada", "continuidad.zoom_crash", "fondos.titulo", "fondos.plano", "fondos.cap",
    "fondos.cierre", "mattes.blanco", "marca.barra", "marca.titulo", "marca.cta", "estructura.duracion_s",
    "musica.bajo_voz_db", "musica.sin_voz_db", "animaciones.base_fps", "animaciones.popIn",
    "animaciones.wordReveal", "animaciones.eco", "transiciones.preferencia", "transiciones.corte",
    "audio.lufs", "audio.pico_dbtp", "pistas.video", "pistas.audio", "sfx.mapa",
    "lienzo.ancho", "lienzo.alto", "lienzo.fps",
    "roles_texto.titulo.x", "roles_texto.titulo.y", "roles_texto.titulo.color",
    "roles_texto.cierre.x", "roles_texto.cierre.y", "roles_texto.cierre.color", "roles_texto.eco.colores"];
const PISTAS_VIDEO: [&str; 3] = ["Fondo", "Main", "Mattes"];
const PISTAS_AUDIO: [&str; 2] = ["Dialogue", "Music"];
const PAL: [&str; 4] = ["fondo", "oscuro", "claro", "acento1"];
const ANIMS: [&str; 10] = ["popIn", "wordReveal", "eco", "calorEntra", "golpe", "desliza", "caida", "pop", "escribe", "ninguna"];
const ROLES_MIN: [&str; 10] = ["marca", "subtitulo", "etiqueta", "eco", "pill", "tag", "titulo", "cierre", "meta", "pie"];
const ROLES_CON_POS: [&str; 2] = ["marca", "subtitulo"];

fn get<'a>(d: &'a Value, ruta: &str) -> Option<&'a Value> {
    let mut x = d;
    for k in ruta.split('.') {
        x = x.as_object()?.get(k)?;
    }
    if x.is_null() { None } else { Some(x) }
}

/// str() de Python de un valor JSON.
pub fn py_str(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        _ => esquema::repr(v),
    }
}

fn opt_str(v: Option<&Value>) -> String { v.map(py_str).unwrap_or_else(|| "None".into()) }

fn es_num(v: &Value) -> bool { v.is_number() || v.is_boolean() }
fn num(v: &Value) -> f64 { v.as_f64().or_else(|| v.as_bool().map(|b| b as u8 as f64)).unwrap_or(0.0) }

/// Verdad de Python: null, false, 0, "", [] y {} son falsos.
pub fn verdad(v: Option<&Value>) -> bool {
    match v {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64() != Some(0.0),
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

fn errores_esquema(raw: &Value) -> Vec<String> {
    let s: Value = serde_json::from_str(ESQUEMA).expect("ds.schema.json incluido");
    let mut es = esquema::validar(&s, raw);
    es.sort_by(|a, b| a.ruta.cmp(&b.ruta));
    es.into_iter().map(|e| {
        let ruta = if e.ruta.is_empty() { "(raíz)".to_string() } else { e.ruta.join(".") };
        let m: String = e.mensaje.chars().take(200).collect();
        format!("esquema: {ruta}: {m}")
    }).collect()
}

fn errores_forma(raw: &Value) -> Vec<String> {
    let obj = raw.as_object();
    let mut err: Vec<String> = REQ.iter().filter(|k| obj.map_or(true, |o| !o.contains_key(**k))).map(|k| format!("falta '{k}'")).collect();
    if !err.is_empty() { return err }
    err.extend(REQ_ANIDADAS.iter().filter(|k| get(raw, k).is_none()).map(|k| format!("falta '{k}'")));
    let Some(roles) = raw["roles_texto"].as_object() else { err.push("roles_texto no es un objeto".into()); return err };
    for (name, r) in roles {
        if !r.is_object() {
            err.push(format!("rol {name}: no es un objeto"));
            continue;
        }
        let tam = r.get("tam");
        if !tam.map_or(false, es_num) || tam.map_or(0.0, num) <= 0.0 {
            err.push(format!("rol {name}: 'tam' tiene que ser un número > 0"));
        }
    }
    let id = raw.get("id").map(py_str).unwrap_or_else(|| "".into());
    if !patron::casa("^[a-z0-9][a-z0-9-]{0,63}$", &id) {
        err.push(format!("id no válido: {} (slug [a-z0-9-])", esquema::repr(raw.get("id").unwrap_or(&Value::Null))));
    }
    if let Some(eco) = get(raw, "roles_texto.eco.colores") {
        let bien = eco.as_array().map_or(false, |l| !l.is_empty() && l.iter().all(|p| p.as_array().map_or(false, |p| p.len() == 2)));
        if !bien { err.push("rol eco: 'colores' tiene que ser una lista no vacía de pares [texto, fondo]".into()) }
    }
    for rol in ["titulo", "cierre"] {
        for k in ["x", "y"] {
            if let Some(v) = get(raw, &format!("roles_texto.{rol}.{k}")) {
                if !(es_num(v) && (0.0..=1.0).contains(&num(v))) {
                    err.push(format!("rol {rol}: '{k}' tiene que ser un número entre 0 y 1 (fracción del lienzo)"));
                }
            }
        }
    }
    if let Some(ev) = get(raw, "zonas.evitar_y") {
        let bien = ev.as_array().map_or(false, |l| l.iter().all(|z| z.as_array().map_or(false, |z| z.len() == 2 && z.iter().all(es_num))));
        if !bien { err.push("zonas.evitar_y tiene que ser una lista de pares [y0, y1] (plan_compile los desempaqueta)".into()) }
    }
    if obj.map_or(false, |o| o.contains_key("promo")) && !get(raw, "promo.bpm").map_or(false, es_num) {
        err.push("promo sin 'bpm' numérico (promo_preview.py lo lee)".into());
    }
    err
}

fn dedup(xs: Vec<String>) -> Vec<String> {
    let mut vistos = std::collections::HashSet::new();
    xs.into_iter().filter(|x| vistos.insert(x.clone())).collect()
}

fn lista_str(v: Option<&Value>) -> Vec<String> {
    v.and_then(|x| x.as_array()).map(|a| a.iter().map(py_str).collect()).unwrap_or_default()
}

pub fn validar(ds: &Value, raw: &Value) -> (Vec<String>, Vec<String>) {
    let mut err = errores_esquema(raw);
    err.extend(errores_forma(raw));
    let mut warn: Vec<String> = vec![];
    if err.iter().any(|e| e.starts_with("falta '") && !e.contains('.')) {
        return (dedup(err), dedup(warn));
    }
    let vacio = serde_json::Map::new();
    let pal = ds["paleta"].as_object().unwrap_or(&vacio);
    for k in PAL {
        if !pal.contains_key(k) { err.push(format!("paleta sin '{k}'")) }
    }
    for (k, v) in pal {
        if !v.as_str().map_or(false, es_hex6) { err.push(format!("color no hex: {k}={}", py_str(v))) }
    }
    for k in ["rejilla", "acento2", "acento3"] {
        if !pal.contains_key(k) { warn.push(format!("paleta sin '{k}' (ds_preview y ds_assets usan el acento1 o una mezcla)")) }
    }
    let ok_ref = |x: &Value| x.is_null() || x.as_str().map_or(false, |s| es_hex6(s) || pal.contains_key(s));
    let hexc = |x: &Value, defecto: &str| -> Option<String> {
        let v = if x.is_null() { pal.get(defecto) } else if x.as_str().map_or(false, |s| s.starts_with('#')) { Some(x) } else { x.as_str().and_then(|s| pal.get(s)) };
        v.and_then(|v| v.as_str()).filter(|s| es_hex6(s)).map(String::from)
    };
    let vt = lista_str(ds["pistas"].get("video"));
    let at = lista_str(ds["pistas"].get("audio"));
    let mapa = ds["sfx"].get("mapa").and_then(|m| m.as_object()).cloned().unwrap_or_default();
    for t in PISTAS_VIDEO {
        if !vt.iter().any(|x| x == t) { err.push(format!("pistas.video sin '{t}' (apply_plan coloca ahí fondo, planos o mattes)")) }
    }
    let sfx_pistas = match ds["pistas"].get("sfx") { Some(v) => lista_str(Some(v)), None => vec!["SFX".into()] };
    for t in PISTAS_AUDIO.iter().map(|s| s.to_string()).chain(sfx_pistas) {
        if !at.contains(&t) { err.push(format!("pistas.audio sin '{t}' (apply_plan coloca ahí diálogo, música o SFX)")) }
    }
    if !vt.iter().any(|x| x == "Producto") {
        warn.push("pistas.video sin 'Producto': las capas de producto del plan no tendrán dónde ir".into());
    }
    let roles = ds["roles_texto"].as_object().cloned().unwrap_or_default();
    for r in ROLES_MIN {
        if !roles.contains_key(r) { err.push(format!("falta el rol de texto '{r}'")) }
    }
    for r in ROLES_CON_POS {
        if let Some(x) = roles.get(r) {
            if !verdad(x.get("pos")) { err.push(format!("rol {r}: falta 'pos' (apply_plan lo coloca con posición fija)")) }
        }
    }
    let fuentes = ds["fuentes"].as_object().cloned().unwrap_or_default();
    let anims = ds["animaciones"].as_object().cloned().unwrap_or_default();
    for (name, r) in &roles {
        if !r.is_object() { continue }
        let fu = r.get("fuente");
        if !fu.and_then(|f| f.as_str()).map_or(false, |f| fuentes.contains_key(f)) {
            err.push(format!("rol {name}: fuente '{}' no declarada", opt_str(fu)));
        }
        let pistas: Vec<Value> = if verdad(r.get("pistas")) { r["pistas"].as_array().cloned().unwrap_or_default() } else { vec![r.get("pista").cloned().unwrap_or(Value::Null)] };
        for t in pistas {
            if !t.as_str().map_or(false, |t| vt.iter().any(|x| x == t)) {
                err.push(format!("rol {name}: pista '{}' no está en pistas.video", py_str(&t)));
            }
        }
        let an = r.get("anim").map(py_str).unwrap_or_else(|| "ninguna".into());
        if !ANIMS.contains(&an.as_str()) {
            err.push(format!("rol {name}: animación '{an}' desconocida"));
        } else if an != "ninguna" && !anims.contains_key(&an) {
            err.push(format!("rol {name}: animación '{an}' sin definir en 'animaciones'"));
        }
        if verdad(r.get("sfx")) && !mapa.contains_key(&py_str(&r["sfx"])) {
            err.push(format!("rol {name}: sfx '{}' no está en sfx.mapa", py_str(&r["sfx"])));
        }
        let pares: Vec<(Value, Value)> = if verdad(r.get("colores")) {
            r["colores"].as_array().unwrap().iter().map(|p| {
                let l = p.as_array().cloned().unwrap_or_default();
                (l.first().cloned().unwrap_or(Value::Null), l.get(1).cloned().unwrap_or(Value::Null))
            }).collect()
        } else {
            let color = match r.get("color") { Some(c) => c.clone(), None => json!("claro") };
            let fondos: Vec<Value> = match r.get("fondo") { Some(Value::Array(a)) => a.clone(), Some(f) => vec![f.clone()], None => vec![Value::Null] };
            fondos.into_iter().map(|f| (color.clone(), f)).collect()
        };
        for (tc, bc) in pares {
            if !ok_ref(&tc) || !ok_ref(&bc) {
                err.push(format!("rol {name}: color '{}'/'{}' no está en la paleta", py_str(&tc), py_str(&bc)));
                continue;
            }
            let (Some(txc), Some(bgc)) = (hexc(&tc, "claro"), hexc(&bc, "fondo")) else { continue };
            let c = contraste(hex_a_rgb(&txc).unwrap(), hex_a_rgb(&bgc).unwrap());
            let minimo = if r.get("tam").map_or(0.0, num) >= 60.0 { 3.0 } else { 4.5 };
            if c < minimo {
                let bc_s = if verdad(Some(&bc)) { py_str(&bc) } else { "fondo".into() };
                let m = format!("rol {name}: contraste {c:.1}:1 de {} sobre {bc_s} (mínimo {minimo:.1})", py_str(&tc));
                if c < 2.5 { err.push(m) } else { warn.push(m) }
            }
        }
        // pegatina@1: sombra, contorno, prefijo y resaltado también nombran colores de la paleta
        let extra = [r.get("sombra").and_then(|x| x.get("color")), r.get("contorno").and_then(|x| x.get("color")),
                     r.get("prefijo").and_then(|x| x.get("color")), r.get("resalta")];
        for c in extra.into_iter().flatten() {
            if !ok_ref(c) { err.push(format!("rol {name}: color '{}' no está en la paleta", py_str(c))) }
        }
    }
    let home = catalogo::casa().display().to_string();
    for (k, f) in &fuentes {
        match archivo_fuente(f) {
            Some(ff) if Path::new(&ff).exists() => {
                if ff.starts_with(&home) { warn.push(format!("fuente '{k}' en {}: en otra máquina puede no estar", ff.replace(&home, "~"))) }
            }
            _ => err.push(format!("fuente '{k}' ({} {}) no está instalada", opt_str(f.get("familia")), f.get("estilo").map(py_str).unwrap_or_default())),
        }
    }
    let lz = &ds["lienzo"];
    let (la, lh) = (lz.get("ancho").map(num), lz.get("alto").map(num));
    let mut variantes: Vec<((f64, f64), String)> = vec![];
    if let Some(vs) = lz.get("variantes").and_then(|v| v.as_object()) {
        for (n, v) in vs {
            if v.is_object() {
                let t = (v.get("ancho").map_or(f64::NAN, num), v.get("alto").map_or(f64::NAN, num));
                variantes.retain(|(x, _)| *x != t);
                variantes.push((t, n.clone()));
            }
        }
    }
    for grp in ["fondos", "mattes"] {
        for (k, p) in ds[grp].as_object().cloned().unwrap_or_default() {
            let p = py_str(&p);
            if !Path::new(&p).exists() {
                err.push(format!("{grp}.{k}: no existe {p}"));
                continue;
            }
            let (w, h) = match tam_imagen(Path::new(&p)) {
                Ok(t) => (t.0 as f64, t.1 as f64),
                Err(e) => { err.push(format!("{grp}.{k}: no se puede abrir ({e} '{p}')")); continue }
            };
            let es_lienzo = Some(w) == la && Some(h) == lh;
            let var = variantes.iter().find(|(t, _)| *t == (w, h));
            if !es_lienzo {
                if let Some((_, n)) = var {
                    warn.push(format!("{grp}.{k}: mide {w}x{h} (variante '{n}'), no como el lienzo {}x{}", fmt_n(la), fmt_n(lh)));
                } else {
                    err.push(format!("{grp}.{k}: mide {w}x{h} y el lienzo es {}x{} (regenera con promo_fondos.py o ds_assets.py)", opt_str(lz.get("ancho")), opt_str(lz.get("alto"))));
                }
            }
        }
    }
    for (k, p) in ds["sfx"].get("_mapa_abs").and_then(|m| m.as_object()).cloned().unwrap_or_default() {
        if !Path::new(&py_str(&p)).exists() { err.push(format!("sfx.{k}: no existe {}", py_str(&p))) }
    }
    let tr = ds["transiciones"].as_object().cloned().unwrap_or_default();
    let mut usadas: Vec<String> = lista_str(tr.get("preferencia"));
    usadas.extend(tr.keys().filter(|k| *k != "preferencia").cloned());
    let mattes = ds["mattes"].as_object().cloned().unwrap_or_default();
    let mut pide: Vec<(String, Vec<String>)> = vec![];
    if usadas.iter().any(|u| u == "matte") {
        let m = tr.get("matte").and_then(|m| m.get("mattes")).filter(|x| verdad(Some(x)));
        pide.push(("matte".into(), m.map(|x| lista_str(Some(x))).unwrap_or_else(|| vec!["acento1".into()])));
    }
    for t in ["flash", "glitch"] {
        if usadas.iter().any(|u| u == t) {
            let m = tr.get(t).and_then(|c| c.get("matte")).map(py_str).unwrap_or_else(|| "blanco".into());
            pide.push((t.into(), vec![m]));
        }
    }
    for (t, ms) in pide {
        for m in ms {
            if !mattes.contains_key(&m) { err.push(format!("transición {t}: el matte '{m}' no está en mattes")) }
        }
    }
    for (t, cfg) in &tr {
        if cfg.is_object() && verdad(cfg.get("sfx")) && !mapa.contains_key(&py_str(&cfg["sfx"])) {
            err.push(format!("transición {t}: sfx '{}' no está en sfx.mapa", py_str(&cfg["sfx"])));
        }
    }
    for t in lista_str(tr.get("preferencia")) {
        if !tr.contains_key(&t) { err.push(format!("transición '{t}' en preferencia pero sin definir")) }
    }
    if !(verdad(lz.get("ancho")) && verdad(lz.get("alto")) && verdad(lz.get("fps"))) {
        err.push("lienzo necesita ancho, alto y fps".into());
    }
    (dedup(err), dedup(warn))
}

fn fmt_n(x: Option<f64>) -> String {
    match x { Some(v) if v.fract() == 0.0 => format!("{}", v as i64), Some(v) => format!("{v}"), None => "None".into() }
}

pub fn comprobar(id: &str, estricto: bool) -> Value {
    let (ds, raw, dir) = match cargar_ds(id) {
        Ok(x) => x,
        Err(e) if e.starts_with("no encuentro") => return json!({"ds": id, "dir": null, "ok": false, "errores": [e], "avisos": [], "esquema": null}),
        Err(e) => return json!({"ds": id, "dir": null, "ok": false, "errores": [format!("ds.json no se puede cargar: {e}")], "avisos": [], "esquema": null}),
    };
    let (mut err, mut warn) = validar(&ds, &raw);
    if estricto {
        err.extend(warn.iter().map(|w| format!("(estricto) {w}")));
        warn.clear();
    }
    json!({"ds": ds.get("id").cloned().unwrap_or(Value::Null), "dir": dir.display().to_string(), "ok": err.is_empty(),
           "errores": err, "avisos": warn, "esquema": "cine (JSON Schema 2020-12, subconjunto)"})
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let todos = a.flag("todos");
    let id = a.pos.first().cloned();
    if id.is_none() && !todos {
        eprintln!("cine validar-ds: indica un DS o --todos");
        return Ok(2);
    }
    let res: Vec<Value> = if todos {
        lista_ds().iter().map(|d| comprobar(&d.display().to_string(), a.flag("estricto"))).collect()
    } else {
        vec![comprobar(id.as_deref().unwrap(), a.flag("estricto"))]
    };
    if a.flag("json") {
        let v = if todos { Value::Array(res.clone()) } else { res[0].clone() };
        println!("{}", serde_json::to_string_pretty(&v).unwrap());
    } else {
        for r in &res {
            println!("DS {}: {}", py_str(&r["ds"]), if r["ok"] == true { "OK" } else { "CON ERRORES" });
            for e in r["errores"].as_array().unwrap() { println!("  ✗ {}", py_str(e)) }
            for w in r["avisos"].as_array().unwrap() { println!("  ! {}", py_str(w)) }
        }
    }
    Ok(if res.iter().all(|r| r["ok"] == true) { 0 } else { 1 })
}
