//! Expresiones regulares mínimas para los `pattern` de los esquemas: ^ $, literales, `.`, clases
//! [a-z0-9_-] y [^…], y cuantificadores ? * + {m} {m,} {m,n}. Búsqueda como re.search de Python.

#[derive(Debug, Clone)]
enum Atomo {
    Lit(char),
    Cualquiera,
    Clase(Vec<(char, char)>, bool),
}

#[derive(Debug, Clone)]
struct Pieza {
    a: Atomo,
    min: usize,
    max: usize,
}

fn compilar(p: &str) -> Option<(bool, Vec<Pieza>, bool)> {
    let cs: Vec<char> = p.chars().collect();
    let mut i = 0;
    let ini = cs.first() == Some(&'^');
    if ini { i = 1 }
    let mut fin = false;
    let mut v = vec![];
    while i < cs.len() {
        let c = cs[i];
        let a = match c {
            '$' if i == cs.len() - 1 => { fin = true; i += 1; continue }
            '.' => { i += 1; Atomo::Cualquiera }
            '\\' => {
                let e = *cs.get(i + 1)?;
                i += 2;
                match e {
                    'd' => Atomo::Clase(vec![('0', '9')], false),
                    'w' => Atomo::Clase(vec![('a', 'z'), ('A', 'Z'), ('0', '9'), ('_', '_')], false),
                    's' => Atomo::Clase(vec![(' ', ' '), ('\t', '\t'), ('\n', '\n'), ('\r', '\r')], false),
                    x => Atomo::Lit(x),
                }
            }
            '[' => {
                i += 1;
                let neg = cs.get(i) == Some(&'^');
                if neg { i += 1 }
                let mut r = vec![];
                let mut primero = true;
                while i < cs.len() && (cs[i] != ']' || primero) {
                    let mut a = cs[i];
                    if a == '\\' { i += 1; a = *cs.get(i)? }
                    if cs.get(i + 1) == Some(&'-') && cs.get(i + 2).map_or(false, |x| *x != ']') {
                        r.push((a, cs[i + 2]));
                        i += 3;
                    } else {
                        r.push((a, a));
                        i += 1;
                    }
                    primero = false;
                }
                if i >= cs.len() { return None }
                i += 1;
                Atomo::Clase(r, neg)
            }
            x => { i += 1; Atomo::Lit(x) }
        };
        let (mut min, mut max) = (1, 1);
        match cs.get(i) {
            Some('?') => { min = 0; i += 1 }
            Some('*') => { min = 0; max = usize::MAX; i += 1 }
            Some('+') => { max = usize::MAX; i += 1 }
            Some('{') => {
                let cierre = cs[i..].iter().position(|x| *x == '}')? + i;
                let dentro: String = cs[i + 1..cierre].iter().collect();
                let mut partes = dentro.splitn(2, ',');
                min = partes.next()?.trim().parse().ok()?;
                max = match partes.next() {
                    None => min,
                    Some(s) if s.trim().is_empty() => usize::MAX,
                    Some(s) => s.trim().parse().ok()?,
                };
                i = cierre + 1;
            }
            _ => {}
        }
        v.push(Pieza { a, min, max });
    }
    Some((ini, v, fin))
}

fn casa_atomo(a: &Atomo, c: char) -> bool {
    match a {
        Atomo::Lit(x) => *x == c,
        Atomo::Cualquiera => c != '\n',
        Atomo::Clase(r, neg) => r.iter().any(|(a, b)| *a <= c && c <= *b) != *neg,
    }
}

fn desde(ps: &[Pieza], t: &[char], fin: bool) -> bool {
    let Some(p) = ps.first() else { return !fin || t.is_empty() };
    let mut n = 0;
    while n < p.max && n < t.len() && casa_atomo(&p.a, t[n]) { n += 1 }
    loop {
        if n >= p.min && desde(&ps[1..], &t[n..], fin) { return true }
        if n == 0 || n <= p.min { return false }
        n -= 1;
    }
}

/// ¿El patrón aparece en el texto (re.search)? Un patrón que no se entiende cuenta como que casa.
pub fn casa(p: &str, t: &str) -> bool {
    let Some((ini, ps, fin)) = compilar(p) else { return true };
    let cs: Vec<char> = t.chars().collect();
    if ini { return desde(&ps, &cs, fin) }
    (0..=cs.len()).any(|i| desde(&ps, &cs[i..], fin))
}

#[cfg(test)]
mod pruebas {
    use super::casa;
    #[test]
    fn patrones_del_esquema() {
        assert!(casa("^#[0-9A-Fa-f]{6}$", "#00ff0A"));
        assert!(!casa("^#[0-9A-Fa-f]{6}$", "#00ff0"));
        assert!(!casa("^#[0-9A-Fa-f]{6}$", "#00ff0AA"));
        assert!(casa("^[a-z0-9][a-z0-9-]{0,63}$", "promo-riso"));
        assert!(!casa("^[a-z0-9][a-z0-9-]{0,63}$", "-riso"));
        assert!(casa("^[a-z0-9-]+@[0-9]+$", "termo@1"));
        assert!(!casa("^[a-z0-9-]+@[0-9]+$", "termo@"));
        assert!(casa("^[a-z][a-z0-9_]*$", "acento1"));
        assert!(casa("b+", "abbc"));
    }
}
