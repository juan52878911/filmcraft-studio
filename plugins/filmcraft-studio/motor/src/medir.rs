//! `cine medir-video`: medidas de un video renderizado con ffprobe y ffmpeg (formato, loudness con curva
//! por segundo, cortes por cambio de escena, planos y negros). Las cifras salen de ffmpeg; aquí solo se
//! lanzan los procesos y se leen sus salidas, como hacían common.ffprobe/loudness y referencias.cortes.
use crate::color::redondear;
use crate::Args;
use serde_json::{json, Value};
use std::process::Command;

fn ejecutar_cmd(bin: &str, args: &[&str]) -> Result<(String, String, bool), String> {
    let o = Command::new(bin).args(args).output().map_err(|e| format!("no se pudo ejecutar {bin}: {e}"))?;
    Ok((String::from_utf8_lossy(&o.stdout).into(), String::from_utf8_lossy(&o.stderr).into(), o.status.success()))
}

/// Números tras `clave` en el texto (como re.findall(r"clave\s*(-?[\d.]+)")).
fn numeros_tras(t: &str, clave: &str) -> Vec<f64> {
    let mut out = vec![];
    let mut resto = t;
    while let Some(i) = resto.find(clave) {
        resto = &resto[i + clave.len()..];
        let s = resto.trim_start();
        let n: String = s.chars().take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-').collect();
        if let Ok(x) = n.parse::<f64>() { out.push(x) }
    }
    out
}

fn tasa(r: &str) -> Option<f64> {
    let (n, d) = r.split_once('/')?;
    let (n, d): (f64, f64) = (n.parse().ok()?, d.parse().ok()?);
    if d == 0.0 { None } else { Some(redondear(n / d, 3)) }
}

pub fn ffprobe(video: &str) -> Result<Value, String> {
    let (out, err, ok) = ejecutar_cmd("ffprobe", &["-v", "error", "-show_entries",
        "stream=codec_type,width,height,r_frame_rate,avg_frame_rate:stream_side_data=rotation:format=duration,size",
        "-of", "json", video])?;
    let j: Value = serde_json::from_str(&out).unwrap_or(json!({}));
    let dur: f64 = j["format"]["duration"].as_str().and_then(|s| s.parse().ok()).unwrap_or(0.0);
    if !ok || dur <= 0.0 { return Err(format!("ffprobe no da duración para {video}: {}", err.trim())) }
    let streams = j["streams"].as_array().cloned().unwrap_or_default();
    let v = streams.iter().find(|s| s["codec_type"] == "video").cloned().unwrap_or(json!({}));
    let mut rot = 0i64;
    for sd in v["side_data_list"].as_array().into_iter().flatten() {
        if let Some(r) = sd["rotation"].as_i64() { rot = r }
    }
    let (mut w, mut h) = (v["width"].clone(), v["height"].clone());
    if [90, -90, 270, -270].contains(&rot) && !w.is_null() { std::mem::swap(&mut w, &mut h) }
    let bytes: Option<f64> = j["format"]["size"].as_str().and_then(|s| s.parse().ok());
    Ok(json!({"dur": dur, "w": w, "h": h, "rot": rot,
        "fps": v["r_frame_rate"].as_str().and_then(tasa), "fps_media": v["avg_frame_rate"].as_str().and_then(tasa),
        "audio": streams.iter().any(|s| s["codec_type"] == "audio"),
        "peso_mb": bytes.map(|b| redondear(b / 1_048_576.0, 2))}))
}

/// Curva por segundo como common.parse_ebur128: S del primer fotograma de cada segundo o, mientras S
/// aún no vale (−120,7), la media energética de M en ese segundo; −70 para silencio.
pub fn curva_ebur(stdout: &str) -> Vec<f64> {
    let val = |x: &str| -> Option<f64> { if x.contains("inf") { None } else { x.parse::<f64>().ok().filter(|v| *v > -70.0) } };
    let mut segs: std::collections::BTreeMap<i64, (Option<Option<f64>>, Vec<f64>)> = Default::default();
    let mut t: Option<i64> = None;
    for linea in stdout.lines() {
        if let Some(i) = linea.find("pts_time:") {
            let n: String = linea[i + 9..].chars().take_while(|c| c.is_ascii_digit() || *c == '.').collect();
            if let Ok(x) = n.parse::<f64>() {
                t = Some(x as i64);
                segs.entry(x as i64).or_insert((None, vec![]));
            }
            continue;
        }
        let l = linea.trim_start();
        let Some(r) = l.strip_prefix("lavfi.r128.") else { continue };
        let Some(t) = t else { continue };
        let (k, v) = match r.split_once('=') { Some(x) => x, None => continue };
        let seg = segs.get_mut(&t).unwrap();
        match k {
            "S" => { if seg.0.is_none() { seg.0 = Some(val(v)) } }
            "M" => { if let Some(x) = val(v) { seg.1.push(x) } }
            _ => {}
        }
    }
    segs.values().map(|(s, ms)| {
        let mut sv = s.flatten();
        if sv.is_none() && !ms.is_empty() {
            sv = Some(10.0 * (crate::color::suma(ms.iter().map(|x| 10f64.powf(x / 10.0))) / ms.len() as f64).log10());
        }
        match sv { Some(x) if x > -70.0 => redondear(x, 1), _ => -70.0 }
    }).collect()
}

