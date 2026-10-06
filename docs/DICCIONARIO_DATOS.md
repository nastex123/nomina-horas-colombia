# Diccionario de Datos — v1.4 detallado (SQLite real Python + base IBC 3 ded)
**DB:** `nomina.db` (archivo, WAL ON, FK ON) · **Código:** `app.py:56-91` · **Zona:** America/Bogota

> [!NOTE]
> Tarifa 100% manual. Sin tablas por cargo. Base IBC = bruto con recargos. Sincronizado a 3 ded (sin caja). Plan Drizzle archivado.

## 1. employees (SQLite real)
| Campo | Tipo SQLite | Constraints | Regla negocio | Ejemplo |
|---|---|---|---|---|
| id | TEXT PK | PRIMARY KEY | `emp_` + 8 hex uuid `app.py:193` | emp_a3f9c1e2 |
| nombre | TEXT NOT NULL | NOT NULL, trim | requerido, max 120 UI | Ana Pérez |
| email | TEXT UNIQUE NOT NULL | UNIQUE NOT NULL + regex | email válido, destino envío, 409 si duplicado | ana@empresa.co |
| cargo | TEXT NOT NULL | CHECK IN (gerente,administrativo,operario) | solo clasifica | operario |
| tarifa | REAL NOT NULL | CHECK(tarifa>0) | la ingresas tú = hora ordinaria, editable solo Borrador | 20000 |
| h_ord | REAL NOT NULL | DEFAULT 0 CHECK(>=0) | diurnas lun-sáb 6am-7pm | 150 |
| h_noct | REAL NOT NULL | DEFAULT 0 CHECK(>=0) | 7pm-6am ×1.35 | 10 |
| h_dom | REAL NOT NULL | DEFAULT 0 CHECK(>=0) | dom/fest diurno ×1.90 | 8 |
| num_hijos | INTEGER NOT NULL | DEFAULT 0 CHECK(>=0) | entero >=0, define subsidio | 1 |
| activo | INTEGER NOT NULL | DEFAULT 1 (0/1) | informativo, no excluye cálculo | 1 |
| updated_at | TEXT NOT NULL | ISO UTC | `datetime.now(timezone.utc).isoformat()` | 2026-10-06T... |

Fila ejemplo:
```json
{"id":"emp_a3f9c1e2","nombre":"Ana Pérez","email":"ana@empresa.co","cargo":"administrativo","tarifa":20000,"h_ord":150,"h_noct":10,"h_dom":8,"num_hijos":1,"activo":1}
```

## 2. app_params (singleton vigente)
| Campo | Tipo | Default v1.3 | Nota |
|---|---|---|---|
| version | TEXT PK | `v2026-10-3ded` → `v2026-10-3ded-manual` tras PUT | snapshot por liquidación |
| salud | REAL NOT NULL | 0.04 | empleado, configurable 0-1 |
| pension | REAL NOT NULL | 0.04 | empleado |
| arl | REAL NOT NULL | 0.00522 | Nivel I, aquí descontada por requisito |
| rec_noct | REAL NOT NULL | 1.35 | Ley 2466, versionar |
| rec_dom | REAL NOT NULL | 1.90 | 1.90→2.0 en jul-2027, versionar |

> [!WARNING]
> Sin columna `caja` en v1.3. Si se reactiva, agregar `caja REAL DEFAULT 0.02` + migrar snapshots viejos con `caja=0`.

## 3. payslips (1 vigente por empleado en MVP)
| Campo | Tipo | Nota |
|---|---|---|
| employee_id | TEXT PK → FK employees(id) ON DELETE CASCADE | 1:1 en MVP, no histórico |
| estado | TEXT NOT NULL DEFAULT 'Borrador' | Borrador/En revisión/Autorizada/Enviada |
| snap | TEXT NULL (JSON) | snapshot params al pasar a En revisión/Autorizada |
| updated_at | TEXT NOT NULL | ISO UTC |

`snap` ejemplo:
```json
{"salud":0.04,"pension":0.04,"arl":0.00522,"recNoct":1.35,"recDom":1.9,"version":"v2026-10-3ded"}
```
Cálculo derivado (no columnas, se computa al leer `app.py:170-176`): `bruto, base, sub, dSalud, dPen, dArl, total, neto`.

V2 histórico propuesto:
```sql
CREATE TABLE payslips_hist(id TEXT PRIMARY KEY, employee_id TEXT REFERENCES employees(id),
 periodo TEXT NOT NULL, -- YYYY-MM
 horas_json TEXT NOT NULL, tarifa_aplicada REAL NOT NULL,
 bruto REAL, subsidio REAL, d_salud REAL, d_pension REAL, d_arl REAL,
 neto REAL, estado TEXT, params_snapshot TEXT NOT NULL);
CREATE INDEX idx_pay_emp_period ON payslips_hist(employee_id, periodo);
```

## 4. send_log (auditoría envíos mock)
| Campo | Tipo | Ejemplo |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | 1 |
| ts | TEXT NOT NULL ISO UTC | 2026-10-06T14:00:00+00:00 |
| msg | TEXT NOT NULL | `ENVIADA a ana@empresa.co \| Ana Pérez \| base $3574000 - ded $304576 (salud $142960 pen $142960 arl $18656) + sub $250000 = NETO $3519424` |

Lectura: `SELECT ts,msg ORDER BY id DESC LIMIT 30` `app.py:180`. Retención: sin purga en MVP. V1.1: rotar >10k filas.

## 5. Índices y pragmas
```sql
PRAGMA journal_mode=WAL; -- concurrencia lectura
PRAGMA foreign_keys=ON;   -- integridad
CREATE INDEX IF NOT EXISTS idx_emp_email ON employees(email); -- O(log n)
```
Falta en MVP: índice `idx_pay_estado(estado)`, índice compuesto `(activo, cargo)` para reportes. Agregar en v1.1 si n>1k.

## 6. Reglas de integridad
- No NULL en `tarifa`, `email`, `nombre`, `cargo`.
- `tarifa>0`, `h_*>=0`, `num_hijos>=0` — doble capa: CHECK SQL + `validate_emp()` `app.py:102-121`.
- No borrado físico con payslips: sin `DELETE` implementado; si se agrega, usar borrado lógico `activo=0` o bloquear si tiene `payslips` no-Borrador.
- Email UNIQUE case-sensitive en SQLite — normalizar a lower en app antes de insert (deuda v1.1).
- Redondeo: `round()` a entero COP solo en salida `liquidar`, no en acumulados intermedios.

> [!WARNING]
> No NULL en tarifa_manual. No borrado físico con payslips. No recalcular snapshot.

> [!TIP]
> Siguiente paso sugerido: agregar `CHECK(salud BETWEEN 0 AND 1)` en `app_params` para evitar params inválidos vía PUT.
