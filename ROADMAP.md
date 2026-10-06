# ROADMAP — v1.4 (real Python + base IBC 3 ded)
**Base:** `app.py:1-312` verificado · **Zona:** America/Bogota

> [!NOTE]
> Opción 1 SQLite original (Drizzle/TS) archivada. Implementado Opción 1b: Python stdlib + SQLite archivo. Sin deps.

## MVP v1 — DONE (2 sem, modo plan→build) ✅
- [x] CRUD + tarifa_manual obligatoria + h_ord/h_noct/h_dom. `app.py:185-288`
- [x] Motor `bruto = ord + noct*1.35 + dom*1.90`, base IBC, subsidio 250/400/600k, 3 ded 8.522%. `app.py:37-53`
- [x] SQLite `nomina.db` WAL + FK + `init_db()` idempotente. `app.py:64-91`
- [x] Flujo lineal + snapshot + envío mock con log. `app.py:223-253`
- [x] UI `index.html` verificado RN-06 neto 3.519.424 (3 ded).
- [x] Docs v1.4 sincronizados (este lote).

DoD MVP cumplido: corre con `python3 app.py`, 0 tracebacks, docs sync.

## v1.1 — Endurecer (1 sem, siguiente)
- Cola reintentos + SMTP real + PDF desglose (ReportLab o WeasyPrint).
- Auditoría quién/cuándo autorizó: tabla `audit_log(actor, action, employee_id, ts)`.
- Auth mínima: token gerente para `/authorize` y `/send`, rate-limit.
- Validación params 0-1 y recargos >=1 en servidor.
- `ThreadingHTTPServer`, backup automático `.bak-diario`, export JSON.
- Normalizar email lower, índices `idx_pay_estado`.
- Tests: `pytest` para `liquidar` (RN-03/04/05/06 + bordes 0h, 3+ hijos).

## v2 — Full legal (2 sem)
- 7 tipos (extras 1.25/1.75/2.15/2.65/2.25), ARL por riesgo I-V (0.522%–6.96%), rec_dom 2.0 desde jul-2027 con versionado automático por fecha.
- Histórico por periodo: migrar `payslips` 1:1 → `payslips_hist` con `periodo YYYY-MM`.
- Reportes ERP/CSV, nómina O(n) batch + preview por periodo.
- Jornada 42h validación: alerta si `h_ord > 42*4.33 ≈ 182h/mes`.
- Frontend: Next.js+TS + Tailwind+shadcn si escala (recomendación skill), o mantener HTML si <50 empleados.

## Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Cambio legal dom 2.0 jul-2027 olvidado | Alto | `TODO` + `params.version` por fecha, test calendarizado |
| ARL descontada vs ley (empleador paga) | Medio | Parametrizable a 0, nota contable en SRS |
| Single-thread bloquea con n grande | Bajo | `ThreadingHTTPServer` en v1.1, Big-O ya O(n) |
| Sin auth expone salarios | Alto | No exponer a LAN/internet hasta v1.1 |

> [!TIP]
> Siguiente paso sugerido: congelar v1.1 solo cuando contabilidad firme RN-06 3.519.424 y legal confirme plan jul-2027.
