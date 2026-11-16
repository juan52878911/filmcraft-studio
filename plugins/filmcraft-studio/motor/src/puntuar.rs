//! `cine puntuar`: puntúa con reglas fijas los ejes del crítico que se pueden contar (1–5) y prepara lo
//! que queda para el único crítico con IA: los ejes de gusto, sus techos y los criterios sin medida.
//!
//! Anclas (de agents/critico.md, skills/editor-filmcraft y director-video/references/reglas.md):
//! - audio: −14 ± 1 LUFS (o `ds.audio.lufs`) y pico ≤ −1 dBTP (`ds.audio.pico_dbtp`).
//! - obligatorios: `cobertura` del compilado; uno que falta es bloqueante.
//! - imagen: texto sobre cara (> 5 % de la caja) bloqueante; sobre cuerpo (> 25 %) resta; keyframes fuera
//!   del clip; negros a mitad del video (los del primer y último segundo son fundidos).
//! - ritmo: planos dentro de `ds.ritmo.plano_s` (1,2–5,5 s si no hay); cortes dentro de palabra;
//!   duración dentro de `ds.estructura.duracion_s` (o la del brief).
//! - lectura: rótulos y subtítulos ≤ 3 palabras/s y ≥ 1 s en pantalla.
//! - criterios: los de la biblia que se pudieron medir (`cine criterios`); uno que no cumple es bloqueante.
//! - estilo medido: veredictos de `referencias.py --comparar`; clon o misma maqueta es bloqueante y fija
//!   el techo de la originalidad que juzga el crítico.
use crate::catalogo::{cargar_ds, leer_json};
use crate::color::redondear;
use crate::criterios;
use crate::Args;
use serde_json::{json, Map, Value};
use std::path::Path;

pub const EJES_MEDIDOS: [&str; 6] = ["criterios", "obligatorios", "audio", "imagen", "ritmo", "lectura"];
pub const EJES_JUICIO: [&str; 3] = ["historia", "copy", "originalidad"];

struct Eje {
    nota: Option<f64>,
    evidencia: Vec<String>,
}

fn clamp(x: f64) -> f64 { redondear(x.clamp(1.0, 5.0), 1) }

fn por_fraccion(f: f64) -> f64 {
    if f >= 0.9 { 5.0 } else if f >= 0.75 { 4.0 } else if f >= 0.6 { 3.0 } else if f >= 0.4 { 2.0 } else { 1.0 }
}

fn f(v: &Value) -> Option<f64> { v.as_f64() }

pub struct Entrada {
    pub ds: Option<Value>,
    pub compilado: Option<Value>,
    pub verificacion: Option<Value>,
    pub entregas: Vec<(String, Value)>,
    pub biblia: Option<Value>,
    pub comparaciones: Vec<Value>,
}

