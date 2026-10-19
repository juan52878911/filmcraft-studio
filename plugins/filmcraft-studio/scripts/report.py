#!/usr/bin/env python3
"""informe.md de un montaje: decisiones D1–D3, evidencias, comparación con la referencia y preguntas.

Uso: report.py WORK [--critica WORK/critica.md] [--out WORK/informe.md]

Lee WORK/brief.json, plan.json, compiled.json, verificacion/verificacion.json y (si existe) critica.md.
Todo lo que el informe afirma sale de esos ficheros: si algo no se midió, lo dice.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import jload  # noqa: E402


def fmt(v):
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, dict):
        return ", ".join(f"{k}: {x}" for k, x in v.items())
    return str(v)


def rel(p, base):
    try:
        return str(Path(p).relative_to(base))
    except Exception:
        return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--critica")
    ap.add_argument("--out")
    a = ap.parse_args()
    w = Path(a.work)
    brief = jload(w / "brief.json")
    plan = jload(w / "plan.json")
    comp = jload(w / "compiled.json")
    vf = w / "verificacion/verificacion.json"
    ver = jload(vf) if vf.exists() else None
    L = [f"# Informe de montaje · {plan.get('titulo', w.name)}", ""]
    L += ["Modo **headless**: proyecto nuevo, sin exportar video. "
          f"Proyecto: `{rel(ver['proyecto'], w) if ver else '—'}` · DS `{comp['ds']}` · {comp['fps']} fps · "
          f"{comp['duracion']:.2f} s.", ""]

    L += ["## D1 · Brief", "", "| Campo | Valor | Origen | Confianza |", "|---|---|---|---|"]
    preguntas = []
    for k, v in brief.items():
        if not isinstance(v, dict) or "valor" not in v:
            continue
        L.append(f"| {k} | {fmt(v['valor'])} | {v['origen']} | {v['confianza']} |")
        if v["confianza"] < 0.6 and v["origen"] != "dado":
            preguntas.append(f"**{k}**: usé «{fmt(v['valor'])}» ({v['origen']}{', ' + v['por'] if v.get('por') else ''}). ¿Es correcto?")
    L.append("")

    L += ["## D2 · Design system", "", f"`{comp['ds']}` — {brief['ds'].get('por') or brief['ds']['origen']}.", ""]

    L += ["## D3 · Plan", ""]
    if plan.get("estrategia"):
        L += [plan["estrategia"], ""]
    L += ["| Bloque | Tipo | Secuencia | Resumen |", "|---|---|---|---|"]
    for b in comp["bloques"]:
        L.append(f"| {b['id']} | {b['tipo']} | {b['start']:.2f}–{b['end']:.2f} | {b.get('resumen', '')} |")
    L.append("")
    tr = {}
    for t in comp["transiciones"]:
        tr[t["tipo"]] = tr.get(t["tipo"], 0) + 1
    L += [f"- Planos: {len(comp['segmentos'])} · cortes: {comp['cortes']} · transiciones: {fmt(tr) or 'solo cortes'}",
          f"- Textos: {len(comp['textos'])} · subtítulos: {len(comp['subtitulos'])} · SFX: {len(comp['sfx'])}",
          f"- Bordes de plano ajustados a límite de palabra: {len(comp['ajustes_corte'])}", ""]
    if comp["avisos"]:
        L += ["Avisos del compilador:", ""] + [f"- {x}" for x in comp["avisos"]] + [""]

    L += ["## Verificación", ""]
    if not ver:
        L += ["**Sin verificar**: no hay `verificacion/verificacion.json`.", ""]
    else:
        au = ver["audio"]
        kc = ver["keyframes"]
        cp = ver["cortes_en_palabra"]
        tc = ver["textos_vs_caras"]
        ok = lambda c: "✅" if c else "⚠️"  # noqa: E731
        L += ["| Comprobación | Resultado |", "|---|---|",
              f"| Duración | {ver['duracion_s']} s (objetivo {brief['duracion_s']['valor']} s) |",
              f"| Loudness integrada | {ok(au.get('lufs') is not None and abs(au['lufs'] + 14) <= 1.5)} {au.get('lufs')} LUFS (objetivo −14) |",
              f"| Pico | {ok((au.get('pico_dbtp') or 0) <= -1)} {au.get('pico_dbtp')} dBFS (≤ −1) |",
              f"| Cortes dentro de palabra | {ok(not cp['dentro_de_palabra'])} {len(cp['dentro_de_palabra'])} de {cp['bordes']} bordes |",
              f"| Keyframes fuera de rango | {ok(not kc['n_fuera'])} {kc['n_fuera']} de {kc['keyframes']} |",
              f"| Pop-ups que tapan caras/personas | {ok(not tc['choques'])} {len(tc['choques'])} de {tc['popups']} |",
              f"| Obligatorios cubiertos | {sum(ver['cobertura'].values())}/{len(ver['cobertura'])} ({fmt({k: '✓' if v else '✗' for k, v in ver['cobertura'].items()})}) |",
              ""]
        if tc["choques"]:
            L += ["Pop-ups con choque:", ""] + [f"- «{c['texto']}» en {c['t']} s (cara {c['cara']}, persona {c['persona']})" for c in tc["choques"]] + [""]
        if cp["dentro_de_palabra"]:
            L += ["Cortes dentro de palabra:", ""] + [f"- {c['seq_s']} s, {c['borde']} en «{c['palabra']}»" for c in cp["dentro_de_palabra"]] + [""]
        L += ["Evidencias:", ""]
        for k in ("hoja_cortes", "hoja_popups", "hoja_popups_sin_textos", "hoja_comparacion", "hoja_curvas"):
            if ver.get(k):
                L.append(f"- {k.replace('_', ' ')}: `{rel(ver[k], w)}`")
        L.append(f"- mezcla: `{rel(au.get('wav', ''), w)}`")
        L.append("")
        if ver.get("referencia"):
            r = ver["referencia"]
            ra = r["audio"]
            L += ["## Comparación con el montaje manual", "",
                  f"Referencia: `{r['proyecto']}` (solo lectura).", "",
                  "| | Automático | Manual |", "|---|---|---|",
                  f"| Duración | {ver['duracion_s']} s | {r['duracion_s']} s |",
                  f"| Planos en Main | {ver['planos']} | {r['planos']} |",
                  f"| Cortes | {ver['cortes']} | {r['cortes']} |",
                  f"| Loudness | {au.get('lufs')} LUFS | {ra.get('lufs')} LUFS |",
                  f"| Pico | {au.get('pico_dbtp')} dBFS | {ra.get('pico_dbtp')} dBFS |",
                  f"| LRA | {au.get('lra')} LU | {ra.get('lra')} LU |",
                  f"| Obligatorios | {sum(ver['cobertura'].values())}/{len(ver['cobertura'])} | "
                  f"{sum(r['obligatorios'].values())}/{len(r['obligatorios'])} |", ""]
            ca, cb = au.get("curva_s", []), ra.get("curva_s", [])
            n = min(len(ca), len(cb))
            if n:
                d = [abs(x - y) for x, y in zip(ca[:n], cb[:n]) if x > -60 and y > -60]
                if d:
                    L += [f"Curva LUFS a corto plazo: diferencia media {sum(d) / len(d):.1f} LU en {len(d)} s comparables "
                          f"(no es una medida de calidad: los montajes son distintos).", ""]
    crit = Path(a.critica) if a.critica else w / "critica.md"
    if crit.exists():
        L += ["## Crítica", "", crit.read_text().strip(), ""]
    L += ["## Preguntas pendientes", ""] + ([f"- {p}" for p in preguntas] or ["- Ninguna."]) + [""]
    L += ["## Qué no está verificado", "",
          "- No hay export de video: las hojas son renders headless de fotogramas sueltos y el audio es la mezcla `.wav`.",
          "- Nadie ha escuchado la mezcla: solo hay cifras (LUFS, pico, curva).", ""]
    out = Path(a.out) if a.out else w / "informe.md"
    out.write_text("\n".join(L))
    print(out)


if __name__ == "__main__":
    main()
