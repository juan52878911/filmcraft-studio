//! Subconjunto de JSON Schema 2020-12 que usan los esquemas del plugin (type, required, properties,
//! additionalProperties, items, prefixItems, min/maxItems, minimum, exclusiveMinimum, pattern, enum,
//! anyOf y $ref local), con los mensajes de la librería `jsonschema` de Python para los casos simples.
use serde_json::Value;

pub struct Error {
    pub ruta: Vec<String>,
    pub mensaje: String,
}

/// repr() de Python de un valor JSON (para los mensajes).
pub fn repr(v: &Value) -> String {
    match v {
        Value::Null => "None".into(),
        Value::Bool(b) => if *b { "True".into() } else { "False".into() },
        Value::Number(n) => {
            if n.is_f64() {
                let f = n.as_f64().unwrap();
                if f.fract() == 0.0 && f.abs() < 1e16 { format!("{f:.1}") } else { format!("{f}") }
            } else {
                n.to_string()
            }
        }
        Value::String(s) => repr_str(s),
        Value::Array(a) => format!("[{}]", a.iter().map(repr).collect::<Vec<_>>().join(", ")),
        Value::Object(o) => format!("{{{}}}", o.iter().map(|(k, v)| format!("{}: {}", repr_str(k), repr(v))).collect::<Vec<_>>().join(", ")),
    }
}

fn repr_str(s: &str) -> String {
    let q = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut o = String::from(q);
    for c in s.chars() {
        match c {
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\t' => o.push_str("\\t"),
            '\r' => o.push_str("\\r"),
            c if c == q => { o.push('\\'); o.push(c) }
            c => o.push(c),
        }
    }
    o.push(q);
    o
}

fn es_tipo(v: &Value, t: &str) -> bool {
    match t {
        "object" => v.is_object(),
        "array" => v.is_array(),
        "string" => v.is_string(),
        "null" => v.is_null(),
        "boolean" => v.is_boolean(),
        "number" => v.is_number(),
        "integer" => v.as_i64().is_some() || v.as_u64().is_some() || v.as_f64().map_or(false, |f| f.fract() == 0.0),
        _ => true,
    }
}

fn num(v: &Value) -> String {
    repr(v)
}

pub fn validar(raiz: &Value, v: &Value) -> Vec<Error> {
    let mut out = vec![];
    nodo(raiz, raiz, v, &mut vec![], &mut out);
    out
}

fn resolver<'a>(raiz: &'a Value, r: &str) -> Option<&'a Value> {
    let mut x = raiz;
    for p in r.strip_prefix("#/")?.split('/') {
        x = x.get(p)?;
    }
    Some(x)
}

fn nodo(raiz: &Value, s: &Value, v: &Value, ruta: &mut Vec<String>, out: &mut Vec<Error>) {
    if let Some(o) = s.as_object() {
        nodo_resto(raiz, o, v, ruta, out);
    }
}

fn out_push(out: &mut Vec<Error>, ruta: &[String], m: String) {
    out.push(Error { ruta: ruta.to_vec(), mensaje: m });
}

