# SRS Funcional — Autorización y Liquidación de Empleados
**Empresa:** Financiera y contable | **Modo:** Formal detallada | **Zona:** America/Bogota | **Versión:** v1.4 docs (código v1.3 Python stdlib + SQLite + base IBC + 3 ded)

> [!NOTE]
> Sincronizado con `app.py:1-312` + `index.html:1-101`. Corrige ejemplo RN-06 a 3 ded (neto 3.519.424). Versiones previas con 4 ded (caja) quedan en `CHANGELOG.md`.

## 1. Objetivo
Autorizar y liquidar nómina por horas con recargos legales CO, subsidio por hijos no salarial y 3 deducciones sobre base IBC, con envío registrado y trazabilidad por snapshot.

**Alcance v1.3:** CRUD empleados, tarifa manual, 3 tipos hora, motor IBC, flujo 4 estados, params versionados, log envíos, UI única.
**Fuera de alcance:** 7 tipos full extras, ARL por riesgo I-V, SMTP real + PDF, ERP, multi-empresa, auth usuarios.

## 2. Investigación Colombia — fines de semana y nocturnas (Oct-2026 vigente)
Fuentes: CST Art.160/168/179, Ley 2466/2025 Art.10/14, Buk/Actualícese/Gerencie 2026.

- **Franja nocturna:** 7:00 p.m. – 6:00 a.m. desde 25-dic-2025 (antes 9 p.m.).
- **Jornada máxima:** 42h/sem desde 15-jul-2026 (antes 44h). Hora ordinaria ref = salario_mensual / 235 aprox.
- **Recargo nocturno ordinario:** +35% factor 1.35.
- **Dominical/festivo diurno ordinario:** +90% factor 1.90 vigente 1-jul-2026 a 30-jun-2027. Gradual: 75% → 80% (1-jul-2025) → 90% (1-jul-2026) → 100% (1-jul-2027).
- **Referencia full (no implementada, v2):** extra diurna 1.25, extra nocturna 1.75, extra diurna dom 2.15, extra nocturna dom 2.65, recargo nocturno dom 2.25.

> [!IMPORTANT]
> Decisión Simple 3 tipos: solo `ordinaria (1.0) + nocturna (1.35) + dominical/festiva diurna (1.90)`. Suficiente para MVP y auditable. Full 7 tipos queda para v2. Ver `GDD_DECISIONES.md D-02`.

### 2.1 Base IBC (hallazgo clave v1.3)
Recargos nocturnos/dominicales y horas extras **sí son salario** y suman a la base de aportes (IBC). Subsidio por hijos y auxilio de transporte **no** entran a la base. Implementado como `base = bruto` en `app.py:44`.

## 3. Roles y permisos
| Rol | Crea | Edita | A revisión | Autoriza | Envía | Nota |
|---|---|---|---|---|---|---|
| Auxiliar | x | x (solo Borrador) | x | - | - | Carga horas/tarifa |
| Financiero | - | - | - | revisa | - | Valida cálculo vs params |
| Gerente | - | - | - | x | x | Solo `Autorizada` envía |

Sin auth real en MVP — rol es procedimental, no enforced por código. V1.1: agregar usuario + auditoría quién autorizó.

## 4. Reglas de negocio v1.3 detalladas

**RN-01 Cargos:** `gerente | administrativo | operario` solo clasifica, no define tarifa. CHECK en DB `app.py:69`. Sin tabla salarial por cargo.

**RN-02 Tarifa manual única:**
`tarifa_ordinaria_manual > 0` obligatoria por empleado, editable solo en Borrador. No hay base por cargo. Sin tarifa → 400 `Tarifa debe ser > 0`. Derivadas auto: `tarifa_noct = tarifa*1.35`, `tarifa_dom = tarifa*1.90`. Validado en `app.py:110-111`.

**RN-03 Bruto con recargos (simple):**
```text
bruto = (h_ord * tarifa) + (h_noct * tarifa * 1.35) + (h_dom * tarifa * 1.90)
h_* >= 0, admite 0.5 pasos en UI. O(k) k=3 tipos, total O(n) nómina.
```
Implementación `app.py:40-42`. Redondeo a entero COP al retornar.

**RN-04 Subsidio hijos (no salarial, lookup O(1)):**
0→0, 1→250.000, 2→400.000, 3+→600.000 COP. `app.py:27-34`. No suma a base IBC. No depende de tarifa ni horas.

**RN-05 Deducciones 3 sobre base IBC (subsidio no suma base):**
salud 4% + pensión 4% + ARL 0.522% Nivel I = 8.522% efectivo. Todos configurables vía `PUT /api/params`. `app.py:23-24`, `app.py:45-48`.
```text
neto = base - (d_salud+d_pension+d_arl) + subsidio
```

