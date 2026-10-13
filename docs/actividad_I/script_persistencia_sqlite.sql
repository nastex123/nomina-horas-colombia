-- Persistencia SQLite (archivo local, sin servidor)
-- Archivo sugerido: liquidacion_nomina.db
-- Activar FK en cada conexión: PRAGMA foreign_keys = ON;

PRAGMA foreign_keys = ON;

-- 1. Cargos
CREATE TABLE IF NOT EXISTS cargos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL UNIQUE, -- Gerente, Administrativo, Operario
  tarifa_base_hora REAL NOT NULL CHECK (tarifa_base_hora > 0),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Empleados (CRUD principal)
CREATE TABLE IF NOT EXISTS empleados (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombres TEXT NOT NULL,
  apellidos TEXT NOT NULL,
  cedula TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  cargo_id INTEGER NOT NULL,
  tarifa_hora REAL NOT NULL CHECK (tarifa_hora > 0),
  num_hijos INTEGER NOT NULL DEFAULT 0 CHECK (num_hijos >= 0),
  riesgo_arl TEXT NOT NULL DEFAULT 'I' CHECK (riesgo_arl IN ('I','II','III','IV','V')),
  fecha_ingreso DATE NOT NULL,
  estado TEXT NOT NULL DEFAULT 'Activo' CHECK (estado IN ('Activo','Inactivo')),
  cuenta_bancaria TEXT,
  FOREIGN KEY (cargo_id) REFERENCES cargos(id)
);
CREATE INDEX IF NOT EXISTS idx_empleado_cedula ON empleados(cedula);
CREATE INDEX IF NOT EXISTS idx_empleado_estado ON empleados(estado);

-- 3. Usuarios (login/roles)
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id INTEGER,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('Admin','Gerencia','Empleado')),
  intentos_fallidos INTEGER DEFAULT 0,
  bloqueado_hasta DATETIME,
  FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE SET NULL
);

-- 4. Config (todo parametrizable)
CREATE TABLE IF NOT EXISTS config (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL,
  descripcion TEXT
);

-- 5. Periodos quincenales
CREATE TABLE IF NOT EXISTS periodos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL CHECK (fecha_fin > fecha_inicio),
  estado TEXT DEFAULT 'Abierto' CHECK (estado IN ('Abierto','Cerrado')),
  UNIQUE (fecha_inicio, fecha_fin)
);

-- 6. Horas (Fase1 + campos Fase2 en 0)
CREATE TABLE IF NOT EXISTS horas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id INTEGER NOT NULL,
  periodo_id INTEGER NOT NULL,
  horas_normales REAL NOT NULL DEFAULT 0 CHECK (horas_normales >= 0),
  horas_nocturnas REAL DEFAULT 0,
  horas_extra_diurna REAL DEFAULT 0,
  horas_extra_nocturna REAL DEFAULT 0,
  horas_dominical REAL DEFAULT 0,
  observacion TEXT,
  UNIQUE (empleado_id, periodo_id),
  FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE,
  FOREIGN KEY (periodo_id) REFERENCES periodos(id) ON DELETE CASCADE
);

-- 7. Festivos (Fase2)
CREATE TABLE IF NOT EXISTS festivos (
  fecha DATE PRIMARY KEY,
  descripcion TEXT NOT NULL
);

-- 8. Liquidaciones (ARL descontada del base, subsidio después)
CREATE TABLE IF NOT EXISTS liquidaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  empleado_id INTEGER NOT NULL,
  periodo_id INTEGER NOT NULL,
  tarifa_aplicada REAL NOT NULL,
  horas_total REAL NOT NULL,
  salario_base REAL NOT NULL,
  ded_salud REAL NOT NULL,
  ded_pension REAL NOT NULL,
  ded_arl REAL NOT NULL,
  base_neta REAL NOT NULL,
  subsidio REAL NOT NULL DEFAULT 0,
  neto REAL NOT NULL,
  aporte_caja REAL NOT NULL,
  estado TEXT DEFAULT 'Calculada' CHECK (estado IN ('Borrador','Calculada','Autorizada','Enviada','Rechazada')),
  autorizado_por INTEGER,
  fecha_calculo DATETIME DEFAULT CURRENT_TIMESTAMP,
  fecha_envio DATETIME,
  UNIQUE (empleado_id, periodo_id),
  FOREIGN KEY (empleado_id) REFERENCES empleados(id),
  FOREIGN KEY (periodo_id) REFERENCES periodos(id),
  FOREIGN KEY (autorizado_por) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- 9. Log envíos
CREATE TABLE IF NOT EXISTS envios_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  liquidacion_id INTEGER NOT NULL,
  email_destino TEXT NOT NULL,
  estado TEXT NOT NULL CHECK (estado IN ('OK','FALLO')),
  error_msg TEXT,
  fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE
);

-- DATOS INICIALES
INSERT OR IGNORE INTO cargos (nombre, tarifa_base_hora) VALUES
('Gerente', 28000), ('Administrativo', 18000), ('Operario', 12500);

INSERT OR IGNORE INTO config (clave, valor, descripcion) VALUES
('SUB_H1','250000','Subsidio mensual 1 hijo'),
('SUB_H2','400000','Subsidio mensual 2 hijos'),
('SUB_H3','600000','Subsidio mensual 3+ hijos'),
('SALUD_PORC','0.04','Salud trabajador'),
('PENSION_PORC','0.04','Pension trabajador'),
('ARL_I','0.00522','Riesgo I'),('ARL_II','0.01044','Riesgo II'),
('ARL_III','0.02436','Riesgo III'),('ARL_IV','0.0435','Riesgo IV'),
('ARL_V','0.0696','Riesgo V'),
('CAJA_PORC','0.04','Caja solo informativo'),
('REC_NOCT','0.35','Fase2'),('REC_EXD','0.25','Fase2'),
('REC_EXN','0.75','Fase2'),('REC_DF','0.90','Fase2 vigente oct-2026');
