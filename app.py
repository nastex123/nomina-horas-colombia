#!/usr/bin/env python3
"""MVP Liquidación — HTML + Python stdlib + SQLite (cero deps).
Fórmula CO v1.3: base = bruto con recargos (IBC), ded solo 3 sobre base, neto = base - ded + subsidio.
Uso: python3 app.py [--port 8000] [--force]  ->  http://localhost:8000/
  --port N     puerto a usar (default 8000).
  --force / --free-port  libera el puerto matando el proceso previo que lo ocupe.
  --help       muestra ayuda.
"""
import json
import os
import random
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "nomina.db"
HTML_PATH = BASE_DIR / "index.html"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FLOW = ["Borrador", "En revisión", "Autorizada", "Enviada"]
NEXT = {"Borrador": "En revisión", "En revisión": "Autorizada", "Autorizada": "Enviada"}

DEFAULT_PARAMS = {"salud": 0.04, "pension": 0.04, "arl": 0.00522,
                  "recNoct": 1.35, "recDom": 1.90, "version": "v2026-10-ley-colombia"}

CARGOS = ("gerente", "administrativo", "operario")
# Tarifa distinta por cargo (default híbrido, editable vía API/UI). O(1) lookup.
DEFAULT_CARGO_RATES = {"gerente": 35000, "administrativo": 20000, "operario": 15000}

TIPOS_SANGRE = ("O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-")
TIPOS_SANGRE_PESOS = [0.65, 0.03, 0.20, 0.02, 0.06, 0.01, 0.025, 0.005]

NOMBRES_COL = [
    "Carlos", "Andrés", "Juan", "Felipe", "Mateo", "Santiago", "Alejandro", "Diego",
    "Esteban", "Daniel", "Camilo", "Sebastián", "Nicolás", "Julián", "David", "Gabriel",
    "Samuel", "Álvaro", "Rodrigo", "Fernando", "Laura", "Valentina", "Camila", "Mariana",
    "Daniela", "Sofía", "Isabella", "Natalia", "Paola", "Carolina", "Diana", "Juliana",
    "Catalina", "Gabriela", "Andrea", "Alejandra", "Lucía", "Elena", "Manuela", "Tatiana"
]

APELLIDOS_COL = [
    "Gómez", "Rodríguez", "Martínez", "García", "López", "Hernández", "González", "Pérez",
    "Sánchez", "Ramírez", "Torres", "Flores", "Díaz", "Vargas", "Castro", "Morales",
    "Ortiz", "Gutiérrez", "Chávez", "Ramos", "Herrera", "Jiménez", "Moreno", "Medina",
    "Rojas", "Cardona", "Restrepo", "Montoya", "Valencia", "Ospina", "Quintero", "Duque",
    "Jaramillo", "Mejía", "Zapata", "Berrío", "Londoño", "Uribe", "Ceballos", "Salazar"
]


def _slugify(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r'[^a-zA-Z0-9]+', '', cleaned).lower()


