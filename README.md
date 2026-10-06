# README — Autorización y Liquidación de Nómina por Horas
**Versión:** v1.4 docs · **Código real:** v1.3 Python stdlib + SQLite · **Zona:** America/Bogota · **Estado:** MVP verificado local

> [!NOTE]
> Fuente de verdad del cálculo: `app.py:37-53` + `app.py:23-24` (params). UI en `index.html:1-101`. Docs sincronizados a 3 deducciones + base IBC.

## 1. Qué es
MVP web para autorizar y liquidar nómina por horas con recargos legales Colombia (Ley 2466/2025), subsidio por hijos y 3 deducciones sobre base IBC. Flujo `Borrador → En revisión → Autorizada → Enviada` con snapshot de parámetros y log de envíos.

## 2. Stack real (no plan TS)
- Backend: Python 3 stdlib `http.server + sqlite3`, cero dependencias. `app.py:6-13`
- DB: SQLite archivo `nomina.db`, `WAL ON + FK ON`. `app.py:56-61`
- Frontend: `index.html` único, CSS inline, JS fetch a `/api/*`. Sin build.
- Persistencia: `employees + payslips + app_params + send_log`. `app.py:64-91`

> [!IMPORTANT]
> El plan antiguo TS + Drizzle + better-sqlite3 queda archivado como alternativa. No implementado. Ver `docs/GDD_DECISIONES.md`.

## 3. Quickstart
```bash
python3 app.py --port 8000
python3 app.py --port 8000 --force   # libera 8000 si está ocupado y arranca
python3 app.py --help                 # ver flags
# abrir http://localhost:8000/
# botón "Cargar ejemplo" crea Ana Pérez si DB vacía
# Front responsive: cards en móvil ≤700px, params 3 ded en % directo con total vivo
```
- Salud: `GET /api/health` → `{"ok":true}`
- Puerto ocupado sin `--force`: sale 1 con ayuda (`lsof -ti :8000 | xargs kill -9`, `fuser -k 8000/tcp` o `--port 8001`). Con `--force`: TERM → espera 6s → KILL si hace falta. Verificado en 8771/8772. `app.py:360-448`
- Backup: copiar `nomina.db*` antes de migrar o cambiar params.
- Reset demo: detener server, borrar `nomina.db*`, reiniciar.

## 4. Fórmula vigente (base IBC)
```text
bruto = h_ord*tarifa + h_noct*tarifa*1.35 + h_dom*tarifa*1.90
subsidio = 0/250.000/400.000/600.000 por 0/1/2/3+ hijos — O(1)
base IBC = bruto (recargos SÍ son salario, subsidio NO)
ded = base*0.04 + base*0.04 + base*0.00522 (salud+pensión+ARL)
neto = base - ded + subsidio
```
Ejemplo RN-06 verificado `app.py:liquidar`: tarifa 20.000, 150/10/8h, 1 hijo → `bruto 3.574.000 + sub 250.000 - ded 304.576 = neto 3.519.424`.

> [!WARNING]
> ARL la paga legalmente el empleador. Aquí se descuenta por requisito del ejercicio. Parametrizable a 0. Caja (2%) eliminada en v1.3 — si contabilidad la exige, reactivar como 4ta ded.

## 5. Flujo y reglas
- Solo `Autorizada` puede pasar a `Enviada` (mock log, no SMTP real). `app.py:223-253`
- Edición bloqueada en `En revisión/Autorizada/Enviada` → 409. `app.py:267-269`
- Sin `tarifa>0` bloquea crear. Horas `>=0`, hijos entero `>=0`. `app.py:102-121`
- Snapshot de params en `En revisión/Autorizada`. Nunca recalcular una autorizada. `app.py:239-241`

## 6. API mínima
| Método | Ruta | Uso |
|---|---|---|
| GET | `/`, `/index.html` | UI |
| GET | `/api/health`, `/api/params`, `/api/employees`, `/api/logs` | Lectura + diagnóstico |
| POST | `/api/employees` | Crear (409 si email duplicado) |
| PUT | `/api/employees/:id` | Editar solo en Borrador |
| POST | `/api/employees/:id/estado` | Avanzar flujo lineal |
| PUT | `/api/params` | Ajustar % y recargos (versiona manual) |
| POST | `/api/seed` | Cargar ejemplo si vacío |

## 7. Estructura repo
```text
app.py                  # Servidor HTTP, motor de cálculo, SQLite y gestión de puerto
index.html              # Interfaz web responsiva
nomina.db               # Base de datos SQLite (WAL + FK)
TODO.md                 # Tareas y pendientes
CHANGELOG.md            # Registro histórico de versiones
docs/                   # Documentación técnica y especificaciones
  ├── SRS_FUNCIONAL.md      # Requerimientos funcionales y reglas de negocio
  ├── TDD_TECNICO.md        # Arquitectura técnica, endpoints y pruebas
  ├── DICCIONARIO_DATOS.md  # Modelo relacional y campos
  ├── GDD_DECISIONES.md     # Registro de decisiones de diseño (ADRs)
  ├── MANUAL_OPERATIVO.md   # Guía operativa y troubleshooting
  ├── MODELO_NEGOCIO.md     # Justificación de negocio y casos de uso
  └── ROADMAP.md            # Fases de evolución del sistema
```

## 8. Legal CO vigente Oct-2026
- Nocturna 7pm–6am desde 25-dic-2025. Recargo +35% → 1.35.
- Dominical/festivo diurno +90% → 1.90 (1-jul-2026 a 30-jun-2027). Sube a 2.0 el 1-jul-2027.
- Jornada máxima 42h/sem desde 15-jul-2026.
- Detalle fuentes y gradualidad en `docs/SRS_FUNCIONAL.md §2`.

## 9. Docs relacionados
- Funcional: `docs/SRS_FUNCIONAL.md` · Técnico: `docs/TDD_TECNICO.md` · Datos: `docs/DICCIONARIO_DATOS.md`
- Plan: `docs/ROADMAP.md` · Pendientes: `TODO.md` · Cambios: `CHANGELOG.md` · Decisiones: `docs/GDD_DECISIONES.md` · Uso: `docs/MANUAL_OPERATIVO.md` · Negocio: `docs/MODELO_NEGOCIO.md`

> [!TIP]
> Siguiente paso sugerido: validar con contabilidad el neto 3.519.424 sin caja y congelar `v2026-10-3ded`.
