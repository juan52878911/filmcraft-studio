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
from common import ds_del_compilado, jload, load_ds  # noqa: E402


def fmt(v):
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, dict):
        return ", ".join(f"{k}: {x}" for k, x in v.items())
    return str(v)


def rel(p, base):
    try:
        return str(Path(p).relative_to(base))
    except (ValueError, TypeError):
        return str(p)


def objetivos(ds_id):
    """(lufs, pico_dbtp, origen) de la mezcla: los del DS; −14/−1 si el DS no los trae o no se encuentra.

    ds_id: el id o el compiled.json entero (entonces usa el DS con el que se compiló, `ds_dir`)."""
    try:
        ds = ds_del_compilado(ds_id) if isinstance(ds_id, dict) else load_ds(ds_id)
        au = ds.get("audio", {})
    except (FileNotFoundError, KeyError, TypeError, SystemExit):
        au = {}
    lufs, pico = au.get("lufs"), au.get("pico_dbtp")
    origen = "DS" if lufs is not None else "por defecto"
    return (lufs if lufs is not None else -14), (pico if pico is not None else -1), origen


def marca(medido, bien):
    """✅ / ⚠️ solo si se midió; si no, «sin medir»."""
    if not medido:
        return "❓ sin medir"
    return "✅" if bien else "⚠️"


def valor(brief, k, sub="valor", defecto="no consta"):
    v = brief.get(k)
    return v.get(sub, defecto) if isinstance(v, dict) else defecto


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
    ef = w / "estado.json"
    modo = (ver or {}).get("modo") or (jload(ef).get("modo") if ef.exists() else None)
    modo_txt = {"headless": "Modo **headless**: proyecto nuevo, sin exportar video. ",
                "live": "Modo **en vivo** (app abierta), sin exportar video. "}.get(modo, "Modo: no consta. ")
    L = [f"# Informe de montaje · {plan.get('titulo', w.name)}", ""]
    L += [modo_txt + f"Proyecto: `{rel(ver['proyecto'], w) if ver else '—'}` · DS `{comp['ds']}` · {comp['fps']} fps · "
          f"{comp['duracion']:.2f} s.", ""]

    L += ["## D1 · Brief", "", "| Campo | Valor | Origen | Confianza |", "|---|---|---|---|"]
    preguntas = []
    for k, v in brief.items():
        if not isinstance(v, dict) or "valor" not in v:
            continue
        L.append(f"| {k} | {fmt(v['valor'])} | {v.get('origen', '—')} | {v.get('confianza', '—')} |")
        if (v.get("confianza") or 1) < 0.6 and v.get("origen") != "dado":
            preguntas.append(f"**{k}**: usé «{fmt(v['valor'])}» ({v['origen']}{', ' + v['por'] if v.get('por') else ''}). ¿Es correcto?")
    L.append("")

    bds = brief.get("ds") if isinstance(brief.get("ds"), dict) else {}
    L += ["## D2 · Design system", "", f"`{comp['ds']}` — {bds.get('por') or bds.get('origen') or 'no consta'}.", ""]

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
        lufs_obj, pico_obj, origen_obj = objetivos(comp)
        fallos = ver.get("fallos") or []
        tc_medido = tc.get("medido", True)          # verificaciones antiguas no traen «medido»
        nota_tc = "" if tc_medido else f" (medidos {tc.get('momentos_medidos', 0)} de {tc.get('momentos', 0)} momentos)"
        lufs_ok = au.get("lufs") is not None
        # cortes en palabra: 0 bordes = nada medido (falta <fuente>.palabras.json), no «0 problemas»
        cp_medido = cp.get("medido", True) and cp["bordes"] > 0
        nota_cp = f" ({len(cp['clips_sin_palabras'])} clips sin transcripción)" if cp.get("clips_sin_palabras") else ""
        dcomp = ver.get("duracion_compilada_s") or comp.get("duracion")
        dur_ok = not dcomp or ver["duracion_s"] <= dcomp + 1 / (comp.get("fps") or 30) + 0.005
        if fallos or ver.get("verificado") is False:
            L += ["**Verificación incompleta** — lo marcado «sin medir» no se pudo comprobar:", ""] + \
                 [f"- {f}" for f in fallos] + [""]
        L += ["| Comprobación | Resultado |", "|---|---|",
              f"| Duración | {marca(ver['duracion_s'] > 0, dur_ok)} {ver['duracion_s']} s (compilado {dcomp} s; objetivo "
              f"{valor(brief, 'duracion_s')} s) |",
              f"| Loudness integrada | {marca(lufs_ok, lufs_ok and abs(au['lufs'] - lufs_obj) <= 1.0)} {au.get('lufs')} LUFS "
              f"(objetivo {lufs_obj}, {origen_obj}) |",
              f"| Pico | {marca(au.get('pico_dbtp') is not None, (au.get('pico_dbtp') or 0) <= pico_obj)} {au.get('pico_dbtp')} dBTP "
              f"(≤ {pico_obj}) |",
              f"| Cortes dentro de palabra | {marca(cp_medido, not cp['dentro_de_palabra'])} {len(cp['dentro_de_palabra'])} de "
              f"{cp['bordes']} bordes{nota_cp} |",
              f"| Keyframes fuera de rango | {marca(True, not kc['n_fuera'])} {kc['n_fuera']} de {kc['keyframes']} |",
              f"| Pop-ups que tapan caras/personas | {marca(tc_medido, not tc['choques'])} {len(tc['choques'])} de {tc['popups']}"
              f"{nota_tc} |",
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
                  f"| Pico | {au.get('pico_dbtp')} dBTP | {ra.get('pico_dbtp')} dBTP |",
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
    L += ["## Qué no está verificado", ""] + [f"- {f}" for f in ((ver or {}).get("fallos") or [])] + [
          "- No hay export de video: las hojas son renders headless de fotogramas sueltos y el audio es la mezcla `.wav`.",
          "- Nadie ha escuchado la mezcla: solo hay cifras (LUFS, pico, curva).", ""]
    out = Path(a.out) if a.out else w / "informe.md"
    out.write_text("\n".join(L))
    print(out)


if __name__ == "__main__":
    main()