def create_fictional_employees(count: int, cargo_mode: str = "mixto") -> int:
    """Genera `count` empleados ficticios con datos colombianos realistas."""
    rates = get_cargo_rates()
    now = datetime.now(timezone.utc).isoformat()
    con = db()
    created = 0

    for _ in range(count):
        nom = random.choice(NOMBRES_COL)
        ap1 = random.choice(APELLIDOS_COL)
        ap2 = random.choice(APELLIDOS_COL)
        nombre_completo = f"{nom} {ap1} {ap2}"

        if cargo_mode in CARGOS:
            cargo = cargo_mode
        else:
            r = random.random()
            if r < 0.12:
                cargo = "gerente"
            elif r < 0.42:
                cargo = "administrativo"
            else:
                cargo = "operario"

        tarifa = rates.get(cargo, DEFAULT_CARGO_RATES.get(cargo, 20000))
        eid = "emp_" + uuid.uuid4().hex[:8]
        slug_user = f"{_slugify(nom)}.{_slugify(ap1)}"
        email = f"{slug_user}.{uuid.uuid4().hex[:4]}@empresa.co"
        cedula = f"10{random.randint(10000000, 99999999)}"
        edad = random.randint(21, 58)
        tipo_sangre = random.choices(TIPOS_SANGRE, weights=TIPOS_SANGRE_PESOS)[0]

        # Distribución de hijos
        hp = random.random()
        hijos = 0 if hp < 0.40 else (1 if hp < 0.70 else (2 if hp < 0.90 else 3))

        # Horas base según cargo
        if cargo == "gerente":
            h_ord = random.choice([150, 160])
            h_noct = random.choice([0, 5, 10])
            h_dom = random.choice([0, 4])
        elif cargo == "administrativo":
            h_ord = random.choice([150, 160])
            h_noct = random.choice([0, 8, 12])
            h_dom = random.choice([0, 4, 8])
        else:
            h_ord = random.choice([140, 150, 160])
            h_noct = random.choice([10, 15, 20, 25])
            h_dom = random.choice([8, 12, 16])

        try:
            con.execute("""
                INSERT INTO employees(id, nombre, cedula, edad, tipo_sangre, email, cargo, tarifa, h_ord, h_noct, h_dom, num_hijos, activo, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (eid, nombre_completo, cedula, edad, tipo_sangre, email, cargo, float(tarifa), float(h_ord), float(h_noct), float(h_dom), hijos, 1, now))
            con.execute("INSERT OR IGNORE INTO payslips(employee_id, estado, updated_at) VALUES(?,?,?)", (eid, "Borrador", now))
            con.execute("""
                INSERT OR IGNORE INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                VALUES(?, '2026-10', ?, ?, ?, ?, 'Borrador', NULL, ?)
            """, (eid, float(h_ord), float(h_noct), float(h_dom), float(tarifa), now))
            created += 1
        except sqlite3.IntegrityError:
            continue

    con.commit()
    con.close()
    return created


def subsidio(num_hijos: int) -> int:
    if num_hijos <= 0:
        return 0
    if num_hijos == 1:
        return 250_000
    if num_hijos == 2:
        return 400_000
    return 600_000


def liquidar(emp: dict, p: dict) -> dict:
    """Base IBC = bruto con recargos. Subsidio NO entra a base. O(n) por emp, O(1) subsidio."""
    tarifa = float(emp["tarifa"])
    bruto = (float(emp["hOrd"]) * tarifa
             + float(emp["hNoct"]) * tarifa * float(p["recNoct"])
             + float(emp["hDom"]) * tarifa * float(p["recDom"]))
    sub = subsidio(int(emp["numHijos"]))
    base = bruto  # IBC: recargos sí son salario; subsidio/aux transporte no
    d_salud = base * float(p["salud"])
    d_pension = base * float(p["pension"])
    d_arl = base * float(p["arl"])
    total = d_salud + d_pension + d_arl
    neto = base - total + sub
    r = lambda x: round(x)
    return {"bruto": r(bruto), "base": r(base), "sub": r(sub),
            "dSalud": r(d_salud), "dPen": r(d_pension), "dArl": r(d_arl),
            "total": r(total), "neto": r(neto)}


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS employees(
      id TEXT PRIMARY KEY, nombre TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      cargo TEXT NOT NULL CHECK(cargo IN ('gerente','administrativo','operario')),
      tarifa REAL NOT NULL CHECK(tarifa>0),
      h_ord REAL NOT NULL DEFAULT 0 CHECK(h_ord>=0),
      h_noct REAL NOT NULL DEFAULT 0 CHECK(h_noct>=0),
      h_dom REAL NOT NULL DEFAULT 0 CHECK(h_dom>=0),
      num_hijos INTEGER NOT NULL DEFAULT 0 CHECK(num_hijos>=0),
      activo INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
      cedula TEXT, edad INTEGER DEFAULT 28, tipo_sangre TEXT DEFAULT 'O+');
    CREATE TABLE IF NOT EXISTS payslips(
      employee_id TEXT PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
      estado TEXT NOT NULL DEFAULT 'Borrador', snap TEXT, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payslips_history(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      employee_id TEXT NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
      periodo TEXT NOT NULL,
      h_ord REAL NOT NULL DEFAULT 0 CHECK(h_ord>=0),
      h_noct REAL NOT NULL DEFAULT 0 CHECK(h_noct>=0),
      h_dom REAL NOT NULL DEFAULT 0 CHECK(h_dom>=0),
      tarifa_aplicada REAL NOT NULL,
      estado TEXT NOT NULL DEFAULT 'Borrador' CHECK(estado IN ('Borrador','En revisión','Autorizada','Enviada')),
      snap TEXT,
      updated_at TEXT NOT NULL,
      UNIQUE(employee_id, periodo));
    CREATE TABLE IF NOT EXISTS app_params(
      version TEXT PRIMARY KEY, salud REAL NOT NULL, pension REAL NOT NULL,
      arl REAL NOT NULL, rec_noct REAL NOT NULL, rec_dom REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS send_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, msg TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cargo_rates(cargo TEXT PRIMARY KEY, tarifa_default REAL NOT NULL CHECK(tarifa_default>0), updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_emp_email ON employees(email);
    CREATE INDEX IF NOT EXISTS idx_emp_cargo ON employees(cargo);
    CREATE INDEX IF NOT EXISTS idx_hist_periodo ON payslips_history(periodo);
    CREATE INDEX IF NOT EXISTS idx_hist_emp_periodo ON payslips_history(employee_id, periodo);
    """)

    # Migración de columnas de datos personales en employees si ya existía la tabla
    cols = [r["name"] for r in con.execute("PRAGMA table_info(employees)").fetchall()]
    if "cedula" not in cols:
        con.execute("ALTER TABLE employees ADD COLUMN cedula TEXT")
    if "edad" not in cols:
        con.execute("ALTER TABLE employees ADD COLUMN edad INTEGER DEFAULT 28")
    if "tipo_sangre" not in cols:
        con.execute("ALTER TABLE employees ADD COLUMN tipo_sangre TEXT DEFAULT 'O+'")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_emp_cedula ON employees(cedula)")

    # Asignar cédula, edad y tipo de sangre a empleados existentes que no los tengan
    null_emps = con.execute("SELECT id FROM employees WHERE cedula IS NULL OR cedula = ''").fetchall()
    for row in null_emps:
        gen_cc = f"10{random.randint(10000000, 99999999)}"
        gen_age = random.randint(22, 58)
        gen_rh = random.choices(TIPOS_SANGRE, weights=TIPOS_SANGRE_PESOS)[0]
        con.execute("UPDATE employees SET cedula=?, edad=?, tipo_sangre=? WHERE id=?",
                    (gen_cc, gen_age, gen_rh, row["id"]))

    row = con.execute("SELECT * FROM app_params").fetchone()
    if not row:
        con.execute("INSERT INTO app_params(version,salud,pension,arl,rec_noct,rec_dom) VALUES(?,?,?,?,?,?)",
                    (DEFAULT_PARAMS["version"], DEFAULT_PARAMS["salud"], DEFAULT_PARAMS["pension"],
                     DEFAULT_PARAMS["arl"], DEFAULT_PARAMS["recNoct"], DEFAULT_PARAMS["recDom"]))
    now_seed = datetime.now(timezone.utc).isoformat()
    for _cargo, _tar in DEFAULT_CARGO_RATES.items():
        con.execute("INSERT OR IGNORE INTO cargo_rates(cargo,tarifa_default,updated_at) VALUES(?,?,?)",
                    (_cargo, float(_tar), now_seed))

    # Poblar historial mes a mes (2026-10 actual, 2026-09 y 2026-08 históricos)
    has_cur = con.execute("SELECT COUNT(*) c FROM payslips_history WHERE periodo = '2026-10'").fetchone()["c"]
    if has_cur == 0:
        emps = con.execute("SELECT * FROM employees").fetchall()
        slips = {r["employee_id"]: dict(r) for r in con.execute("SELECT * FROM payslips").fetchall()}
        for e in emps:
            sl = slips.get(e["id"], {})
            st = sl.get("estado", "Borrador")
            snap = sl.get("snap")
            con.execute("""
                INSERT OR IGNORE INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                VALUES(?, '2026-10', ?, ?, ?, ?, ?, ?, ?)
            """, (e["id"], e["h_ord"], e["h_noct"], e["h_dom"], e["tarifa"], st, snap, now_seed))

    p_snap = json.dumps(DEFAULT_PARAMS)
    for past_p in ["2026-09", "2026-08"]:
        has_past = con.execute("SELECT COUNT(*) c FROM payslips_history WHERE periodo = ?", (past_p,)).fetchone()["c"]
        if has_past == 0:
            emps = con.execute("SELECT * FROM employees").fetchall()
            for e in emps:
                past_ord = 160.0
                past_noct = 10.0 if e["cargo"] == "operario" else 0.0
                past_dom = 8.0 if e["cargo"] == "operario" else 0.0
                con.execute("""
                    INSERT OR IGNORE INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, 'Enviada', ?, ?)
                """, (e["id"], past_p, past_ord, past_noct, past_dom, e["tarifa"], p_snap, f"{past_p}-28T18:00:00+00:00"))

    emp_count = con.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"]
    con.commit()
    con.close()
    if emp_count < 100:
        create_fictional_employees(100 - emp_count, "mixto")