pub fn puntuar(e: &Entrada) -> Value {
    let mut bloq: Vec<Value> = vec![];
    let mut arreglos: Vec<Value> = vec![];
    let mut sin_medir: Vec<String> = vec![];
    let mut ejes: Vec<(&str, Eje)> = vec![];
    let ds = e.ds.clone().unwrap_or(json!({}));

    // ---- audio ----
    let obj = f(&ds["audio"]["lufs"]).unwrap_or(-14.0);
    let tope = f(&ds["audio"]["pico_dbtp"]).unwrap_or(-1.0);
    let mut fuentes_audio: Vec<(String, Value)> = vec![];
    if let Some(v) = &e.verificacion { fuentes_audio.push(("mezcla".into(), v["audio"].clone())) }
    for (n, m) in &e.entregas { fuentes_audio.push((n.clone(), m["audio"].clone())) }
    let mut notas_audio = vec![];
    let mut ev = vec![];
    for (n, a) in &fuentes_audio {
        let (Some(l), p) = (f(&a["lufs"]), f(&a["pico_dbtp"])) else { continue };
        let d = l - obj;
        let pico_ok = p.map_or(true, |p| p <= tope + 1e-9);
        let mut s = if d.abs() <= 1.0 { 5.0 } else if d.abs() <= 1.5 { 4.0 } else if d.abs() <= 2.0 { 3.0 } else if d.abs() <= 3.0 { 2.0 } else { 1.0 };
        if !pico_ok { s = f64::min(s, if p.unwrap() <= tope + 0.5 { 3.0 } else { 2.0 }) }
        ev.push(format!("{n}: {l} LUFS (objetivo {obj} ± 1), pico {} dBTP (≤ {tope})", p.map_or("?".into(), |p| p.to_string())));
        if d.abs() > 1.0 {
            arreglos.push(json!({"eje": "audio", "que": format!("{n}: llevar la mezcla de {l} a {obj} LUFS ({:+.1} dB de ganancia)", -d)}));
        }
        if !pico_ok { arreglos.push(json!({"eje": "audio", "que": format!("{n}: limitar el pico a {tope} dBTP (ahora {})", p.unwrap())})) }
        if d.abs() > 2.0 || p.map_or(false, |p| p > 0.0) {
            bloq.push(json!({"eje": "audio", "que": format!("{n}: loudness fuera de {obj} ± 2 LUFS o pico sobre 0 dBTP"), "evidencia": ev.last()}));
        }
        notas_audio.push(s);
    }
    if notas_audio.is_empty() { sin_medir.push("audio: no hay loudness medido".into()) }
    ejes.push(("audio", Eje { nota: notas_audio.iter().cloned().reduce(f64::min), evidencia: ev }));

    // ---- obligatorios ----
    let cob = e.verificacion.as_ref().map(|v| v["cobertura"].clone()).filter(|c| c.as_object().map_or(false, |o| !o.is_empty()))
        .or_else(|| e.compilado.as_ref().map(|c| c["cobertura"].clone())).unwrap_or(Value::Null);
    if let Some(o) = cob.as_object().filter(|o| !o.is_empty()) {
        let falta: Vec<&String> = o.iter().filter(|(_, v)| **v == Value::Bool(false)).map(|(k, _)| k).collect();
        let ev = vec![format!("{} de {} obligatorios en pantalla", o.len() - falta.len(), o.len())];
        for k in &falta {
            bloq.push(json!({"eje": "obligatorios", "que": format!("falta el obligatorio «{k}»"), "evidencia": "cobertura del compilado"}));
            arreglos.push(json!({"eje": "obligatorios", "que": format!("poner «{k}» en un rótulo o subtítulo de un plano donde se diga")}));
        }
        ejes.push(("obligatorios", Eje { nota: Some(clamp(5.0 - 2.0 * falta.len() as f64)), evidencia: ev }));
    } else {
        ejes.push(("obligatorios", Eje { nota: None, evidencia: vec!["sin obligatorios (o sin compilado)".into()] }));
    }

    // ---- imagen ----
    let mut s = 5.0;
    let mut ev = vec![];
    let mut medida_imagen = false;
    if let Some(v) = &e.verificacion {
        let tc = &v["textos_vs_caras"];
        if tc["medido"] == true {
            medida_imagen = true;
            for c in tc["choques"].as_array().into_iter().flatten() {
                let (cara, pers) = (f(&c["cara"]).unwrap_or(0.0), f(&c["persona"]).unwrap_or(0.0));
                let txt = c["texto"].as_str().unwrap_or("");
                let t = f(&c["t"]).unwrap_or(0.0);
                if cara > 0.05 {
                    s -= 2.0;
                    bloq.push(json!({"eje": "imagen", "que": format!("[{t:.1} s] «{txt}» tapa una cara ({:.0} %)", cara * 100.0), "evidencia": "hoja_popups_sin_textos.jpg"}));
                    arreglos.push(json!({"eje": "imagen", "que": format!("[{t:.1} s] mover «{txt}» a la zona libre (quitar `pos` o cambiar `variante`)")}));
                } else if pers > 0.25 {
                    s -= 0.5;
                    ev.push(format!("[{t:.1} s] «{txt}» roza un cuerpo ({:.0} %)", pers * 100.0));
                }
            }
            ev.push(format!("{} choques de texto en {} momentos medidos", tc["choques"].as_array().map_or(0, |a| a.len()), tc["momentos_medidos"]));
        } else if !tc.is_null() {
            sin_medir.push("imagen: textos frente a caras sin medir (verificacion.textos_vs_caras.medido = false)".into());
        }
        if let Some(n) = v["keyframes"]["n_fuera"].as_u64() {
            medida_imagen = true;
            if n > 0 {
                s -= (n as f64).min(2.0);
                ev.push(format!("{n} keyframes fuera del rango del clip"));
                arreglos.push(json!({"eje": "imagen", "que": format!("recolocar {n} keyframes fuera del clip (verificacion.keyframes.fuera_de_rango)")}));
            }
        }
    }
    let flash_es_transicion = ds["transiciones"].get("flash").is_some();
    // cada entregable se puntúa aparte y cuenta el peor: el mismo negro en 4:5 y 9:16 resta una vez
    let base = s;
    for (n, m) in &e.entregas {
        medida_imagen = true;
        let mut se = base;
        let dur = f(&m["duracion_s"]).unwrap_or(0.0);
        for ng in m["negros"].as_array().into_iter().flatten() {
            let (a, b) = (f(&ng[0]).unwrap_or(0.0), f(&ng[1]).unwrap_or(0.0));
            if a > 1.0 && b < dur - 1.0 {
                se -= 1.0;
                ev.push(format!("{n}: negro de {a}–{b} s a mitad del video"));
                arreglos.push(json!({"eje": "imagen", "que": format!("{n}: quitar el negro de {a}–{b} s (hueco entre planos o fundido de más), salvo que sea un paso de la transición firma")}));
            }
        }
        let fl = m["flashes"].as_array().map_or(0, |a| a.len());
        if fl > 0 && !flash_es_transicion {
            ev.push(format!("{n}: {fl} fotogramas casi blancos (el DS no tiene transición flash)"));
            se -= 0.5;
        }
        s = s.min(se);
    }
    ejes.push(("imagen", Eje { nota: medida_imagen.then(|| clamp(s)), evidencia: ev }));

    // ---- ritmo ----
    let rango = ds["ritmo"]["plano_s"].as_array().filter(|a| a.len() == 2).map(|a| (f(&a[0]).unwrap_or(1.2), f(&a[1]).unwrap_or(5.5))).unwrap_or((1.2, 5.5));
    let mut planos: Vec<f64> = vec![];
    let mut origen = "";
    if let Some(c) = &e.compilado {
        planos = c["segmentos"].as_array().into_iter().flatten().filter(|s| s["tipo"] == "video").filter_map(|s| f(&s["dur"])).collect();
        origen = "compiled.segmentos";
    }
    if planos.is_empty() {
        for (_, m) in &e.entregas { planos.extend(m["planos_s"].as_array().into_iter().flatten().filter_map(f)) }
        origen = "cortes por cambio de escena del render";
    }
    let mut ev = vec![];
    let mut nota_ritmo = None;
    if !planos.is_empty() {
        let dentro = planos.iter().filter(|d| **d >= rango.0 - 0.05 && **d <= rango.1 + 0.05).count();
        let fr = dentro as f64 / planos.len() as f64;
        let mut s = por_fraccion(fr);
        ev.push(format!("{dentro} de {} planos en {}–{} s ({origen})", planos.len(), rango.0, rango.1));
        let largos: Vec<String> = planos.iter().filter(|d| **d > rango.1 + 0.05).map(|d| format!("{d:.1}")).collect();
        if !largos.is_empty() { arreglos.push(json!({"eje": "ritmo", "que": format!("acortar o partir los planos de {} s (máximo {} s en este DS)", largos.join(", "), rango.1)})) }
        if let Some(v) = &e.verificacion {
            let dp = v["cortes_en_palabra"]["dentro_de_palabra"].as_array().cloned().unwrap_or_default();
            if !dp.is_empty() {
                s -= dp.len() as f64;
                ev.push(format!("{} bordes de diálogo dentro de una palabra", dp.len()));
                for d in dp.iter().take(3) {
                    arreglos.push(json!({"eje": "ritmo", "que": format!("[{} s] corte dentro de «{}» ({}): mover el borde a la pausa", d["seq_s"], d["palabra"].as_str().unwrap_or(""), d["borde"].as_str().unwrap_or(""))}));
                }
                if dp.len() > 2 { bloq.push(json!({"eje": "ritmo", "que": format!("{} cortes a mitad de palabra", dp.len()), "evidencia": "verificacion.cortes_en_palabra"})) }
            }
            if v["cortes_en_palabra"]["medido"] == false { sin_medir.push("ritmo: cortes en palabra sin medir (faltan palabras.json)".into()) }
        }
        nota_ritmo = Some(clamp(s));
    } else {
        sin_medir.push("ritmo: no hay planos (ni compilado ni cortes del render)".into());
    }
    // duración total frente al DS
    if let Some(dr) = ds["estructura"]["duracion_s"].as_array().filter(|a| a.len() == 2) {
        let (a, b) = (f(&dr[0]).unwrap_or(0.0), f(&dr[1]).unwrap_or(f64::MAX));
        let mut durs: Vec<(String, f64)> = vec![];
        if let Some(v) = &e.verificacion { if let Some(d) = f(&v["duracion_s"]) { durs.push(("montaje".into(), d)) } }
        if durs.is_empty() { for (n, m) in &e.entregas { if let Some(d) = f(&m["duracion_s"]) { durs.push((n.clone(), d)) } } }
        for (n, d) in durs {
            ev.push(format!("{n}: {d} s (DS: {a}–{b} s)"));
            if d < a * 0.9 || d > b * 1.1 {
                nota_ritmo = nota_ritmo.map(|x| clamp(x - 1.0));
                arreglos.push(json!({"eje": "ritmo", "que": format!("{n}: la duración {d} s queda fuera de {a}–{b} s del DS: quitar o añadir bloques enteros")}));
            }
        }
    }
    ejes.push(("ritmo", Eje { nota: nota_ritmo, evidencia: ev }));

    // ---- lectura ----
    if let Some(c) = &e.compilado {
        let mut total = 0;
        let mut mal = vec![];
        // rótulos: ≤ 3 palabras/s y ≥ 1 s (el eco es un destello deliberado de una cifra y no cuenta);
        // subtítulos: van con la voz, solo ≤ 3 palabras/s
        let rotulos = c["textos"].as_array().into_iter().flatten().filter(|t| t["rol"] != "eco").map(|t| (t, true));
        let subs = c["subtitulos"].as_array().into_iter().flatten().map(|t| (t, false));
        for (t, es_rotulo) in rotulos.chain(subs) {
            let (Some(txt), Some(d)) = (t["texto"].as_str(), f(&t["dur"])) else { continue };
            let pal = txt.split_whitespace().count();
            if pal == 0 { continue }
            total += 1;
            let ps = pal as f64 / d.max(0.01);
            if ps > 3.0 + 1e-9 || (es_rotulo && d < 1.0 - 1e-9) {
                mal.push(format!("[{:.1} s] «{}» {pal} palabras en {d:.2} s", f(&t["start"]).unwrap_or(0.0), txt.chars().take(40).collect::<String>()));
            }
        }
        if total > 0 {
            let fr = 1.0 - mal.len() as f64 / total as f64;
            let mut ev = vec![format!("{} de {total} textos legibles (≤ 3 palabras/s y ≥ 1 s)", total - mal.len())];
            for m in mal.iter().take(3) { arreglos.push(json!({"eje": "lectura", "que": format!("{m}: alargarlo o recortar el texto")})) }
            ev.extend(mal.into_iter().take(5));
            ejes.push(("lectura", Eje { nota: Some(por_fraccion(fr)), evidencia: ev }));
        }
    }

    // ---- criterios de la biblia ----
    let mut para_ia_criterios: Vec<Value> = vec![];
    if let Some(b) = &e.biblia {
        let mut entregas = e.entregas.clone();
        if let Some(v) = &e.verificacion { entregas.push(("montaje".into(), criterios::montaje(v.clone(), e.compilado.as_ref()))) }
        let r = criterios::comprobar(b, &entregas);
        let mut no = 0;
        let mut medidos = 0;
        for c in r["criterios"].as_array().into_iter().flatten() {
            match c["estado"].as_str().unwrap_or("") {
                "no cumple" => {
                    no += 1;
                    medidos += 1;
                    let ev: Vec<String> = c["evidencia"].as_array().into_iter().flatten().filter_map(|x| x.as_str()).filter(|x| x.ends_with('✗')).map(String::from).collect();
                    bloq.push(json!({"eje": "criterios", "que": format!("criterio {} no cumple: {}", c["id"].as_str().unwrap_or(""), c["que"].as_str().unwrap_or("")), "evidencia": ev}));
                    arreglos.push(json!({"eje": "criterios", "que": format!("{}: {}", c["id"].as_str().unwrap_or(""), ev.join("; "))}));
                }
                "cumple" => medidos += 1,
                "cumple en lo medido" => {
                    medidos += 1;
                    para_ia_criterios.push(json!({"id": c["id"], "que": c["que"], "falta": c["falta"], "medido": c["evidencia"]}));
                }
                _ => para_ia_criterios.push(json!({"id": c["id"], "que": c["que"], "como": b["criterios"].as_array().and_then(|l| l.iter().find(|x| x["id"] == c["id"])).map(|x| x["como"].clone())})),
            }
        }
        let ev = vec![format!("{} cumple, {} no cumple, {} para el crítico", r["resumen"]["cumple"], r["resumen"]["no_cumple"], para_ia_criterios.len())];
        ejes.push(("criterios", Eje { nota: (medidos > 0).then(|| clamp(5.0 - 2.0 * no as f64)), evidencia: ev }));
    }

    // ---- estilo medido (referencias.py --comparar) ----
    let antis: Vec<String> = e.biblia.as_ref().map(|b| b["anti_referencias"].as_array().into_iter().flatten().filter_map(|x| x.as_str().map(String::from).or_else(|| x["archivo"].as_str().map(String::from))).collect()).unwrap_or_default();
    let mut techo_orig: f64 = 5.0;
    let mut estilo_ev = vec![];
    for c in &e.comparaciones {
        let v = c["veredicto"].as_str().unwrap_or("");
        let r = c["ref"].as_str().unwrap_or("");
        let foto = c["foto"].as_str().map(|x| Path::new(x).file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default()).unwrap_or_default();
        let foto = foto.as_str();
        let base = Path::new(r).file_name().map(|x| x.to_string_lossy().to_string()).unwrap_or_default();
        let anti = antis.iter().any(|a| a.contains(&base) || base.contains(a.as_str()));
        estilo_ev.push(format!("{foto} frente a {base}{}: {v}", if anti { " (anti-referencia)" } else { "" }));
        if v.starts_with("clon probable") || v.starts_with("misma maqueta") || (anti && c["reproduce_estilo"] == true) {
            techo_orig = techo_orig.min(2.0);
            bloq.push(json!({"eje": "originalidad", "que": format!("{foto}: {v} frente a {base}"), "evidencia": "referencias.py --comparar"}));
            let aj: Vec<String> = c["ajustar"].as_array().into_iter().flatten().take(3).map(|x| format!("{} ({})", x["metrica"].as_str().unwrap_or(""), x["sentido"].as_str().unwrap_or(""))).collect();
            arreglos.push(json!({"eje": "originalidad", "que": format!("{foto}: cambiar la maqueta frente a {base}{}", if aj.is_empty() { String::new() } else { format!("; mover {}", aj.join(", ")) })}));
        } else if v == "estilo distinto" && !anti {
            techo_orig = techo_orig.min(3.0);
        }
    }

    // ---- salida ----
    let mut punt = Map::new();
    let mut det = Map::new();
    for (k, x) in &ejes {
        punt.insert(k.to_string(), x.nota.map_or(Value::Null, |n| json!(n)));
        det.insert(k.to_string(), json!(x.evidencia));
        if x.nota.is_none() && !sin_medir.iter().any(|s| s.starts_with(&format!("{k}:"))) && *k != "obligatorios" {
            sin_medir.push(format!("{k}: sin datos"));
        }
    }
    json!({"puntuaciones": punt, "detalle": det, "bloqueantes": bloq, "arreglos_medidos": arreglos, "sin_medir": sin_medir,
        "ejes_medidos": EJES_MEDIDOS, "para_ia": {"ejes": EJES_JUICIO, "techos": {"originalidad": techo_orig}, "estilo_medido": estilo_ev,
                    "criterios_de_juicio": para_ia_criterios}})
}

