# 01 - Especificación de Requisitos (SRS) - Sistema de Liquidación Quincenal

**Proyecto:** Empresa financiera y contable - automatizar liquidación empleados
**Periodicidad:** Quincenal | **Stack:** Web Python + SQLite | **Envío:** Email con PDF
**Tarifa:** Base por cargo (Gerente $28.000, Administrativo $18.000, Operario $12.500) editable por empleado

## 1. Objetivo y alcance
Automatizar liquidación por horas con tarifa configurable, subsidio por hijos y deducciones, con envío automático.

Incluye: CRUD empleados, configuración parámetros, registro horas, cálculo, autorización, envío PDF, historial.
Fuera de alcance Fase 1: pago bancos, NIIF, WhatsApp, recargos festivos/nocturnos (ver doc 03).

## 2. Regla de cálculo oficial de esta actividad
- Base = Horas * TarifaHora
- DedSalud = Base * 0.04 | DedPension = Base * 0.04 | DedARL = Base * %Riesgo (I 0.522%, II 1.044%, III 2.436%, IV 4.35%, V 6.96%)
- BaseNeta = Base - DedSalud - DedPension - DedARL
- Subsidio_Q = (1 hijo 250k | 2 hijos 400k | 3+ 600k mensual) / 2
- Neto = BaseNeta + Subsidio_Q
- Caja 4% solo informativo empresa, no resta.

> Nota: en ley real ARL/Caja las paga empresa. Aquí ARL SÍ descuenta por exigencia del ejercicio.

## 3. Actores
- Admin/Contador: CRUD, configura, liquida, autoriza.
- Gerencia: aprueba.
- Empleado: recibe PDF.
- Sistema: calcula y envía.

## 4. Requerimientos funcionales
**RF-01 CRUD Empleados:** nombres, apellidos, cédula UNIQUE, email UNIQUE, cargo, tarifa_hora, num_hijos, riesgo_arl, fecha_ingreso, estado, cuenta. Hereda tarifa base pero editable. Validar email único, tarifa>0, hijos>=0.
**RF-02 Config:** SUB_H1/H2/H3, SALUD 0.04, PENSION 0.04, ARL_I..V, CAJA 0.04, periodo 1-15 / 16-30.
**RF-03 Horas:** por empleado+periodo, 0-120h quincena, sin duplicados.
**RF-04 Cálculo:** fórmula sección 2. Estados: Borrador->Calculada->Autorizada->Enviada/Rechazada.
**RF-05 Autorización:** sin autorización no hay envío. Auditoría quién/cuándo.
**RF-06 Envío:** al autorizar genera PDF y envía SMTP, reintento x3, log.
**RF-07 Historial:** filtro por empleado/periodo/estado, exportar Excel/PDF.
**RF-08 Auth:** bcrypt, roles, bloqueo 5 intentos.

## 5. No funcionales
Web Flask MVC, <5seg para 200 liquidadas, backup copiando .db, HTTPS, validación backend, Ley 1581 datos, responsive, config en tabla no en código.

## 6. Ejemplos (ARL descontada)
1. Gerente 80h $28k, 1 hijo, I: Base 2.240.000 -89.600-89.600-11.693=2.049.107 +125.000 = **2.174.107**
2. Admin 80h $18k, 2 hijos, I: Base 1.440.000 -57.600-57.600-7.517=1.317.283 +200.000 = **1.517.283**
3. Operario 90h $12.5k, 3 hijos, III: Base 1.125.000 -45.000-45.000-27.405=1.007.595 +300.000 = **1.307.595**
4. Operario 40h sin hijos: Base 500.000 -20.000-20.000-12.180=447.820 +0 = **447.820**

## 7. Casos de uso / Historias / Pruebas
CU-01 crear, CU-02 configurar tarifa, CU-03 registrar horas, CU-04 calcular, CU-05 autorizar, CU-06 envío auto, CU-07 historial.
HU: contador crea, admin edita tarifa, sistema aplica subsidio y descuenta, gerente autoriza, empleado recibe PDF.
Pruebas: 0/1/2/3/5 hijos, tarifa individual, base 0, horas 0 y >120 bloquea, email inválido bloquea, PDF con neto correcto.
