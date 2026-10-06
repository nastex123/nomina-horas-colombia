# TDD Técnico — Liquidación (Python stdlib + SQLite + base IBC + 3 ded)
**Stack congelado real:** Python 3 stdlib + SQLite archivo + HTML único. Sin TS/Drizzle (plan archivado). Jornada 42h. **Versión:** v1.4 docs / código v1.3.

> [!NOTE]
> Complementa `SRS_FUNCIONAL.md` v1.4. Motor simple 3 tipos + base IBC. Fuente: `app.py:1-312`.

## 1. Arquitectura real
```text
index.html (form + tabla + params + log)
  │ fetch JSON
  ▼
Handler http.server (GET/POST/PUT) app.py:124-301
  ├─ Motor cálculo liquidar() + subsidio() app.py:27-53  O(n) nómina, O(1) subsidio
  ├─ Validación validate_emp() app.py:102-121
  └─ SQLite nomina.db (WAL+FK) app.py:56-91
       employees / payslips / app_params / send_log
```
Sin ORM, sin deps, sin build. Concurrencia: single-thread `HTTPServer`. Suficiente para MVP local / SENA. V1.1: migrar a `ThreadingHTTPServer` + cola reintentos.

## 2. Contratos Python vigentes
```python
# app.py:23-34
DEFAULT_PARAMS = {"salud":0.04, "pension":0.04, "arl":0.00522,
                  "recNoct":1.35, "recDom":1.90, "version":"v2026-10-3ded"}
def subsidio(num_hijos:int)->int:  # O(1) lookup
    ...
# app.py:37-53
def liquidar(emp:dict, p:dict)->dict:
    tarifa=float(emp["tarifa"])
    bruto=(float(emp["hOrd"])*tarifa
           +float(emp["hNoct"])*tarifa*float(p["recNoct"])
           +float(emp["hDom"])*tarifa*float(p["recDom"]))
    sub=subsidio(int(emp["numHijos"]))
    base=bruto  # IBC: recargos sí, subsidio no
    d_salud=base*float(p["salud"]); d_pension=base*float(p["pension"]); d_arl=base*float(p["arl"])
    total=d_salud+d_pension+d_arl
    neto=base-total+sub
    return {"bruto":round(bruto),"base":round(base),"sub":round(sub),
            "dSalud":round(d_salud),"dPen":round(d_pension),"dArl":round(d_arl),
            "total":round(total),"neto":round(neto)}
```
Equivalencia TS (solo referencia, no implementada):
```ts
type Cargo='gerente'|'administrativo'|'operario';
interface Employee{id:string;nombre:string;email:string;cargo:Cargo;tarifaManual:number;hOrd:number;hNoct:number;hDom:number;numHijos:number;activo:boolean}
interface Params{saludPct:number;pensionPct:number;arlPct:number;recNoct:1.35;recDom:1.90;version:string}
```

## 3. SQLite real (implementado) vs plan Drizzle (archivado)
**Real `app.py:64-91`:**
```sql
PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS employees(
  id TEXT PRIMARY KEY, nombre TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  cargo TEXT NOT NULL CHECK(cargo IN ('gerente','administrativo','operario')),
  tarifa REAL NOT NULL CHECK(tarifa>0),
  h_ord REAL NOT NULL DEFAULT 0 CHECK(h_ord>=0),
  h_noct REAL NOT NULL DEFAULT 0 CHECK(h_noct>=0),
  h_dom REAL NOT NULL DEFAULT 0 CHECK(h_dom>=0),
  num_hijos INTEGER NOT NULL DEFAULT 0 CHECK(num_hijos>=0),
  activo INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payslips(
  employee_id TEXT PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
  estado TEXT NOT NULL DEFAULT 'Borrador', snap TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_params(
  version TEXT PRIMARY KEY, salud REAL NOT NULL, pension REAL NOT NULL,
  arl REAL NOT NULL, rec_noct REAL NOT NULL, rec_dom REAL NOT NULL);
CREATE TABLE IF NOT EXISTS send_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, msg TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_emp_email ON employees(email);
```
Diferencias vs plan antiguo: `payslips` usa `employee_id PK` (1 slip vigente por empleado, no histórico por periodo), sin `periodo YYYY-MM`, sin `horas_json` separado (lee de employees), `app_params` sin caja, `send_log` en vez de cola. V2: migrar a `payslips(id PK, employee_id FK, periodo, horas_json, ...)` para histórico.

