# MODELO DE NEGOCIO — Liquidación Nómina por Horas v1.0
**Formato:** Ejecutivo completo · **Zona:** America/Bogota · **Base producto:** `SRS_FUNCIONAL.md` + `app.py:37-53` + `TDD_TECNICO.md` · **Fecha:** 2026-10-06

> [!NOTE]
> MVP real: Python stdlib + SQLite, base IBC + 3 ded, flujo con snapshot. Neto RN-06 3.519.424 como caso demostración comercial.

## 1. Problema y propuesta de valor
Pymes de 5–50 empleados liquidan horas nocturnas/dominicales en Excel con recargos desactualizados (Ley 2466/2025: nocturna 7pm–6am 1.35, dom 1.90→2.0 en jul-2027) y errores de base IBC (recargos sí suman, subsidio no).
Propuesta: web local cero-instalación que autoriza, liquida con snapshot auditable y registra envíos en 1 comando (`python3 app.py --port 8000 --force`).

## 2. Segmentos
| Segmento | Dolor | Disposición pago |
|---|---|---|
| Pymes operativas 10–30 (logística, seguridad, manufactura) | turnos nocturnos/dom, reclamos | Alta, paga por evitar sanciones |
| Contadores independientes (5–20 clientes) | multi-empresa en Excel | Alta, paga por cliente |
| SENA/educativo + micro 1–5 | aprender Ley 2466 sin costo | Baja, puerta a premium |
No-clientes: grandes con ERP (SAP/Workday) — se atacan en v2 con reportes ERP.

## 3. Producto y diferenciación
- Motor 3 tipos O(k) k=3, nómina O(n), subsidio O(1). `app.py:37-53`
- Snapshot params por liquidación (auditoría ante cambio dom 2.0). `app.py:239-241`
- SQLite archivo + backup copia, sin licencias DB. `app.py:56-91`
- Arranque robusto `--force` (lsof/fuser, TERM→KILL) reduce soporte inicial.
Diferencial vs Excel/SIIGO: recargos Ley 2466 versionados + flujo autorización + log, no solo cálculo.

## 4. Canales y go-to-market
- Directo: contadores aliados (comisión 20% primer año), demo RN-06 en vivo.
- Contenido: guía Ley 2466 + calculadora base IBC (SEO es-CO).
- Educativo: convenio SENA, versión aula gratis con marca.
- O(n) onboarding: 1h instalación + carga ejemplo `POST /api/seed`.

## 5. Ingresos y pricing COP (propuesto)
| Plan | Precio/mes | Incluye | Ideal |
|---|---|---|---|
| Aula/Local | 0 | 1 empresa ≤5 empleados, log mock | SENA/demo |
| Micro | 39.000 | 1 empresa ≤10, backup manual | micro |
| Pyme | 89.000 | 1 empresa ≤30, multi-usuario básico, export CSV | core |
| Contador | 149.000 | 5 empresas ≤50 c/u, snapshots comparables | socios |
| Pago por uso | 1.900/payslip Autorizada | sin suscripción | picos temporada |
Add-ons v1.1/v2: PDF+SMTP real +25.000/mes, histórico por periodo +30.000/mes, ARL multi-riesgo +20.000/mes.

**Unit economics ejemplo (Pyme 20 empleados, plan Pyme):**
```text
Ingreso: 89.000/mes = 4.450/empleado/mes
Costo infra local: ~0 (PC cliente) + soporte 15min/mes ≈ 12.500 a 50.000/hora
Margen bruto: ~75–85%. O(1) por payslip extra (solo cómputo).
LTV 24 meses ≈ 2.136.000, CAC objetivo < 250.000 (demo + referido).
```
A escala cloud v2: hosting ~60.000/mes por 50 empresas → costo 1.200/empresa, margen >90%.

## 6. Costos y operación Big-O
| Rubro | Costo | Big-O |
|---|---|---|
| Dev MVP | hundido (SENA) | O(1) |
| Soporte instalación (puerto/DB) | 0.5h/cliente tras `--force` | O(n) clientes, decreciente |
| Cálculo nómina | CPU despreciable | O(n) empleados, O(1) subsidio |
| Almacenamiento | 1 archivo SQLite <10MB/1000 slips | O(n) |
| Legal/contable actualización anual | 4–8h (ej. dom 2.0) | O(1) |
Punto equilibrio: ~8 clientes Pyme cubren 1 soporte medio tiempo.

## 7. Métricas (v1.1 instrumentar)
MRR, churn mensual <5%, NPS demo, % Autorizadas sin devolución, tiempo Borrador→Enviada <48h, CAC/LTV >4. Tabla `send_log` ya da conteo Enviadas para facturar por uso.

## 8. Riesgos
| Riesgo | Mitigación |
|---|---|
| Cambio legal no aplicado (dom 2.0) | versionado params + alerta calendario, test en `TODO` |
| ARL descontada vs ley empleador paga | pricing con toggle + nota contable `SRS RN-05` |
| Sin auth expone salarios | solo local hasta v1.1 token gerente, cláusula contrato |
| Excel gratis como ancla precio | demo error IBC cuantificado en COP (ej. 71.480 caja) |

> [!IMPORTANT]
> Precios sin IVA, sujetos a firma contable de 3 ded y concepto legal. No constituye asesoría tributaria.

> [!WARNING]
> No operar multi-empresa real sobre un solo `nomina.db` sin separar por archivo/empresa hasta v2 histórico.

> [!TIP]
> Siguiente paso sugerido: pilotar 2 pymes + 1 contador 30 días en plan Pyme/Contador y medir Borrador→Enviada y disposición a pagar 89.000/149.000.
