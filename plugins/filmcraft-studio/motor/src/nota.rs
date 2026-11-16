//! `cine nota`: junta los ejes medidos (`cine puntuar`) y el juicio del crítico, aplica los techos y da
//! la nota ponderada, el veredicto (publicable / publicable con arreglos / no publicable), los 5 arreglos
//! y, con `--mejor`, si la versión nueva es Mejora, Regresión o Empate frente a la mejor hasta ahora.
//! El A/B a ciegas solo se pide cuando la diferencia de nota es ambigua (|Δ| < 0,30) y no hay un
//! bloqueante nuevo (que ya es Regresión).
use crate::catalogo::leer_json;
use crate::color::redondear;
use crate::Args;
use serde_json::{json, Map, Value};
use std::path::Path;

pub const PESOS: [(&str, f64); 9] = [
    ("criterios", 3.0), ("obligatorios", 3.0), ("audio", 2.0), ("imagen", 2.0), ("ritmo", 2.0), ("lectura", 1.0),
    ("historia", 3.0), ("copy", 2.0), ("originalidad", 3.0),
];
pub const ZONA_AB: f64 = 0.30;

fn texto(v: &Value) -> String {
    v.as_str().map(String::from).unwrap_or_else(|| if v.is_null() { String::new() } else { v.to_string() })
}

fn preferida(ab: &Value, clave: Option<&str>) -> Result<Value, String> {
    if !ab["preferida_version"].is_null() { return Ok(ab["preferida_version"].clone()) }
    let letra = ab["preferida"].as_str().unwrap_or("");
    if letra == "empate" { return Ok(json!("empate")) }
    let c = std::fs::read_to_string(clave.ok_or("el A/B dice A o B: falta --clave")?).map_err(|e| e.to_string())?;
    for par in c.split_whitespace() {
        if let Some((l, v)) = par.split_once('=') { if l == letra { return Ok(json!(v)) } }
    }
    Err(format!("la clave no tiene la letra «{letra}»"))
}

/// `cine ab --nueva DIR --anterior DIR --out DIR/ab`: copia las hojas (*.jpg, *.png) como A-*/B-* al
/// azar y deja la clave en `clave-ab.txt` junto a la carpeta, fuera de lo que ve el crítico.
pub fn preparar_ab(a: &Args) -> Result<i32, String> {
    let (nueva, anterior, out) = (a.req("nueva")?, a.req("anterior")?, std::path::PathBuf::from(a.req("out")?));
    std::fs::create_dir_all(&out).map_err(|e| e.to_string())?;
    let azar = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.subsec_nanos()).unwrap_or(0) ^ std::process::id();
    let (da, db) = if azar % 2 == 0 { (nueva, anterior) } else { (anterior, nueva) };
    let mut n = 0;
    for (letra, dir) in [("A", da), ("B", db)] {
        let mut fs: Vec<_> = std::fs::read_dir(dir).map_err(|e| format!("{dir}: {e}"))?.flatten().map(|e| e.path()).collect();
        fs.sort();
        for p in fs {
            let ext = p.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
            if !["jpg", "jpeg", "png"].contains(&ext.as_str()) { continue }
            let nombre = p.file_name().unwrap().to_string_lossy().to_string();
            std::fs::copy(&p, out.join(format!("{letra}-{nombre}"))).map_err(|e| e.to_string())?;
            n += 1;
        }
    }
    let clave = out.parent().unwrap_or(&out).join("clave-ab.txt");
    let txt = if da == nueva { "A=nueva B=anterior" } else { "A=anterior B=nueva" };
    std::fs::write(&clave, format!("{txt}\n")).map_err(|e| e.to_string())?;
    println!("{}", json!({"hojas": n, "carpeta": out.display().to_string(), "clave": clave.display().to_string()}));
    Ok(0)
}