pub fn loudness(video: &str, curva: bool) -> Result<Value, String> {
    let af = if curva { "ebur128=peak=true:metadata=1,ametadata=print:file=-" } else { "ebur128=peak=true" };
    let (out, err, _) = ejecutar_cmd("ffmpeg", &["-hide_banner", "-nostats", "-i", video, "-vn", "-af", af, "-f", "null", "-"])?;
    let i = numeros_tras(&err, "I:");
    let lra = numeros_tras(&err, "LRA:");
    let pico = numeros_tras(&err, "Peak:");
    let Some(l) = i.last() else { return Err(format!("ebur128 no dio loudness para {video}")) };
    let mut v = json!({"lufs": l, "lra": lra.last(), "pico_dbtp": pico.last()});
    if curva { v["curva_s"] = json!(curva_ebur(&out)) }
    Ok(v)
}

/// Cortes por cambio de escena > umbral (como referencias.cortes: a 320 px de ancho).
pub fn cortes(video: &str, umbral: f64) -> Result<Vec<f64>, String> {
    let vf = format!("scale=320:-2,select='gt(scene,{umbral})',showinfo");
    let (_, err, _) = ejecutar_cmd("ffmpeg", &["-nostats", "-i", video, "-vf", &vf, "-an", "-f", "null", "-"])?;
    Ok(numeros_tras(&err, "pts_time:").into_iter().map(|t| redondear(t, 2)).collect())
}

/// Tramos negros (blackdetect ≥ 0,1 s) y fotogramas casi blancos (flash) con signalstats.
pub fn negros_y_flashes(video: &str) -> Result<(Vec<[f64; 2]>, Vec<f64>), String> {
    let (out, err, _) = ejecutar_cmd("ffmpeg", &["-nostats", "-i", video, "-vf",
        "scale=160:-2,blackdetect=d=0.1:pix_th=0.10,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-an", "-f", "null", "-"])?;
    let ini = numeros_tras(&err, "black_start:");
    let fin = numeros_tras(&err, "black_end:");
    let negros = ini.iter().zip(&fin).map(|(a, b)| [redondear(*a, 2), redondear(*b, 2)]).collect();
    let mut flashes = vec![];
    let mut t = 0.0;
    for l in out.lines() {
        if let Some(x) = numeros_tras(l, "pts_time:").first() { t = *x }
        if let Some(y) = numeros_tras(l, "lavfi.signalstats.YAVG=").first() {
            if *y >= 235.0 { flashes.push(redondear(t, 2)) }
        }
    }
    Ok((negros, flashes))
}

pub fn medir(video: &str, umbral: f64) -> Result<Value, String> {
    let f = ffprobe(video)?;
    let dur = f["dur"].as_f64().unwrap();
    let c = cortes(video, umbral)?;
    let mut bordes = vec![0.0];
    bordes.extend(c.iter().copied());
    bordes.push(dur);
    let planos: Vec<f64> = bordes.windows(2).map(|w| redondear(w[1] - w[0], 2)).filter(|d| *d > 0.0).collect();
    let audio = if f["audio"] == true { loudness(video, true).unwrap_or_else(|e| json!({"error": e})) } else { json!(null) };
    let (negros, flashes) = negros_y_flashes(video)?;
    let media = if planos.is_empty() { 0.0 } else { crate::color::suma(planos.iter().copied()) / planos.len() as f64 };
    Ok(json!({"video": video, "formato": f, "duracion_s": redondear(dur, 2), "cortes": c, "planos_s": planos,
        "plano_medio_s": redondear(media, 2), "plano_max_s": planos.iter().cloned().fold(0.0, f64::max),
        "cortes_por_min": redondear(c.len() as f64 * 60.0 / dur, 1), "audio": audio, "negros": negros, "flashes": flashes}))
}

pub fn ejecutar(a: &Args) -> Result<i32, String> {
    let video = a.pos.first().ok_or("falta el video")?;
    let umbral = a.opt("umbral").and_then(|x| x.parse().ok()).unwrap_or(0.3);
    let m = medir(video, umbral)?;
    let txt = serde_json::to_string_pretty(&m).unwrap();
    match a.opt("out") {
        Some(o) => { std::fs::write(o, &txt).map_err(|e| format!("{o}: {e}"))?; println!("{o}") }
        None => println!("{txt}"),
    }
    Ok(0)
}

#[cfg(test)]
mod pruebas {
    use super::*;
    #[test]
    fn lee_ebur128() {
        let err = "[Parsed_ebur128_0] Summary:\n  Integrated loudness:\n    I:         -14.2 LUFS\n  Loudness range:\n    LRA:         5.1 LU\n  True peak:\n    Peak:       -1.3 dBFS";
        assert_eq!(numeros_tras(err, "I:"), vec![-14.2]);
        assert_eq!(numeros_tras(err, "Peak:"), vec![-1.3]);
        let out = "frame:0 pts:0 pts_time:0\nlavfi.r128.M=-20.0\nlavfi.r128.S=-120.7\nframe:1 pts_time:0.5\nlavfi.r128.M=-20.0\nframe:2 pts_time:1.0\nlavfi.r128.S=-15.04\nlavfi.r128.M=-inf\n";
        assert_eq!(curva_ebur(out), vec![-20.0, -15.0]);
    }
}