fn nodo_resto(raiz: &Value, o: &serde_json::Map<String, Value>, v: &Value, ruta: &mut Vec<String>, out: &mut Vec<Error>) {
    for (k, regla) in o {
        match k.as_str() {
            "$ref" => {
                if let Some(d) = regla.as_str().and_then(|r| resolver(raiz, r)) {
                    nodo(raiz, d, v, ruta, out);
                }
            }
            "type" => {
                let tipos: Vec<&str> = match regla {
                    Value::String(t) => vec![t.as_str()],
                    Value::Array(a) => a.iter().filter_map(|x| x.as_str()).collect(),
                    _ => vec![],
                };
                if !tipos.iter().any(|t| es_tipo(v, t)) {
                    let lista = tipos.iter().map(|t| format!("'{t}'")).collect::<Vec<_>>().join(", ");
                    out_push(out, ruta, format!("{} is not of type {lista}", repr(v)));
                }
            }
            "required" => {
                if let Some(obj) = v.as_object() {
                    for r in regla.as_array().into_iter().flatten().filter_map(|x| x.as_str()) {
                        if !obj.contains_key(r) {
                            out_push(out, ruta, format!("{} is a required property", repr_str(r)));
                        }
                    }
                }
            }
            "properties" => {
                if let (Some(obj), Some(props)) = (v.as_object(), regla.as_object()) {
                    for (p, sp) in props {
                        if let Some(x) = obj.get(p) {
                            ruta.push(p.clone());
                            nodo(raiz, sp, x, ruta, out);
                            ruta.pop();
                        }
                    }
                }
            }
            "additionalProperties" => {
                if let Some(obj) = v.as_object() {
                    let props = o.get("properties").and_then(|p| p.as_object());
                    let extra: Vec<&String> = obj.keys().filter(|k| props.map_or(true, |p| !p.contains_key(*k))).collect();
                    if regla == &Value::Bool(false) {
                        if !extra.is_empty() {
                            let l = extra.iter().map(|k| repr_str(k)).collect::<Vec<_>>().join(", ");
                            let verbo = if extra.len() == 1 { "was" } else { "were" };
                            out_push(out, ruta, format!("Additional properties are not allowed ({l} {verbo} unexpected)"));
                        }
                    } else if regla.is_object() {
                        for k in extra {
                            ruta.push(k.clone());
                            nodo(raiz, regla, &obj[k], ruta, out);
                            ruta.pop();
                        }
                    }
                }
            }
            "prefixItems" => {
                if let (Some(a), Some(ps)) = (v.as_array(), regla.as_array()) {
                    for (i, (x, sp)) in a.iter().zip(ps).enumerate() {
                        ruta.push(i.to_string());
                        nodo(raiz, sp, x, ruta, out);
                        ruta.pop();
                    }
                }
            }
            "items" => {
                if let Some(a) = v.as_array() {
                    let desde = o.get("prefixItems").and_then(|p| p.as_array()).map_or(0, |p| p.len());
                    for (i, x) in a.iter().enumerate().skip(desde) {
                        ruta.push(i.to_string());
                        nodo(raiz, regla, x, ruta, out);
                        ruta.pop();
                    }
                }
            }
            "minItems" => {
                if let (Some(a), Some(m)) = (v.as_array(), regla.as_u64()) {
                    if (a.len() as u64) < m {
                        let msg = if m == 1 { format!("{} should be non-empty", repr(v)) } else { format!("{} is too short", repr(v)) };
                        out_push(out, ruta, msg);
                    }
                }
            }
            "maxItems" => {
                if let (Some(a), Some(m)) = (v.as_array(), regla.as_u64()) {
                    if (a.len() as u64) > m {
                        let msg = if m == 0 { format!("{} is expected to be empty", repr(v)) } else { format!("{} is too long", repr(v)) };
                        out_push(out, ruta, msg);
                    }
                }
            }
            "minimum" => {
                if let (Some(x), Some(m)) = (v.as_f64().filter(|_| v.is_number()), regla.as_f64()) {
                    if x < m {
                        out_push(out, ruta, format!("{} is less than the minimum of {}", repr(v), num(regla)));
                    }
                }
            }
            "exclusiveMinimum" => {
                if let (Some(x), Some(m)) = (v.as_f64().filter(|_| v.is_number()), regla.as_f64()) {
                    if x <= m {
                        out_push(out, ruta, format!("{} is less than or equal to the minimum of {}", repr(v), num(regla)));
                    }
                }
            }
            "pattern" => {
                if let (Some(t), Some(p)) = (v.as_str(), regla.as_str()) {
                    if !crate::patron::casa(p, t) {
                        out_push(out, ruta, format!("{} does not match {}", repr(v), repr_str(p)));
                    }
                }
            }
            "enum" => {
                if let Some(l) = regla.as_array() {
                    if !l.contains(v) {
                        out_push(out, ruta, format!("{} is not one of {}", repr(v), repr(regla)));
                    }
                }
            }
            "anyOf" => {
                if let Some(l) = regla.as_array() {
                    let vale = l.iter().any(|sp| {
                        let mut e = vec![];
                        nodo(raiz, sp, v, &mut ruta.clone(), &mut e);
                        e.is_empty()
                    });
                    if !vale {
                        out_push(out, ruta, format!("{} is not valid under any of the given schemas", repr(v)));
                    }
                }
            }
            _ => {}
        }
    }
}

#[cfg(test)]
mod pruebas {
    use super::*;
    use serde_json::json;
    #[test]
    fn subconjunto() {
        let s = json!({"type": "object", "required": ["a"], "additionalProperties": false,
            "$defs": {"hex": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}},
            "properties": {"a": {"$ref": "#/$defs/hex"}, "b": {"type": "array", "minItems": 2, "items": {"type": "number", "exclusiveMinimum": 0}}}});
        assert!(validar(&s, &json!({"a": "#00FF00", "b": [1, 2.5]})).is_empty());
        let e = validar(&s, &json!({"b": [0], "c": 1}));
        let m: Vec<_> = e.iter().map(|e| e.mensaje.clone()).collect();
        assert!(m.contains(&"'a' is a required property".to_string()));
        assert!(m.contains(&"Additional properties are not allowed ('c' was unexpected)".to_string()));
        assert!(m.contains(&"[0] is too short".to_string()));
        assert!(m.contains(&"0 is less than or equal to the minimum of 0".to_string()));
        let e = validar(&s, &json!({"a": "#00FF0"}));
        assert_eq!(e[0].mensaje, "'#00FF0' does not match '^#[0-9A-Fa-f]{6}$'");
    }
}