pub fn nota(ejes: &Value, juicio: Option<&Value>) -> Value {
    let mut p: Map<String, Value> = ejes["puntuaciones"].as_object().cloned().unwrap_or_default();
    let mut bloq: Vec<String> = ejes["bloqueantes"].as_array().into_iter().flatten().map(|b| format!("{}: {}", texto(&b["eje"]), texto(&b["que"]))).collect();
    let mut arreglos: Vec<String> = ejes["arreglos_medidos"].as_array().into_iter().flatten().map(|a| format!("[{}] {}", texto(&a["eje"]), texto(&a["que"]))).collect();
    let mut no_tocar = vec![];
    if let Some(j) = juicio {
        let techo = ejes["para_ia"]["techos"]["originalidad"].as_f64().unwrap_or(5.0);
        let pj = &j["puntuaciones"];
        p.insert("historia".into(), pj["historia"].clone());
        p.insert("copy".into(), pj["copy"].clone());
        let mut orig = pj["originalidad"].as_f64();
        match j["veredicto_estilo"].as_str().unwrap_or("") {
            "clon" => { orig = orig.map(|x| x.min(2.0)); bloq.push("originalidad: el crítico ve un clon de la referencia".into()) }
            "correcto pero genérico" => orig = orig.map(|x| x.min(3.0)),
            _ => {}
        }
        p.insert("originalidad".into(), orig.map(|x| json!(x.min(techo))).unwrap_or(Value::Null));
        // criterios de juicio: uno que no cumple es bloqueante (son de aceptación) y baja el eje
        let mut cr = p.get("criterios").and_then(|v| v.as_f64());
        for c in j["criterios"].as_array().into_iter().flatten().filter(|c| c["estado"] == "no cumple") {
            cr = Some(cr.unwrap_or(5.0).min(2.0));
            bloq.push(format!("criterios: {} no cumple (juicio): {}", texto(&c["id"]), texto(&c["evidencia"])));
        }
        if let Some(c) = cr { p.insert("criterios".into(), json!(c)); }
        bloq.extend(j["bloqueantes"].as_array().into_iter().flatten().map(|b| format!("juicio: {}", texto(&b["que"]))));
        arreglos.extend(j["arreglos"].as_array().into_iter().flatten().map(|a| if a.is_string() { texto(a) } else { format!("[{}] {}", texto(&a["eje"]), texto(&a["que"])) }));
        no_tocar = j["no_tocar"].as_array().cloned().unwrap_or_default();
    }
    let (mut s, mut w) = (0.0, 0.0);
    let mut bajos = vec![];
    let mut tabla = Map::new();
    for (k, peso) in PESOS {
        let v = p.get(k).cloned().unwrap_or(Value::Null);
        if let Some(x) = v.as_f64() {
            s += x * peso;
            w += peso;
            if x < 4.0 { bajos.push(format!("{k}={x}")) }
        }
        tabla.insert(k.into(), v);
    }
    let n = (w > 0.0).then(|| redondear(s / w, 2));
    let veredicto = if !bloq.is_empty() { "no publicable" } else if n.map_or(false, |n| n >= 4.2) && bajos.is_empty() { "publicable" } else { "publicable con arreglos" };
    let faltan_juicio = juicio.is_none();
    // primero los arreglos de los bloqueantes medidos, después los del crítico; 5 sin repetir
    let mut vistos = std::collections::HashSet::new();
    let cinco: Vec<String> = arreglos.into_iter().filter(|a| vistos.insert(a.clone())).take(5).collect();
    json!({"nota": n, "ejes": tabla, "por_debajo_de_4": bajos, "bloqueantes": bloq, "veredicto": veredicto,
        "arreglos": cinco, "no_tocar": no_tocar, "sin_medir": ejes["sin_medir"],
        "aviso": if faltan_juicio { json!("sin --juicio: historia, copy y originalidad no cuentan") } else { Value::Null }})
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let ejes = leer_json(Path::new(a.req("ejes")?))?;
    let juicio = a.opt("juicio").map(|p| leer_json(Path::new(p))).transpose()?;
    let mut out = nota(&ejes, juicio.as_ref());
    let ab = match a.opt("ab") { Some(p) => preferida(&leer_json(Path::new(p))?, a.opt("clave"))?, None => Value::Null };
    if let (Some(mejor), Some(n)) = (a.opt("mejor").and_then(|x| x.parse::<f64>().ok()), out["nota"].as_f64()) {
        let d = redondear(n - mejor, 2);
        let ab_s = ab.as_str().unwrap_or("");
        let bloq = !out["bloqueantes"].as_array().map_or(true, |b| b.is_empty());
        let bloq_ant = a.opt("bloq-anterior").map(|x| matches!(x, "si" | "sí" | "1" | "true"));
        let bloqueante_nuevo = bloq_ant == Some(false) && bloq;
        let ab_necesario = ab.is_null() && d.abs() < ZONA_AB && !bloqueante_nuevo;
        let clase = if bloqueante_nuevo || d <= -ZONA_AB || (d < 0.0 && ab_s == "anterior") { "Regresión" }
            else if (d >= ZONA_AB && ab_s != "anterior") || (d >= 0.15 && ab_s == "nueva") { "Mejora" }
            else if ab_necesario { "pendiente de A/B" }
            else { "Empate" };
        let mejor_v = match clase {
            "Mejora" => "nueva",
            "Regresión" => "anterior",
            "pendiente de A/B" => "pendiente",
            _ => match bloq_ant {
                Some(b) if b != bloq => if bloq { "anterior" } else { "nueva" },
                _ => if ab_s == "nueva" { "nueva" } else { "anterior" },
            },
        };
        out["delta"] = json!(d);
        out["ab"] = ab;
        out["ab_necesario"] = json!(ab_necesario);
        out["clase"] = json!(clase);
        out["mejor"] = json!(mejor_v);
    }
    println!("{}", serde_json::to_string_pretty(&out).unwrap());
    Ok(if out["veredicto"] == "no publicable" { 1 } else { 0 })
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn techos_y_veredicto() {
        let ejes = json!({"puntuaciones": {"criterios": 5, "obligatorios": 5, "audio": 5, "imagen": 5, "ritmo": 4, "lectura": 5},
            "bloqueantes": [], "arreglos_medidos": [{"eje": "ritmo", "que": "acortar el plano de 7 s"}],
            "para_ia": {"techos": {"originalidad": 2.0}}});
        let j = json!({"puntuaciones": {"historia": 5, "copy": 4, "originalidad": 5}, "veredicto_estilo": "distinto",
            "criterios": [], "bloqueantes": [], "arreglos": ["cambiar el gancho"], "no_tocar": []});
        let r = nota(&ejes, Some(&j));
        assert_eq!(r["ejes"]["originalidad"], json!(2.0));   // techo medido: clon o misma maqueta
        assert_eq!(r["veredicto"], "publicable con arreglos");
        assert_eq!(r["arreglos"][0], "[ritmo] acortar el plano de 7 s");
        let r = nota(&json!({"puntuaciones": {"audio": 5}, "bloqueantes": [{"eje": "audio", "que": "x"}]}), None);
        assert_eq!(r["veredicto"], "no publicable");
    }
}
