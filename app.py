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
import re
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "nomina.db"
HTML_PATH = BASE_DIR / "index.html"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FLOW = ["Borrador", "En revisión", "Autorizada", "Enviada"]
NEXT = {"Borrador": "En revisión", "En revisión": "Autorizada", "Autorizada": "Enviada"}

DEFAULT_PARAMS = {"salud": 0.04, "pension": 0.04, "arl": 0.00522,
                  "recNoct": 1.35, "recDom": 1.90, "version": "v2026-10-3ded"}

CARGOS = ("gerente", "administrativo", "operario")
# Tarifa distinta por cargo (default híbrido, editable vía API/UI). O(1) lookup.
DEFAULT_CARGO_RATES = {"gerente": 35000, "administrativo": 20000, "operario": 15000}


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
      activo INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS payslips(
      employee_id TEXT PRIMARY KEY REFERENCES employees(id) ON DELETE CASCADE,
      estado TEXT NOT NULL DEFAULT 'Borrador', snap TEXT, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS app_params(
      version TEXT PRIMARY KEY, salud REAL NOT NULL, pension REAL NOT NULL,
      arl REAL NOT NULL, rec_noct REAL NOT NULL, rec_dom REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS send_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, msg TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cargo_rates(cargo TEXT PRIMARY KEY, tarifa_default REAL NOT NULL CHECK(tarifa_default>0), updated_at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_emp_email ON employees(email);
    CREATE INDEX IF NOT EXISTS idx_emp_cargo ON employees(cargo);
    """)
    row = con.execute("SELECT * FROM app_params").fetchone()
    if not row:
        con.execute("INSERT INTO app_params(version,salud,pension,arl,rec_noct,rec_dom) VALUES(?,?,?,?,?,?)",
                    (DEFAULT_PARAMS["version"], DEFAULT_PARAMS["salud"], DEFAULT_PARAMS["pension"],
                     DEFAULT_PARAMS["arl"], DEFAULT_PARAMS["recNoct"], DEFAULT_PARAMS["recDom"]))
    now_seed = datetime.now(timezone.utc).isoformat()
    for _cargo, _tar in DEFAULT_CARGO_RATES.items():
        con.execute("INSERT OR IGNORE INTO cargo_rates(cargo,tarifa_default,updated_at) VALUES(?,?,?)",
                    (_cargo, float(_tar), now_seed))
    con.commit()
    con.close()


def get_params() -> dict:
    con = db()
    r = con.execute("SELECT * FROM app_params LIMIT 1").fetchone()
    con.close()
    return {"salud": r["salud"], "pension": r["pension"], "arl": r["arl"],
            "recNoct": r["rec_noct"], "recDom": r["rec_dom"], "version": r["version"]}


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
    for f in ["hOrd", "h_noct", "hNoct", "h_dom", "hDom", "h_ord"]:
        pass
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
        if u.path == "/api/employees":
            con = db()
            rows = con.execute("SELECT * FROM employees ORDER BY nombre").fetchall()  # O(n log n) por ORDER BY
            slips = {r["employee_id"]: dict(r) for r in con.execute("SELECT * FROM payslips")}
            con.close()
            p = get_params()
            out = []
            for r in rows:  # O(n), subsidio O(1)
                e = {"id": r["id"], "nombre": r["nombre"], "email": r["email"], "cargo": r["cargo"],
                     "tarifa": r["tarifa"], "hOrd": r["h_ord"], "hNoct": r["h_noct"], "hDom": r["h_dom"],
                     "numHijos": r["num_hijos"], "activo": bool(r["activo"])}
                slip = slips.get(e["id"], {"estado": "Borrador", "snap": None})
                snap = json.loads(slip["snap"]) if slip.get("snap") else p
                out.append({**e, "estado": slip.get("estado", "Borrador"), "calc": liquidar(e, snap)})
            return self._json(out)
        if u.path == "/api/logs":
            con = db()
            rows = con.execute("SELECT ts, msg FROM send_log ORDER BY id DESC LIMIT 30").fetchall()
            con.close()
            return self._json([f"[{r['ts']}] {r['msg']}" for r in reversed(rows)])
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/employees":
            b = self._body()
            err = validate_emp(b)
            if err:
                return self._json({"error": err}, 400)
            import uuid
            eid = "emp_" + uuid.uuid4().hex[:8]
            now = datetime.now(timezone.utc).isoformat()
            con = db()
            try:
                con.execute("""INSERT INTO employees(id,nombre,email,cargo,tarifa,h_ord,h_noct,h_dom,num_hijos,activo,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (eid, b["nombre"].strip(), b["email"].strip(), b["cargo"], float(b["tarifa"]),
                             float(b.get("hOrd", 0)), float(b.get("hNoct", 0)), float(b.get("hDom", 0)),
                             int(b.get("numHijos", 0)), 1 if b.get("activo", True) else 0, now))
                con.execute("INSERT INTO payslips(employee_id,estado,updated_at) VALUES(?,?,?)", (eid, "Borrador", now))
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self._json({"error": "Email duplicado."}, 409)
            con.close()
            return self._json({"id": eid}, 201)
        if u.path == "/api/seed":
            con = db()
            n = con.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"]
            if n == 0:
                import uuid
                now = datetime.now(timezone.utc).isoformat()
                eid = "emp_" + uuid.uuid4().hex[:8]
                con.execute("""INSERT INTO employees(id,nombre,email,cargo,tarifa,h_ord,h_noct,h_dom,num_hijos,activo,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (eid, "Ana Pérez", "ana@empresa.co", "administrativo", 20000, 150, 10, 8, 1, 1, now))
                con.execute("INSERT INTO payslips(employee_id,estado,updated_at) VALUES(?,?,?)", (eid, "Borrador", now))
                con.commit()
            con.close()
            return self._json({"ok": True})
        m = re.match(r"^/api/employees/([^/]+)/estado$", u.path)
        if m:
            eid, b = m.group(1), self._body()
            want = b.get("estado", "")
            con = db()
            slip = con.execute("SELECT * FROM payslips WHERE employee_id=?", (eid,)).fetchone()
            emp = con.execute("SELECT * FROM employees WHERE id=?", (eid,)).fetchone()
            if not slip or not emp:
                con.close()
                return self._json({"error": "No existe."}, 404)
            cur = slip["estado"]
            if want not in FLOW or (want != cur and NEXT.get(cur) != want):
                con.close()
                return self._json({"error": f"Transición inválida {cur} -> {want}."}, 400)
            now = datetime.now(timezone.utc).isoformat()
            p = get_params()
            if want in ("En revisión", "Autorizada"):
                con.execute("UPDATE payslips SET estado=?, snap=?, updated_at=? WHERE employee_id=?",
                            (want, json.dumps(p), now, eid))
            else:  # Enviada: mock envío con snapshot
                e = {"tarifa": emp["tarifa"], "hOrd": emp["h_ord"], "hNoct": emp["h_noct"],
                     "hDom": emp["h_dom"], "numHijos": emp["num_hijos"]}
                snap = json.loads(slip["snap"]) if slip["snap"] else p
                c = liquidar(e, snap)
                msg = (f"ENVIADA a {emp['email']} | {emp['nombre']} | base ${c['base']} - ded ${c['total']} "
                       f"(salud ${c['dSalud']} pen ${c['dPen']} arl ${c['dArl']}) + sub ${c['sub']} = NETO ${c['neto']}")
                con.execute("UPDATE payslips SET estado=?, updated_at=? WHERE employee_id=?", (want, now, eid))
                con.execute("INSERT INTO send_log(ts,msg) VALUES(?,?)", (now, msg))
            con.commit()
            con.close()
            return self._json({"ok": True, "estado": want})
        self.send_error(404)

    def do_PUT(self):
        u = urlparse(self.path)
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
                con.execute("""UPDATE employees SET nombre=COALESCE(?,nombre), email=COALESCE(?,email),
                               cargo=COALESCE(?,cargo), tarifa=COALESCE(?,tarifa),
                               h_ord=COALESCE(?,h_ord), h_noct=COALESCE(?,h_noct), h_dom=COALESCE(?,h_dom),
                               num_hijos=COALESCE(?,num_hijos), activo=COALESCE(?,activo), updated_at=? WHERE id=?""",
                            (b.get("nombre"), b.get("email"), b.get("cargo"), b.get("tarifa"),
                             b.get("hOrd"), b.get("hNoct"), b.get("hDom"), b.get("numHijos"),
                             b.get("activo"), now, eid))
                con.commit()
            except sqlite3.IntegrityError:
                con.close()
                return self._json({"error": "Email duplicado."}, 409)
            con.close()
            return self._json({"ok": True})
        if u.path == "/api/params":
            b = self._body()

            def _to_frac(v, default):
                # Contrato: fracción 0-1 (0.04) o % numérico >1 (4) o string "4%" / "0.522%". O(1).
                if v is None or v == "":
                    return float(default)
                if isinstance(v, str) and v.strip().endswith("%"):
                    return float(v.strip().rstrip("%").strip()) / 100.0
                f = float(v)
                if f > 1:
                    f = f / 100.0
                return f

            try:
                salud = _to_frac(b.get("salud", 0.04), 0.04)
                pension = _to_frac(b.get("pension", 0.04), 0.04)
                arl = _to_frac(b.get("arl", 0.00522), 0.00522)
                rec_noct = float(b.get("recNoct", 1.35))
                rec_dom = float(b.get("recDom", 1.90))
            except (TypeError, ValueError):
                return self._json({"error": "Params numéricos inválidos."}, 400)
            if not (0 <= salud <= 1 and 0 <= pension <= 1 and 0 <= arl <= 1):
                return self._json({"error": "Deducciones deben estar entre 0% y 100%."}, 400)
            if not (rec_noct >= 1 and rec_dom >= 1):
                return self._json({"error": "Recargos deben ser >= 1."}, 400)
            con = db()
            con.execute("UPDATE app_params SET salud=?, pension=?, arl=?, rec_noct=?, rec_dom=?, version=?",
                        (salud, pension, arl, rec_noct, rec_dom, "v2026-10-3ded-manual"))
            con.commit()
            con.close()
            return self._json({"ok": True})
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