def get_periods() -> list:
    """Retorna los periodos disponibles mes a mes en orden descendente."""
    con = db()
    rows = con.execute("SELECT DISTINCT periodo FROM payslips_history ORDER BY periodo DESC").fetchall()
    con.close()
    periods = [r["periodo"] for r in rows]
    if "2026-10" not in periods:
        periods.insert(0, "2026-10")
    return periods


def get_params() -> dict:
    con = db()
    r = con.execute("SELECT * FROM app_params LIMIT 1").fetchone()
    con.close()
    rec_noct = float(r["rec_noct"]) if r else 1.35
    rec_dom = float(r["rec_dom"]) if r else 1.90
    return {"salud": 0.04, "pension": 0.04, "arl": 0.00522,
            "recNoct": rec_noct, "recDom": rec_dom, "version": "v2026-10-ley-colombia"}


def get_cargo_rates() -> dict:
    """Tarifa default por cargo. O(1) con 3 filas."""
    con = db()
    rows = con.execute("SELECT cargo, tarifa_default FROM cargo_rates").fetchall()
    con.close()
    out = {r["cargo"]: r["tarifa_default"] for r in rows}
    for c, t in DEFAULT_CARGO_RATES.items():
        out.setdefault(c, float(t))
    return out


def resolve_tarifa(cargo, tarifa_raw):
    """Híbrida con fallback: explícita >0 gana; vacío/nulo/0 usa default del cargo. O(1)."""
    if tarifa_raw is None or (isinstance(tarifa_raw, str) and tarifa_raw.strip() == ""):
        tarifa_raw = None
    if tarifa_raw is not None:
        try:
            f = float(tarifa_raw)
            if f > 0:
                return f
        except (TypeError, ValueError):
            pass
        if tarifa_raw == 0 or tarifa_raw == "0":
            pass  # cae a default
        elif tarifa_raw is not None and str(tarifa_raw).strip() != "":
            # valor inválido explícito se deja para que valide
            return float(tarifa_raw)
    rates = get_cargo_rates()
    if cargo in rates and float(rates[cargo]) > 0:
        return float(rates[cargo])
    return None


