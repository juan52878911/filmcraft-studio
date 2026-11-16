//! cine — motor determinista de filmcraft-studio.
mod catalogo;
mod color;
mod criterios;
mod elegir;
mod esquema;
mod imagen;
mod medir;
mod nota;
mod patron;
mod puntuar;
mod validar;

use std::collections::HashMap;

pub struct Args {
    valores: HashMap<String, String>,
    banderas: Vec<String>,
    pub pos: Vec<String>,
}
impl Args {
    pub fn opt(&self, k: &str) -> Option<&str> { self.valores.get(k).map(|s| s.as_str()) }
    pub fn req(&self, k: &str) -> Result<&str, String> { self.opt(k).ok_or(format!("falta --{k}")) }
    pub fn flag(&self, k: &str) -> bool { self.banderas.iter().any(|b| b == k) }
}

/// Opciones que nunca llevan valor (así `--json ds` no se come el posicional).
const BANDERAS: [&str; 6] = ["todos", "json", "estricto", "md", "solo-ids", "sin-color"];

const AYUDA: &str = "cine — motor determinista de filmcraft-studio

USO
  cine validar-ds <id|carpeta|ds.json> | --todos  [--json] [--estricto]
  cine elegir-ds  [--flyer F | --paleta \"#a,#b\"] [--ruta R | --rutas-json '[..]'] [--para todos|camara|promo] [--json]
  cine medir-video VIDEO [--out medidas.json] [--umbral 0.3]   (ffprobe + ebur128 + cortes + negros/flashes)
  cine criterios  --biblia biblia.json [--medidas a.json,b.json] [--verificacion verificacion.json --compiled compiled.json] [--md]
  cine puntuar    [--ds id] [--compiled compiled.json] [--verificacion v.json] [--medidas a.json,b.json]
                  [--biblia biblia.json] [--comparaciones dir|a.json,b.json] [--out ejes.json]
  cine nota       --ejes ejes.json [--juicio juicio.json] [--mejor 3.9 --bloq-anterior si|no] [--ab ab.json --clave clave-ab.txt]
  cine ab         --nueva vN/hojas --anterior vM/hojas --out vN/ab      (hojas A/B al azar; la clave queda fuera de ab/)
  cine version

Códigos de salida: 0 bien; 1 error, comprobación fallida, criterio que no cumple o «no publicable».";

pub fn analizar(args: Vec<String>) -> (String, Args) {
    let mut it = args.into_iter();
    let cmd = it.next().unwrap_or_default();
    let resto: Vec<String> = it.collect();
    let (mut valores, mut banderas, mut pos) = (HashMap::new(), vec![], vec![]);
    let mut i = 0;
    while i < resto.len() {
        if let Some(k) = resto[i].strip_prefix("--") {
            if let Some((k, v)) = k.split_once('=') {
                valores.insert(k.to_string(), v.to_string());
            } else if !BANDERAS.contains(&k) && i + 1 < resto.len() && !resto[i + 1].starts_with("--") {
                valores.insert(k.to_string(), resto[i + 1].clone());
                i += 1;
            } else {
                banderas.push(k.to_string());
            }
        } else {
            pos.push(resto[i].clone());
        }
        i += 1;
    }
    (cmd, Args { valores, banderas, pos })
}

fn main() {
    let (cmd, a) = analizar(std::env::args().skip(1).collect());
    let r = match cmd.as_str() {
        "validar-ds" => validar::ejecutar(&a),
        "elegir-ds" => elegir::ejecutar(&a),
        "medir-video" => medir::ejecutar(&a),
        "criterios" => criterios::ejecutar(&a),
        "puntuar" => puntuar::ejecutar(&a),
        "nota" => nota::ejecutar(&a),
        "ab" => nota::preparar_ab(&a),
        "version" | "--version" | "-V" => { println!("cine {}", env!("CARGO_PKG_VERSION")); Ok(0) }
        _ => { println!("{AYUDA}"); Ok(if matches!(cmd.as_str(), "" | "ayuda" | "--help" | "-h") { 0 } else { 1 }) }
    };
    match r {
        Ok(c) => std::process::exit(c),
        Err(e) => { eprintln!("cine: {e}"); std::process::exit(1) }
    }
}
