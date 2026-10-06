# CHANGELOG — Nómina por horas
**Zona:** America/Bogota · Formato: `Versión — fecha — Qué / Vs anterior`

## [v1.4.1-structure] — 2026-10-06
### Qué
- Organización limpia de repositorio: agrupación de especificaciones técnicas y funcionales en subdirectorio `docs/` (`SRS_FUNCIONAL.md`, `TDD_TECNICO.md`, `DICCIONARIO_DATOS.md`, `GDD_DECISIONES.md`, `MANUAL_OPERATIVO.md`, `MODELO_NEGOCIO.md`, `ROADMAP.md`).
- Conservación de `app.py`, `index.html`, `nomina.db`, `README.md`, `CHANGELOG.md` y `TODO.md` en raíz para ejecución directa con fricción cero.
- Sincronización de enlaces relativos y diagrama de estructura de directorios en `README.md`.
### Vs anterior
- Antes: 14 archivos planos en la raíz del repositorio mezclando código de ejecución con 9 documentos markdown.
- Ahora: Raíz limpia con puntos de entrada directos y documentación modularizada en `docs/`.
### Verificación
- `git status` con renames preservados; ejecución `python3 app.py --help` verificada exitosa.

## [v1.3.2-front] — 2026-10-06
### Qué
- Front responsive sin overflow: `overflow-x:clip`, cards ≤700px con `data-label`, `row3` 1 col ≤560px, header/nav wrap, `pre.log` wrap, `esc()` anti-XSS.
- Params 3 ded en % directo (`4/4/0.522` + total vivo `8.522%`); backend `PUT /api/params` acepta fracción, `% >1` o `"0.522%"`, valida ded 0–100% y recargos ≥1.
### Vs anterior
- Antes: inputs fracción `0.04`, tabla `min-width:780px` se salía en móvil, sin total, sin validación rangos.
- Ahora: `index.html` cards + % + validación front/back. Neto RN-06 intacto 3519424.
### Verificación
- `PUT {"salud":"4%","arl":"0.522%"}` → `0.04/0.00522 OK`; `GET /` 200 16kB; `py_compile OK`.

## [v1.3.1-port] — 2026-10-06
### Qué
- `app.py` libera puerto al iniciar: `--force / --free-port` mata proceso previo (lsof/fuser/ss, TERM→KILL), chequeo `is_port_in_use` por `connect_ex` O(1) sin falsos TIME_WAIT, `allow_reuse_address`, `--help` y mensaje con fix manual.
- Sync docs: README quickstart + MANUAL arranque/troubleshooting.
### Vs anterior
- Antes: `HTTPServer` directo, `OSError Address already in use` sin ayuda, chequeo por `bind` propenso a TIME_WAIT.
- Ahora: `app.py:360-448`, salida 1 con guía o takeover con `--force`. Cero deps.
### Verificación
- `8771`: sin `--force` sale 1 con ayuda; tras kill queda libre.
- `8772`: A sirve `health OK`, B `--force` imprime `liberado` y retoma `health OK`, A muere.

## [v1.4-docs] — 2026-10-06
### Qué
- Expansión formal detallada de toda la documentación con lo ya existente.
- Crea `README.md`, `CHANGELOG.md`, `GDD_DECISIONES.md`, `MANUAL_OPERATIVO.md`.
- Sincroniza `SRS/TDD/Diccionario/ROADMAP/TODO` a código real v1.3.
### Vs anterior
- Antes: TDD describía TS+Drizzle+4 ded, Diccionario v1.2 con caja, RN-06 3.447.944, sin README/GDD/Manual.
- Ahora: todo a Python stdlib+SQLite+3 ded+base IBC, RN-06 3.519.424, 9 docs sync.
### Verificación
- `python3 -c "import app; print(app.liquidar(...))"` → neto 3519424 coincide con RN-06.

## [v1.3-code] — 2026-10 (app.py:1 + index.html:1)
### Qué
- MVP Python stdlib + SQLite + base IBC + solo 3 ded (salud/pensión/ARL).
- `liquidar()` con `base=bruto`, `DEFAULT_PARAMS v2026-10-3ded`, flujo 4 estados, snapshot, send_log.
### Vs anterior
- Antes v1.2 docs: 4 ded con caja 2%, neto 3.447.944, plan TS sin código.
- Ahora: elimina caja, neto 3.519.424 (+71.480), código real corre en :8000.
### Archivos
- `app.py`, `index.html`, `nomina.db`, `SRS_FUNCIONAL.md v1.3`.

## [v1.2-docs] — previa
- Tarifa manual única, 3 tipos 1.0/1.35/1.90, 4 ded 10.522%, SQLite Opción 1 Drizzle plan, MVP HTML LocalStorage referencia.

## [v1.0-init] — previa
- Esqueleto SRS/TDD/ROADMAP/TODO, Ley 2466 Art.10/14, jornada 42h.

> [!NOTE]
> Convención futura: título commit EN `docs(scope): ...` + cuerpo ES con Qué/Vs anterior/Archivos/Verificación.