def validate_emp(b, for_update=False):
    for f in ["nombre", "email", "cargo", "numHijos"]:
        if f not in b and not for_update:
            return f"Falta {f}"
    if not for_update:
        if "cedula" not in b or not str(b["cedula"]).strip():
            return "Falta cédula."
        if "edad" not in b:
            return "Falta edad."
    if "cedula" in b and str(b["cedula"]).strip():
        clean_cc = re.sub(r'[^0-9]', '', str(b["cedula"]))
        if len(clean_cc) < 6 or len(clean_cc) > 12:
            return "Cédula debe tener entre 6 y 12 dígitos."
    if "edad" in b and b["edad"] is not None and str(b["edad"]).strip() != "":
        try:
            ed = int(b["edad"])
            if not (18 <= ed <= 75):
                return "Edad debe estar entre 18 y 75 años."
        except (TypeError, ValueError):
            return "Edad debe ser un número entero."
    if "tipoSangre" in b and b["tipoSangre"]:
        if b["tipoSangre"] not in TIPOS_SANGRE:
            return f"Tipo de sangre inválido. Opciones: {', '.join(TIPOS_SANGRE)}"
    if "email" in b and not EMAIL_RE.match(str(b["email"])):
        return "Email inválido."
    if "cargo" in b and b["cargo"] not in ("gerente", "administrativo", "operario"):
        return "Cargo inválido."
    if "tarifa" in b and b["tarifa"] is not None and str(b["tarifa"]).strip() != "":
        try:
            _t = float(b["tarifa"])
        except (TypeError, ValueError):
            return "Tarifa debe ser > 0."
        if _t == 0:
            pass  # 0 = usar default del cargo
        elif not (_t > 0):
            return "Tarifa debe ser > 0."
    h_ord = float(b.get("hOrd", b.get("h_ord", 0)))
    h_noct = float(b.get("hNoct", b.get("h_noct", 0)))
    h_dom = float(b.get("hDom", b.get("h_dom", 0)))
    if min(h_ord, h_noct, h_dom) < 0:
        return "Horas >= 0."
    if "numHijos" in b and (int(b["numHijos"]) < 0):
        return "Hijos entero >= 0."
    return ""


