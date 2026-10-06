# MANUAL Operativo — MVP Liquidación v1.3.1
**Stack:** Python + SQLite + HTML único · **Zona:** America/Bogota · **Puerto:** 8000 (configurable)

> [!NOTE]
> Para rol Auxiliar/Financiero/Gerente. Sin auth — uso local `127.0.0.1` únicamente.

## 1. Iniciar
```bash
cd "/home/cohorte5/Documentos/brandonr-r/sena I"
python3 app.py --port 8000
python3 app.py --port 8000 --force   # desocupa 8000 si quedó un proceso previo
python3 app.py --help                # ayuda de flags
# abrir http://localhost:8000/
```
- Si tabla vacía: click **Cargar ejemplo** (crea Ana Pérez 20000/150/10/8/1 hijo).
- Si ves `Inicia backend...`: el server no corre o el puerto cambió.

## 2. Crear empleado
1. `#empleados` → Nombre, Email, Cargo, Hijos, Tarifa, H.ord/noct/dom.
2. **Guardar** → aparece en tabla con `Borrador` y cálculo base IBC.
3. Errores comunes: `Email duplicado` (409), `Tarifa debe ser >0` (400), `Horas >=0`.

## 3. Editar (solo Borrador)
- Click **Editar** → form se llena, cambia valores → **Guardar** (`PUT /api/employees/:id`).
- Si botón deshabilitado es porque está `En revisión/Autorizada/Enviada` (bloqueo `app.py:267`).

## 4. Autorizar y enviar
```text
Borrador --A revisión--> En revisión --Autorizar--> Autorizada --Enviar--> Enviada
```
- Cada botón avanza un paso. Sin saltos.
- Al autorizar se congela snapshot de params (aunque cambies % después, esa liquidación no cambia).
- Al enviar, revisa `#envios`: línea `ENVIADA a email | base $X - ded $Y + sub $Z = NETO $W`.

## 5. Parámetros (solo Financiero/Gerente)
- `#params`: Salud/Pensión/ARL en **% directo** (ej. `4`, `4`, `0.522`) con total en vivo `8.522%`. Recargos como factor (`1.35`, `1.90`).
- **Guardar params** → `PUT /api/params`, cambia `version` a `...-manual`. Front convierte %→fracción.
- Contrato API: fracción `0.04`, numérico `% >1` (`4`) o string `"0.522%"`. Numérico `0.522` solo = fracción 52.2%.
- Afecta solo Borradores y futuros. Autorizadas conservan snapshot.

## 6. Verificación RN-06 (prueba de humo)
Crea: tarifa 20000, ord 150, noct 10, dom 8, hijos 1 → espera:
`Base 3.574.000, Sub 250.000, Ded 304.576 (142.960+142.960+18.656), Neto 3.519.424`.

## 7. Backup / restore
```bash
cp nomina.db "nomina.db.bak-$(date +%F)"  # + .wal/.shm si existen
# restore: detener server, copiar de vuelta, reiniciar
```
Export rápido: `sqlite3 nomina.db "SELECT * FROM employees;"` o `GET /api/employees`.

## 8. Troubleshooting
| Síntoma | Causa | Fix |
|---|---|---|
| `Address already in use` | puerto ocupado por instancia previa | `python3 app.py --port 8000 --force` o manual `lsof -ti :8000 \| xargs kill -9` / `fuser -k 8000/tcp` o `--port 8001` |
| Página con scroll horizontal | viewport pequeño | Corregido v1.3.2: cards en ≤700px, `row3` a 1 col en ≤560px, `overflow-x:clip` |
| `Ded 0–100%` o `Recargos ≥ 1` | params fuera de rango | Salud/Pensión/ARL 0–100%, recargos ≥1 |
| `Transición inválida` | salto de estado | avanza paso a paso |
| `Bloqueada por estado` | editar no-Borrador | duplica empleado o devuelve en DB |
| Tabla no actualiza | fetch falla | F12 → Network, revisa `/api/health` |
| Neto distinto al esperado | params cambiados | revisa `#params` + `p_ver`, compara snapshot |

## 9. FAQ
- **¿Caja 2%?** Eliminada en v1.3. Pedir a TI reactivarla si contabilidad exige.
- **¿PDF/email real?** No, solo log. V1.1 SMTP+PDF.
- **¿Múltiples periodos?** No, 1 slip vigente por empleado. V2 histórico.
- **¿Jornada 42h?** Informativa, no bloquea si excedes 182h/mes. V2 alerta.

> [!WARNING]
> No exponer a internet ni LAN sin auth. Salarios son datos sensibles.

> [!TIP]
> Siguiente paso sugerido: imprimir §6 y pegar firma de contabilidad como acta de aceptación.
