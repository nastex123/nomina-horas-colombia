# 02 - Persistencia de Datos (SQLite + Python)

Script vigente: `script_persistencia_sqlite.sql` -> genera `liquidacion_nomina.db`

## 1. Decisión
SQLite archivo local, sin servidor. Ideal para documentación y prototipo SENA. `PRAGMA foreign_keys=ON` en cada conexión.

## 2. Tablas
- `cargos(id, nombre UNIQUE, tarifa_base_hora)`
- `empleados(id, nombres, apellidos, cedula UNIQUE, email UNIQUE, cargo_id FK, tarifa_hora, num_hijos, riesgo_arl I-V, fecha_ingreso, estado, cuenta)`
- `usuarios(id, empleado_id FK, email UNIQUE, password_hash, rol, intentos, bloqueado_hasta)`
- `config(clave PK, valor, descripcion)` -> SUB_H1/H2/H3, SALUD, PENSION, ARL_I..V, CAJA, REC_*
- `periodos(id, fecha_inicio, fecha_fin UNIQUE combinada, estado)`
- `horas(id, empleado_id FK, periodo_id FK UNIQUE combinada, horas_normales + campos Fase2 en 0, observacion)`
- `festivos(fecha PK, descripcion)`
- `liquidaciones(id, empleado_id FK, periodo_id FK UNIQUE combinada, tarifa_aplicada, horas_total, salario_base, ded_salud, ded_pension, ded_arl, base_neta, subsidio, neto, aporte_caja, estado, autorizado_por FK, fecha_calculo, fecha_envio)`
- `envios_log(id, liquidacion_id FK, email_destino, estado OK/FALLO, error_msg, fecha)`

## 3. Capa de persistencia Python
- `sqlite3` estándar o SQLAlchemy `sqlite:///liquidacion_nomina.db`
- DAO por entidad, transacción única: horas -> cálculo -> insert liquidación -> commit/rollback
- Borrado lógico `estado='Inactivo'`, UNIQUE evita duplicados, CHECK evita negativos
- Backup = copiar `.db`

```python
import sqlite3
con = sqlite3.connect("liquidacion_nomina.db")
con.execute("PRAGMA foreign_keys=ON")
base = horas * tarifa
arl_porc = float(get_config(f"ARL_{riesgo}"))  # ej 0.02436
base_neta = base - base*0.04 - base*0.04 - base*arl_porc
neto = base_neta + subsidio_mensual/2
con.execute("INSERT INTO liquidaciones (...) VALUES (...)", [...])
con.commit()
```

Límite: 1 app / poca concurrencia. Escalar a MySQL después solo cambia conexión.
