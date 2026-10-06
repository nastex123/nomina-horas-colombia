# TODO — v1.4 validación + MVP verificado + puerto --force + front responsive
**Fuente:** `app.py` + `index.html` · **Zona:** America/Bogota

## DONE ✅
- [x] Front responsive sin overflow: cards + scroll, `row3` colapsable, `%` directo con total vivo. `index.html`
- [x] Params 3 ded en % + backend acepta fracción/`% >1`/`"x%"` con validación. Verificado 8781/8782 + neto 3519424.
- [x] Puerto: `--force` libera y retoma (8771/8772 verificado), `--help`, `connect_ex` O(1). `app.py:360-448`
- [x] Docs sync puerto: README quickstart + MANUAL arranque/troubleshooting + CHANGELOG v1.3.1-port.
- [x] Opción 1b elegida: Python stdlib + SQLite archivo (referencia). MVP HTML+API verificado, no LocalStorage.
- [x] Tarifa manual única, derivadas auto 1.35/1.90. `app.py:110-111`
- [x] Simple 3 tipos, jornada 42h, Ley 2466 Art.10/14 verificada Oct-2026.
- [x] Base IBC: recargos sí suman, subsidio no. `app.py:44`
- [x] 3 ded (salud/pensión/ARL) — caja eliminada. Neto RN-06 3.519.424 verificado ejecutando `liquidar`.
- [x] MVP `index.html` + `app.py` corre con 0 errores log.
- [x] Docs v1.4 sincronizados: README/SRS/TDD/Diccionario/ROADMAP/CHANGELOG/GDD/Manual.

## Por validar (externos)
- [ ] Contabilidad: confirmar 3 ded (sin caja) + rec 1.35/1.90 y ejemplo RN-06 neto 3.519.424.
- [ ] Legal: prever cambio dom 90%→100% (1.90→2.0) jul-2027, versionar params por fecha.
- [ ] TI: backup/export JSON de `nomina.db` antes de cualquier migración a histórico.

## Deuda técnica v1.1
- [ ] Normalizar email a lower antes de UNIQUE.
- [ ] Validar `PUT /api/params` rangos 0-1 y recargos >=1.
- [ ] Agregar `CHECK` SQL para params + índice `idx_pay_estado`.
- [ ] Migrar `HTTPServer` → `ThreadingHTTPServer`.
- [ ] SMTP real + PDF + cola reintentos 3x.
- [ ] `pytest` para `liquidar` + transiciones.
- [ ] Auditoría actor + auth token gerente.

## Deuda docs (cerrada en este lote)
- [x] Sincronizar TDD (era TS/Drizzle/4 ded) a Python real 3 ded.
- [x] Corregir RN-06 3.447.944 (4 ded) → 3.519.424 (3 ded).
- [x] Crear README + CHANGELOG + GDD + Manual.

> [!IMPORTANT]
> En modo plan no se crea DB ni código. Solo docs. Pero v1.3 ya tiene código — no borrar `nomina.db` sin backup.

> [!TIP]
> Siguiente paso sugerido: marcar Contabilidad/Legal/TI como done solo con firma o correo de aprobación adjunto.
