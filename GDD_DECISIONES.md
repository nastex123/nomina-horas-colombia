# GDD — Decisiones de Diseño (Producto + Técnico + Legal)
**Versión:** v1.4 · **Zona:** America/Bogota · Decide sobre `app.py` + `index.html` reales.

> [!NOTE]
> GDD aquí = registro de decisiones, no game design. Cada decisión trae contexto, alternativas, elección y consecuencia.

## D-01 Tarifa 100% manual
- **Contexto:** 3 cargos existen pero sin escala salarial aprobada.
- **Alternativas:** (a) tabla por cargo, (b) SMMLV/hora, (c) manual.
- **Elección:** (c) manual `tarifa>0` obligatoria. `app.py:70`
- **Consecuencia:** flexibilidad total, riesgo error digitación → mitigado con ejemplo RN-06 y revisión Financiero.

## D-02 Solo 3 tipos hora (vs 7 full)
- **Contexto:** Ley permite 7 combinaciones extras/recargos.
- **Alternativas:** (a) 3 simple 1.0/1.35/1.90, (b) 7 full.
- **Elección:** (a) para MVP auditable. Full a v2. `SRS §2`
- **Consecuencia:** O(k) k=3, código 5 líneas. Deuda: horas extras >42h no discriminadas.

## D-03 Base IBC = bruto (recargos sí, subsidio no)
- **Contexto:** Investigación CO Oct-2026: recargos son salario.
- **Alternativas:** (a) base=bruto, (b) base=ordinaria sola.
- **Elección:** (a) `base=bruto` `app.py:44`.
- **Consecuencia:** aportes correctos, neto mayor que si se excluyeran recargos. Trazable a CST/Ley 2466.

## D-04 3 ded sin caja (vs 4 con caja)
- **Contexto:** ARL/caja legalmente las paga empleador, pero ejercicio pide descontar.
- **Alternativas:** (a) 4 ded 10.522% con caja, (b) 3 ded 8.522% sin caja.
- **Elección:** (b) en código v1.3. Caja reactivable a 0.02.
- **Consecuencia:** neto 3.519.424 vs 3.447.944 (+71.480). Requiere firma contabilidad.

## D-05 Python stdlib + SQLite archivo (vs TS+Drizzle)
- **Contexto:** Plan era TS + better-sqlite3 + Drizzle sin código.
- **Alternativas:** (a) TS/Drizzle, (b) Python stdlib cero deps.
- **Elección:** (b) `http.server+sqlite3` `app.py:6-13`. Cero install, ideal SENA.
- **Consecuencia:** single-thread, sin ORM, pero portable y verificable en 1 comando.

## D-06 payslips 1:1 por empleado (vs histórico por periodo)
- **Contexto:** MVP necesita 1 estado vigente, no planilla mensual multi-periodo.
- **Elección:** `payslips.employee_id PK` `app.py:76-78`.
- **Consecuencia:** simple, pero no guarda histórico. Migración `payslips_hist` en v2.

## D-07 Snapshot de params (vs recalcular siempre)
- **Contexto:** % y recargos cambian por ley (dom 2.0 en 2027).
- **Elección:** guardar JSON en `En revisión/Autorizada` `app.py:239-241`.
- **Consecuencia:** auditoría perfecta, costo 1 TEXT por slip O(1).

## D-08 Flujo lineal sin retroceso (vs máquina con devoluciones)
- **Contexto:** SRS menciona `Devuelta` pero código solo avanza.
- **Elección:** `NEXT` estricto `app.py:21`.
- **Consecuencia:** predecible, pero corregir error exige DB manual. V1.1: agregar `Devuelta`.

## D-09 Envío mock log (vs SMTP+PDF)
- **Contexto:** Sin credenciales ni generador PDF en stdlib.
- **Elección:** `send_log` texto `app.py:246-250`.
- **Consecuencia:** trazable en UI, no envía email real. V1.1 SMTP+PDF.

## D-10 UI única HTML (vs Next.js+Tailwind)
- **Contexto:** Skill recomienda Next.js+TS+Tailwind+shadcn para escala.
- **Elección:** `index.html` único con CSS inline para MVP <50 empleados.
- **Consecuencia:** 0 build, responsive básico grid-2, a11y focus-visible. Escalar a Next.js solo en v2.

> [!IMPORTANT]
> Ninguna decisión legal sustituye concepto de abogado/contador. Validar D-03/D-04 antes de producción.

> [!TIP]
> Siguiente paso sugerido: convertir D-04 y D-08 en issues v1.1 con dueño y fecha.