> [!WARNING]
> ARL/caja legalmente las paga el empleador. Aquí ARL se descuenta por requisito del ejercicio. Parametrizable a 0%. Caja 2% eliminada en v1.3 — reactivable si lo exige contabilidad.

**RN-06 Ejemplo canónico corregido (3 ded):** tarifa 20.000/h, h_ord 150, h_noct 10, h_dom 8, 1 hijo:
```text
bruto = 150*20000 (=3.000.000) + 10*20000*1.35 (=270.000) + 8*20000*1.90 (=304.000) = 3.574.000
subsidio = 250.000
d_salud = 3.574.000*0.04 = 142.960
d_pension = 142.960
d_arl = 3.574.000*0.00522 = 18.656
total_ded = 304.576
neto = 3.574.000 - 304.576 + 250.000 = 3.519.424
```
Verificado ejecutando `app.liquidar` — coincide con UI `index.html:79`. Valor previo 3.447.944 correspondía a 4 ded con caja, obsoleto.

**RN-07 Inmutabilidad por estado:** edición `PUT` bloqueada si `payslips.estado IN (En revisión, Autorizada, Enviada)` → 409 `Bloqueada por estado`. `app.py:267-269`.

**RN-08 Transición lineal estricta:** `Borrador → En revisión → Autorizada → Enviada`. Sin saltos ni retrocesos. `NEXT` en `app.py:21`, validado `app.py:234`. Error 400 `Transición inválida`.

**RN-09 Snapshot:** al pasar a `En revisión`/`Autorizada` se guarda `params JSON` en `payslips.snap`. `app.py:239-241`. En `Enviada` se liquida con ese snapshot, no con params actuales. Garantiza auditoría ante cambio de % o recargos (ej. dom 1.90→2.0 en jul-2027).

**RN-10 Envío mock:** `Enviada` escribe en `send_log` línea `ENVIADA a {email} | base $X - ded $Y + sub $Z = NETO $W`. `app.py:246-250`. No SMTP/PDF real. Reintentos y cola quedan para v1.1.

## 5. CRUD detallado
Campos: id `emp_<hex8>`, nombre (trim, req, max 120 UI), email único (regex `app.py:19`, max 160), cargo CHECK, tarifa REAL `>0` NOT NULL, h_ord/h_noct/h_dom REAL `>=0` DEFAULT 0, num_hijos INT `>=0` DEFAULT 0, activo 0/1, updated_at ISO UTC.
- Crear: `POST /api/employees` 201 + `{id}`. 400 validación, 409 email duplicado. Crea `payslips` en Borrador. `app.py:185-208`
- Leer: `GET /api/employees` orden `ORDER BY nombre` O(n log n) + cálculo por fila O(n). `app.py:163-177`
- Actualizar: `PUT /api/employees/:id` parcial con COALESCE. `app.py:276-283`
- Eliminar: no implementado. Sin borrado físico con liquidaciones (regla diccionario).
- Activación: flag `activo` no excluye del cálculo, solo informativo en UI.

## 6. Flujo + envío + UI
```text
Borrador → En revisión → Autorizada → Enviada
```
- UI botones por fila: Editar / A revisión / Autorizar / Enviar con `disabled` según estado. `index.html:82-86`
- Solo autorizada genera log + desglose. Log visible en `#log` vía `GET /api/logs` (últimas 30). `index.html:88`, `app.py:178-182`
- Seed demo: `POST /api/seed` crea Ana Pérez 20000/150/10/8/1hijo si vacío. `app.py:209-222`

## 7. Persistencia Opción 1 (real Python, no Drizzle)
SQLite archivo `nomina.db`, `WAL ON`, `FK ON`. Tablas `employees/payslips/app_params/send_log`. Backup = copiar archivo. Ver `TDD_TECNICO.md §3` y `DICCIONARIO_DATOS.md`.

## 8. Criterios de aceptación v1.3
- [x] Crear empleado sin tarifa → 400.
- [x] RN-06 da neto 3.519.424 en API y UI.
- [x] Transición Borrador→Autorizada directa → 400.
- [x] Editar en En revisión → 409.
- [x] Cambiar params no altera Autorizada previa (snapshot).
- [ ] Contabilidad confirma 3 ded + rec 1.35/1.90 y ejemplo.
- [ ] Legal prevé cambio dom 90%→100% jul-2027.

> [!TIP]
> Siguiente paso sugerido: correr `python3 app.py`, crear caso RN-06 y adjuntar captura del neto a contabilidad para congelar params.
