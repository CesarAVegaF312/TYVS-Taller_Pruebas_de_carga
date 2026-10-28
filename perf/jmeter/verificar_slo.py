#!/usr/bin/env python3
"""
Verifica los SLO sobre un archivo de resultados de JMeter (.jtl en formato CSV).

Es el equivalente de los `thresholds` de los scripts k6: k6 los evalua solo y
termina con codigo distinto de cero si no se cumplen; JMeter no tiene esa
puerta de calidad incorporada, asi que la ponemos aqui. En CI, este script es
el paso que hace fallar el pipeline.

Uso (desde la raiz del repositorio):

    python perf/jmeter/verificar_slo.py perf/results/jmeter-baseline.jtl
    python perf/jmeter/verificar_slo.py perf/results/jmeter-load.jtl --p95 300 --p99 800 --error-rate 0.01

Escribe ademas un resumen JSON junto al .jtl (summary-jmeter-<nombre>.json),
con la misma intencion que los summary-*.json que genera handleSummary en k6:
un artefacto pequeno y comparable entre corridas.

Solo usa la biblioteca estandar: no hay nada que instalar.
"""

import argparse
import csv
import json
import math
import os
import sys


def percentil(valores_ordenados, p):
    """Percentil por el metodo del 'rango mas cercano', el mismo que usa el
    reporte HTML de JMeter. Con la lista ya ordenada."""
    if not valores_ordenados:
        return None
    k = max(1, int(math.ceil(p / 100.0 * len(valores_ordenados))))
    return valores_ordenados[k - 1]


def leer_jtl(ruta):
    """Lee un .jtl CSV con cabecera (el formato por defecto de `jmeter -l`)."""
    muestras = []
    with open(ruta, newline="", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        faltan = {"timeStamp", "elapsed", "success"} - set(lector.fieldnames or [])
        if faltan:
            raise SystemExit(
                f"El archivo no parece un .jtl CSV con cabecera (faltan columnas: {sorted(faltan)}). "
                "Si lo genero en XML, vuelva a ejecutar con jmeter.save.saveservice.output_format=csv."
            )
        for fila in lector:
            muestras.append(
                {
                    "ts": int(fila["timeStamp"]),
                    "elapsed": int(fila["elapsed"]),
                    "ok": fila["success"].strip().lower() == "true",
                    "code": fila.get("responseCode", ""),
                    "msg": fila.get("failureMessage", "") or "",
                }
            )
    return muestras


def resumir(muestras):
    total = len(muestras)
    if total == 0:
        raise SystemExit("El .jtl no tiene muestras: la prueba no envio ninguna peticion.")

    tiempos = sorted(m["elapsed"] for m in muestras)
    fallidas = [m for m in muestras if not m["ok"]]
    inicio = min(m["ts"] for m in muestras)
    fin = max(m["ts"] + m["elapsed"] for m in muestras)
    segundos = max((fin - inicio) / 1000.0, 0.001)

    # Separar "no respondio 200" de "respondio 200 pero con el resultado de
    # negocio equivocado": son dos defectos distintos y se diagnostican distinto.
    http_fallido = sum(1 for m in fallidas if m["code"] != "200")
    negocio_fallido = sum(1 for m in fallidas if m["code"] == "200")

    return {
        "peticiones": total,
        "duracion_s": round(segundos, 1),
        "throughput_rps": round(total / segundos, 2),
        "latencia_ms": {
            "promedio": round(sum(tiempos) / total, 1),
            "p50": percentil(tiempos, 50),
            "p90": percentil(tiempos, 90),
            "p95": percentil(tiempos, 95),
            "p99": percentil(tiempos, 99),
            "max": tiempos[-1],
        },
        "errores": {
            "total": len(fallidas),
            "tasa": round(len(fallidas) / total, 4),
            "http_no_200": http_fallido,
            "resultado_negocio_incorrecto": negocio_fallido,
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Verifica SLO sobre un .jtl de JMeter.")
    ap.add_argument("jtl", help="archivo .jtl (CSV con cabecera) generado con `jmeter -n ... -l`")
    ap.add_argument("--p95", type=int, default=300, help="SLO de p95 en ms (por defecto 300)")
    ap.add_argument("--p99", type=int, default=800, help="SLO de p99 en ms (por defecto 800)")
    ap.add_argument("--error-rate", type=float, default=0.01, help="tasa maxima de error (por defecto 0.01 = 1%%)")
    ap.add_argument("--sin-resumen", action="store_true", help="no escribir el summary-jmeter-*.json")
    args = ap.parse_args()

    resumen = resumir(leer_jtl(args.jtl))
    resumen["slo"] = {"p95_ms": args.p95, "p99_ms": args.p99, "error_rate": args.error_rate}

    incumplidos = []
    if resumen["latencia_ms"]["p95"] > args.p95:
        incumplidos.append(f"p95 {resumen['latencia_ms']['p95']} ms > {args.p95} ms")
    if resumen["latencia_ms"]["p99"] > args.p99:
        incumplidos.append(f"p99 {resumen['latencia_ms']['p99']} ms > {args.p99} ms")
    if resumen["errores"]["tasa"] > args.error_rate:
        incumplidos.append(f"tasa de error {resumen['errores']['tasa']:.2%} > {args.error_rate:.2%}")
    resumen["slo_cumplido"] = not incumplidos
    resumen["slo_incumplidos"] = incumplidos

    print(json.dumps(resumen, indent=2, ensure_ascii=False))

    if not args.sin_resumen:
        nombre = os.path.splitext(os.path.basename(args.jtl))[0].replace("jmeter-", "")
        destino = os.path.join(os.path.dirname(args.jtl) or ".", f"summary-jmeter-{nombre}.json")
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(resumen, f, indent=2, ensure_ascii=False)
        print(f"\nResumen guardado en {destino}", file=sys.stderr)

    if incumplidos:
        print("\nSLO INCUMPLIDO:\n  - " + "\n  - ".join(incumplidos), file=sys.stderr)
        if resumen["errores"]["resultado_negocio_incorrecto"] and not resumen["errores"]["http_no_200"]:
            print(
                "\n  Todas las fallas son 200 con resultado de negocio distinto del esperado. "
                "Casi siempre es estado de una corrida anterior (ids ya registrados -> DUPLICATED): "
                "reinicie el servicio o use -Jid_base=700000000.",
                file=sys.stderr,
            )
        sys.exit(1)

    print("\nSLO cumplido.", file=sys.stderr)


if __name__ == "__main__":
    main()