## 4. API mínima (implementada `app.py:155-298`)
| Método | Ruta | Body | OK | Error |
|---|---|---|---|---|
| GET | `/`, `/index.html` | - | 200 html | 404 si falta archivo |
| GET | `/api/health` | - | `{"ok":true,"db":"nomina.db"}` | - |
| GET | `/api/params` | - | params vigentes | - |
| GET | `/api/employees` | - | lista + `calc` con snapshot o vigente | - |
| GET | `/api/logs` | - | últimas 30 líneas | - |
| POST | `/api/employees` | nombre,email,cargo,tarifa,hOrd,hNoct,hDom,numHijos,activo | 201 `{id}` | 400 validación, 409 email |
| PUT | `/api/employees/:id` | parcial | `{ok:true}` | 404, 400, 409 bloqueada |
| POST | `/api/employees/:id/estado` | `{estado}` | `{ok:true,estado}` | 400 transición, 404 |
| PUT | `/api/params` | salud,pension,arl,recNoct,recDom | `{ok:true}` | - |
| POST | `/api/seed` | - | `{ok:true}` | - |
Idempotencia: `seed` solo si `COUNT==0`. `send` no reenvía duplicado salvo retroceso manual (no hay). Errores canónicos: `Falta {campo}, Email inválido, Cargo inválido, Tarifa debe ser >0, Horas >=0, Hijos entero >=0, Email duplicado, No existe, Transición inválida X->Y, Bloqueada por estado`.

## 5. Validaciones y seguridad MVP
- Email regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` `app.py:19`. Trim en insert. UNIQUE con 409.
- `tarifa>0`, horas `>=0` (acepta float, UI step 0.5/1), hijos `int>=0`.
- `activo` coerce a 0/1.
- Sin auth, sin rate-limit, sin HTTPS — solo `127.0.0.1`. No exponer a internet. V1.1: token gerente + validación servidor de `%` entre 0-1 y recargos `>=1`.
- `log_message` silenciado `app.py:300-301` — ver logs vía `/api/logs`.

## 6. Snapshot + versionado
`app_params.version` actual `v2026-10-3ded-manual` tras PUT. `payslips.snap` guarda JSON completo en cada `En revisión/Autorizada`. Lectura `GET /api/employees` usa `snap` si existe, si no params vigentes `app.py:175`. Regla: **nunca recalcular autorizada**.

## 7. Big-O y rendimiento
| Op | Complejidad | Nota |
|---|---|---|
| `liquidar` 1 emp | O(1) / O(k) k=3 | 3 multiplicaciones |
| Nómina n emps | O(n) | loop `app.py:170` |
| `ORDER BY nombre` | O(n log n) | SQLite sort |
| `subsidio` | O(1) | if-else |
| `idx_emp_email` | O(log n) | búsqueda |
| `GET /api/logs` | O(1) | LIMIT 30 |
Suficiente para <10k empleados en archivo local. WAL permite lecturas concurrentes.

## 8. Testing manual + verificación
```bash
python3 app.py --port 8000 &
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/seed
curl -s localhost:8000/api/employees | python3 -m json.tool | head -60
# RN-06 esperado: bruto 3574000, total 304576, neto 3519424
curl -s localhost:8000/api/logs
```
DoD técnico: 0 tracebacks, `nomina.db` creado, UI carga tabla, transición completa Borrador→Enviada sin 400/409 indebidos.

## 9. Backup y despliegue
- Backup: `cp nomina.db nomina.db.bak-$(date +%F)` (+ `-wal/-shm` si existen). Mensual mínimo.
- Restore: detener server, reemplazar, reiniciar `init_db()` es idempotente `IF NOT EXISTS`.
- Puertos: default 8000, override `--port`. Bind `127.0.0.1` only.

> [!IMPORTANT]
> Snapshot de `Params+recargos` en cada payslip. Nunca recalcular autorizada. Cambio dom 1.90→2.0 en jul-2027 exige nueva `version` + migración.

> [!TIP]
> Siguiente paso sugerido: crear migración `0002_historico_periodo.sql` cuando necesites más de 1 liquidación por empleado.