class Handler(BaseHTTPRequestHandler):
    server_version = "NominaMVP/1.3"

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except Exception:
            return {}

    def _serve_html(self):
        if not HTML_PATH.exists():
            self.send_error(404, "index.html no encontrado")
            return
        data = HTML_PATH.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._serve_html()
        if u.path == "/api/health":
            return self._json({"ok": True, "db": str(DB_PATH.name)})
        if u.path == "/api/params":
            return self._json(get_params())
        if u.path == "/api/cargos":
            return self._json(get_cargo_rates())
        if u.path == "/api/periods":
            return self._json({"periods": get_periods(), "current": "2026-10"})
        if u.path == "/api/employees":
            query = parse_qs(u.query)
            periodo = query.get("periodo", ["2026-10"])[0]
            con = db()
            rows = con.execute("SELECT * FROM employees ORDER BY nombre").fetchall()
            hist_rows = {r["employee_id"]: dict(r) for r in con.execute(
                "SELECT * FROM payslips_history WHERE periodo=?", (periodo,)).fetchall()}
            slips = {r["employee_id"]: dict(r) for r in con.execute("SELECT * FROM payslips").fetchall()}
            con.close()
            p = get_params()
            out = []
            for r in rows:
                h = hist_rows.get(r["id"])
                h_ord = h["h_ord"] if h else r["h_ord"]
                h_noct = h["h_noct"] if h else r["h_noct"]
                h_dom = h["h_dom"] if h else r["h_dom"]
                tarifa = h["tarifa_aplicada"] if h else r["tarifa"]
                estado = h["estado"] if h else slips.get(r["id"], {}).get("estado", "Borrador")
                snap = json.loads(h["snap"]) if (h and h.get("snap")) else p
                e = {
                    "id": r["id"],
                    "nombre": r["nombre"],
                    "cedula": r["cedula"] or "",
                    "edad": r["edad"] or 28,
                    "tipoSangre": r["tipo_sangre"] or "O+",
                    "email": r["email"],
                    "cargo": r["cargo"],
                    "tarifa": tarifa,
                    "hOrd": h_ord,
                    "hNoct": h_noct,
                    "hDom": h_dom,
                    "numHijos": r["num_hijos"],
                    "activo": bool(r["activo"]),
                    "estado": estado,
                    "periodo": periodo
                }
                e["calc"] = liquidar(e, snap)
                out.append(e)
            return self._json(out)
        if u.path == "/api/logs":
            con = db()
            rows = con.execute("SELECT ts, msg FROM send_log ORDER BY id DESC LIMIT 30").fetchall()
            con.close()
            return self._json([f"[{r['ts']}] {r['msg']}" for r in reversed(rows)])
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/periods":
            b = self._body()
            periodo = str(b.get("periodo", "")).strip()
            if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", periodo):
                return self._json({"error": "Formato de periodo inválido (debe ser YYYY-MM, ej. 2026-11)."}, 400)
            con = db()
            count_exists = con.execute("SELECT COUNT(*) c FROM payslips_history WHERE periodo=?", (periodo,)).fetchone()["c"]
            if count_exists > 0:
                con.close()
                return self._json({"error": f"El periodo {periodo} ya existe."}, 409)
            emps = con.execute("SELECT * FROM employees WHERE activo=1").fetchall()
            now = datetime.now(timezone.utc).isoformat()
            rates = get_cargo_rates()
            for e in emps:
                tar = e["tarifa"] or rates.get(e["cargo"], 20000)
                con.execute("""
                    INSERT INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, 'Borrador', NULL, ?)
                """, (e["id"], periodo, e["h_ord"], e["h_noct"], e["h_dom"], tar, now))
            con.commit()
            con.close()
            return self._json({"ok": True, "periodo": periodo}, 201)
        if u.path == "/api/generate-employees":
            b = self._body()
            try:
                count = int(b.get("count", 10))
            except (TypeError, ValueError):
                count = 10
            count = max(1, min(count, 500))
            cargo_mode = b.get("cargo", "mixto")
            created = create_fictional_employees(count, cargo_mode)
            return self._json({"ok": True, "created": created})
        if u.path == "/api/employees/bulk-hours":
            b = self._body()
            ids = b.get("ids", [])
            periodo = b.get("periodo", "2026-10")
            if not isinstance(ids, list) or not ids:
                return self._json({"error": "No se seleccionaron empleados."}, 400)
            try:
                h_ord = float(b.get("hOrd", 0))
                h_noct = float(b.get("hNoct", 0))
                h_dom = float(b.get("hDom", 0))
            except (TypeError, ValueError):
                return self._json({"error": "Horas deben ser números válidos."}, 400)
            if min(h_ord, h_noct, h_dom) < 0:
                return self._json({"error": "Las horas deben ser >= 0."}, 400)
            now = datetime.now(timezone.utc).isoformat()
            con = db()
            q_marks = ",".join("?" for _ in ids)
            cur = con.cursor()
            cur.execute(f"""
                UPDATE payslips_history
                SET h_ord=?, h_noct=?, h_dom=?, updated_at=?
                WHERE employee_id IN ({q_marks})
                  AND periodo = ?
                  AND estado = 'Borrador'
            """, [h_ord, h_noct, h_dom, now] + ids + [periodo])
            updated_count = cur.rowcount
            if periodo == "2026-10":
                con.execute(f"""
                    UPDATE employees
                    SET h_ord=?, h_noct=?, h_dom=?, updated_at=?
                    WHERE id IN ({q_marks})
                """, [h_ord, h_noct, h_dom, now] + ids)
            con.commit()
            con.close()
            return self._json({"ok": True, "updated": updated_count, "periodo": periodo})
        if u.path == "/api/employees":
            b = self._body()
            err = validate_emp(b)
            if err:
                return self._json({"error": err}, 400)
            tarifa = resolve_tarifa(b["cargo"], b.get("tarifa"))
            if not tarifa or tarifa <= 0:
                return self._json({"error": "Tarifa debe ser > 0."}, 400)
            eid = "emp_" + uuid.uuid4().hex[:8]
            now = datetime.now(timezone.utc).isoformat()
            cedula = str(b.get("cedula", "")).strip() or f"10{random.randint(10000000, 99999999)}"
            edad = int(b.get("edad", 28))
            tipo_sangre = b.get("tipoSangre", "O+")
            con = db()
            try:
                con.execute("""INSERT INTO employees(id,nombre,cedula,edad,tipo_sangre,email,cargo,tarifa,h_ord,h_noct,h_dom,num_hijos,activo,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (eid, b["nombre"].strip(), cedula, edad, tipo_sangre, b["email"].strip(), b["cargo"], float(tarifa),
                             float(b.get("hOrd", 0)), float(b.get("hNoct", 0)), float(b.get("hDom", 0)),
                             int(b.get("numHijos", 0)), 1 if b.get("activo", True) else 0, now))
                con.execute("INSERT INTO payslips(employee_id,estado,updated_at) VALUES(?,?,?)", (eid, "Borrador", now))
                con.execute("""
                    INSERT OR IGNORE INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                    VALUES(?, '2026-10', ?, ?, ?, ?, 'Borrador', NULL, ?)
                """, (eid, float(b.get("hOrd", 0)), float(b.get("hNoct", 0)), float(b.get("hDom", 0)), float(tarifa), now))
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self._json({"error": "Email o Cédula duplicada."}, 409)
            con.close()
            return self._json({"id": eid}, 201)
        if u.path == "/api/seed":
            con = db()
            con.execute("DELETE FROM payslips_history")
            con.execute("DELETE FROM payslips")
            con.execute("DELETE FROM employees")
            con.commit()
            con.close()
            created = create_fictional_employees(100, "mixto")
            # Sembrar meses históricos
            con = db()
            emps = con.execute("SELECT * FROM employees").fetchall()
            p_snap = json.dumps(DEFAULT_PARAMS)
            for past_p in ["2026-09", "2026-08"]:
                for e in emps:
                    past_ord = 160.0
                    past_noct = 10.0 if e["cargo"] == "operario" else 0.0
                    past_dom = 8.0 if e["cargo"] == "operario" else 0.0
                    con.execute("""
                        INSERT OR IGNORE INTO payslips_history(employee_id, periodo, h_ord, h_noct, h_dom, tarifa_aplicada, estado, snap, updated_at)
                        VALUES(?, ?, ?, ?, ?, ?, 'Enviada', ?, ?)
                    """, (e["id"], past_p, past_ord, past_noct, past_dom, e["tarifa"], p_snap, f"{past_p}-28T18:00:00+00:00"))
            con.commit()
            con.close()
            return self._json({"ok": True, "created": created})
        m = re.match(r"^/api/employees/([^/]+)/estado$", u.path)
        if m:
            eid, b = m.group(1), self._body()
            want = b.get("estado", "")
            periodo = b.get("periodo", "2026-10")
            con = db()
            slip = con.execute("SELECT * FROM payslips_history WHERE employee_id=? AND periodo=?", (eid, periodo)).fetchone()
            emp = con.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            if not slip or not emp:
                con.close()
                return self._json({"error": "No existe registro de liquidación para este periodo."}, 404)
            cur = slip["estado"]
            if want not in FLOW or (want != cur and NEXT.get(cur) != want):
                con.close()
                return self._json({"error": f"Transición inválida {cur} -> {want}."}, 400)
            now = datetime.now(timezone.utc).isoformat()
            p = get_params()
            if want in ("En revisión", "Autorizada"):
                con.execute("UPDATE payslips_history SET estado=?, snap=?, updated_at=? WHERE employee_id=? AND periodo=?",
                            (want, json.dumps(p), now, eid, periodo))
            else:  # Enviada: mock envío con snapshot
                e = {"tarifa": slip["tarifa_aplicada"], "hOrd": slip["h_ord"], "hNoct": slip["h_noct"],
                     "hDom": slip["h_dom"], "numHijos": emp["num_hijos"]}
                snap = json.loads(slip["snap"]) if slip["snap"] else p
                c = liquidar(e, snap)
                msg = (f"[{periodo}] ENVIADA a {emp['email']} | {emp['nombre']} (CC: {emp['cedula']}) | base ${c['base']} - ded ${c['total']} "
                       f"(salud ${c['dSalud']} pen ${c['dPen']} arl ${c['dArl']}) + sub ${c['sub']} = NETO ${c['neto']}")
                con.execute("UPDATE payslips_history SET estado=?, updated_at=? WHERE employee_id=? AND periodo=?", (want, now, eid, periodo))
                con.execute("INSERT INTO send_log(ts,msg) VALUES(?,?)", (now, msg))
            if periodo == "2026-10":
                con.execute("UPDATE payslips SET estado=?, updated_at=? WHERE employee_id=?", (want, now, eid))
            con.commit()
            con.close()
            return self._json({"ok": True, "estado": want, "periodo": periodo})
        self.send_error(404)

    def do_PUT(self):
        u = urlparse(self.path)
        if u.path == "/api/cargos":
            b = self._body()
            rates = {}
            for c in CARGOS:
                if c in b:
                    try:
                        val = float(b[c])
                        if val <= 0:
                            return self._json({"error": f"Tarifa de {c} debe ser > 0."}, 400)
                        rates[c] = val
                    except (TypeError, ValueError):
                        return self._json({"error": f"Tarifa de {c} inválida."}, 400)
            if not rates:
                return self._json({"error": "No se enviaron tarifas."}, 400)
            now = datetime.now(timezone.utc).isoformat()
            con = db()
            for cargo, val in rates.items():
                con.execute("INSERT INTO cargo_rates(cargo, tarifa_default, updated_at) VALUES(?,?,?) "
                            "ON CONFLICT(cargo) DO UPDATE SET tarifa_default=excluded.tarifa_default, updated_at=excluded.updated_at",
                            (cargo, val, now))
                con.execute("""
                    UPDATE employees
                    SET tarifa = ?, updated_at = ?
                    WHERE cargo = ? AND id IN (SELECT employee_id FROM payslips WHERE estado = 'Borrador')
                """, (val, now, cargo))
                con.execute("""
                    UPDATE payslips_history
                    SET tarifa_aplicada = ?, updated_at = ?
                    WHERE periodo = '2026-10' AND estado = 'Borrador'
                      AND employee_id IN (SELECT id FROM employees WHERE cargo = ?)
                """, (val, now, cargo))
            con.commit()
            con.close()
            return self._json({"ok": True, "rates": get_cargo_rates()})
        m = re.match(r"^/api/employees/([^/]+)$", u.path)
        if m:
            eid, b = m.group(1), self._body()
            con = db()
            emp = con.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            slip = con.execute("SELECT * FROM payslips WHERE employee_id=?", (eid,)).fetchone()
            if not emp:
                con.close()
                return self._json({"error": "No existe."}, 404)
            if slip and slip["estado"] in ("En revisión", "Autorizada", "Enviada"):
                con.close()
                return self._json({"error": "Bloqueada por estado."}, 409)
            err = validate_emp(b, for_update=True)
            if err:
                con.close()
                return self._json({"error": err}, 400)
            now = datetime.now(timezone.utc).isoformat()
            try:
                con.execute("""UPDATE employees SET nombre=COALESCE(?,nombre),
                               cedula=COALESCE(?,cedula), edad=COALESCE(?,edad), tipo_sangre=COALESCE(?,tipo_sangre),
                               email=COALESCE(?,email), cargo=COALESCE(?,cargo), tarifa=COALESCE(?,tarifa),
                               h_ord=COALESCE(?,h_ord), h_noct=COALESCE(?,h_noct), h_dom=COALESCE(?,h_dom),
                               num_hijos=COALESCE(?,num_hijos), activo=COALESCE(?,activo), updated_at=? WHERE id=?""",
                            (b.get("nombre"), b.get("cedula"), b.get("edad"), b.get("tipoSangre"),
                             b.get("email"), b.get("cargo"), b.get("tarifa"),
                             b.get("hOrd"), b.get("hNoct"), b.get("hDom"), b.get("numHijos"),
                             b.get("activo"), now, eid))
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self._json({"error": "Email o Cédula duplicada."}, 409)
            con.close()
            return self._json({"ok": True})
        if u.path == "/api/params":
            b = self._body()
            try:
                rec_noct = float(b.get("recNoct", 1.35))
                rec_dom = float(b.get("recDom", 1.90))
            except (TypeError, ValueError):
                return self._json({"error": "Recargos numéricos inválidos."}, 400)
            if not (rec_noct >= 1 and rec_dom >= 1):
                return self._json({"error": "Recargos deben ser >= 1."}, 400)
            con = db()
            con.execute("UPDATE app_params SET salud=0.04, pension=0.04, arl=0.00522, rec_noct=?, rec_dom=?, version=?",
                        (rec_noct, rec_dom, "v2026-10-ley-colombia"))
            con.commit()
            con.close()
            return self._json({"ok": True, "params": get_params()})
        self.send_error(404)

    def log_message(self, *a):
        pass


def parse_args(argv):
    """Parsea --port/--force/--help sin deps. O(1)."""
    port = 8000
    force = False
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        print("Ejemplos:\n  python3 app.py\n  python3 app.py --port 8001\n"
              "  python3 app.py --port 8000 --force   # libera 8000 si está ocupado")
        sys.exit(0)
    if "--port" in argv:
        try:
            port = int(argv[argv.index("--port") + 1])
        except (IndexError, ValueError):
            print("ERROR: --port requiere un entero válido (ej. --port 8000).", file=sys.stderr)
            sys.exit(2)
    if "--force" in argv or "--free-port" in argv or "--free" in argv or "--kill" in argv:
        force = True
    if not (1 <= port <= 65535):
        print(f"ERROR: puerto {port} fuera de rango 1-65535.", file=sys.stderr)
        sys.exit(2)
    return port, force


def is_port_in_use(port, host="127.0.0.1"):
    """True si hay algo escuchando. O(1) connect. Evita falsos por TIME_WAIT del bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex((host, port)) == 0
        except OSError:
            return True


def find_pids_using_port(port):
    """Busca PIDs con lsof/fuser/ss. Retorna lista. O(p) p = procesos."""
    pids = []
    # 1) lsof -ti :port (más preciso)
    if shutil.which("lsof"):
        try:
            out = subprocess.run(["lsof", "-ti", f":{port}"],
                                 capture_output=True, text=True, timeout=5)
            for line in out.stdout.split():
                if line.strip().isdigit():
                    pids.append(int(line.strip()))
        except Exception:
            pass
    # 2) fuser port/tcp
    if not pids and shutil.which("fuser"):
        try:
            out = subprocess.run(["fuser", f"{port}/tcp"],
                                 capture_output=True, text=True, timeout=5)
            for tok in (out.stdout + " " + out.stderr).replace(":", " ").split():
                if tok.strip().isdigit():
                    pids.append(int(tok.strip()))
        except Exception:
            pass
    # 3) ss -lpt (fallback informativo, no siempre trae PID sin sudo)
    if not pids and shutil.which("ss"):
        try:
            out = subprocess.run(["ss", "-lpt", f"sport = :{port}"],
                                 capture_output=True, text=True, timeout=5)
            import re as _re
            for m in _re.findall(r"pid=(\d+)", out.stdout):
                pids.append(int(m))
        except Exception:
            pass
    return sorted(set(pids))


def free_port(port, timeout=6.0):
    """Intenta liberar el puerto: TERM -> espera -> KILL. Retorna True si queda libre."""
    pids = find_pids_using_port(port)
    if not pids:
        # Sin herramienta o proceso ya muerto: espera breve por TIME_WAIT
        time.sleep(0.5)
        return not is_port_in_use(port)
    own = os.getpid()
    for pid in pids:
        if pid == own:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as e:
            print(f"  no se pudo TERM pid {pid}: {e}", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_port_in_use(port):
            return True
        time.sleep(0.3)
    # Escalado a KILL
    for pid in [p for p in find_pids_using_port(port) if p != own]:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    time.sleep(0.5)
    return not is_port_in_use(port)


def print_port_busy_help(port):
    print(f"ERROR: puerto {port} ocupado (Address already in use).", file=sys.stderr)
    print(f"  Usa: python3 app.py --port {port} --force   # libera y reintenta", file=sys.stderr)
    print(f"  O manual: lsof -ti :{port} | xargs kill -9   |   fuser -k {port}/tcp", file=sys.stderr)
    print(f"  O cambia: python3 app.py --port {port + 1}", file=sys.stderr)


def main():
    port, force = parse_args(sys.argv)
    if is_port_in_use(port):
        if force:
            print(f"Puerto {port} ocupado — liberando (--force)...", flush=True)
            if free_port(port):
                print(f"Puerto {port} liberado.", flush=True)
            else:
                print_port_busy_help(port)
                sys.exit(1)
        else:
            print_port_busy_help(port)
            sys.exit(1)
    init_db()
    print(f"MVP http://localhost:{port}/  db={DB_PATH.name}", flush=True)
    HTTPServer.allow_reuse_address = True
    try:
        HTTPServer(("127.0.0.1", port), Handler).serve_forever()
    except OSError as e:
        # Carrera: se ocupó entre el chequeo y el bind
        if "Address already in use" in str(e) or getattr(e, "errno", 0) in (48, 98, 10013):
            print_port_busy_help(port)
            sys.exit(1)
        raise
    except KeyboardInterrupt:
        print("\nDetenido por usuario.", flush=True)


if __name__ == "__main__":
    main()