fn lista(a: &Args, k: &str) -> Vec<String> {
    a.opt(k).map(|s| s.split(',').map(|x| x.trim().to_string()).filter(|x| !x.is_empty()).collect()).unwrap_or_default()
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let leer = |k: &str| -> Result<Option<Value>, String> { a.opt(k).map(|p| leer_json(Path::new(p))).transpose() };
    let compilado = leer("compiled")?;
    let ds = match a.opt("ds").map(String::from).or_else(|| compilado.as_ref().and_then(|c| c["ds_dir"].as_str().or(c["ds"].as_str()).map(String::from))) {
        Some(id) => Some(cargar_ds(&id)?.0),
        None => None,
    };
    let mut comparaciones = vec![];
    for p in lista(a, "comparaciones") {
        let pp = Path::new(&p);
        if pp.is_dir() {
            let mut fs: Vec<_> = std::fs::read_dir(pp).map_err(|e| e.to_string())?.flatten().map(|e| e.path()).filter(|x| x.extension().map_or(false, |e| e == "json")).collect();
            fs.sort();
            for f in fs { comparaciones.push(leer_json(&f)?) }
        } else {
            comparaciones.push(leer_json(pp)?);
        }
    }
    let e = Entrada { ds, compilado, verificacion: leer("verificacion")?, entregas: criterios::cargar_medidas(a)?, biblia: leer("biblia")?, comparaciones };
    let r = puntuar(&e);
    let txt = serde_json::to_string_pretty(&r).unwrap();
    match a.opt("out") { Some(o) => { std::fs::write(o, &txt).map_err(|e| format!("{o}: {e}"))?; println!("{o}") } None => println!("{txt}") }
    Ok(0)
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn anclas() {
        let ds = json!({"audio": {"lufs": -14, "pico_dbtp": -1}, "ritmo": {"plano_s": [1.2, 5.5]}, "estructura": {"duracion_s": [45, 60]}, "transiciones": {}});
        let comp = json!({"cobertura": {"SageMaker": true, "100 USD": false},
            "segmentos": [{"tipo": "video", "dur": 2.0}, {"tipo": "video", "dur": 3.0}, {"tipo": "video", "dur": 8.0}, {"tipo": "tarjeta", "dur": 9.0}],
            "textos": [{"texto": "hola", "start": 1.0, "dur": 1.5}, {"texto": "una frase demasiado larga para leer", "start": 4.0, "dur": 1.0}]});
        let ver = json!({"duracion_s": 50.0, "audio": {"lufs": -16.6, "pico_dbtp": -0.4},
            "textos_vs_caras": {"medido": true, "momentos_medidos": 3, "choques": [{"texto": "X", "t": 3.0, "cara": 0.3, "persona": 0.5}]},
            "keyframes": {"n_fuera": 0}, "cortes_en_palabra": {"medido": true, "dentro_de_palabra": [{"seq_s": 4.0, "palabra": "datos", "borde": "salida"}]}});
        let r = puntuar(&Entrada { ds: Some(ds), compilado: Some(comp), verificacion: Some(ver), entregas: vec![], biblia: None, comparaciones: vec![] });
        let p = &r["puntuaciones"];
        assert_eq!(p["audio"], json!(2.0));      // −2,6 LU y pico sobre −1
        assert_eq!(p["obligatorios"], json!(3.0));
        assert_eq!(p["imagen"], json!(3.0));
        assert_eq!(p["ritmo"], json!(2.0));       // 2 de 3 planos dentro (0,67 → 3) − 1 corte en palabra
        assert_eq!(p["lectura"], json!(2.0));
        assert!(r["bloqueantes"].as_array().unwrap().len() >= 3);
    }
}
