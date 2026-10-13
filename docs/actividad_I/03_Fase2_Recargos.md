# 03 - Fase 2 Futuro: Festivos y Horas Nocturnas (Investigación Ley 2026)

> No hace parte de Fase 1. Solo backlog para no frenar entrega.

## 1. Base legal vigente Oct-2026
- Ley 2466/2025: Diurna 6am-7pm, Nocturna 7pm-6am (desde 25/dic/2025). Recargo nocturno 35%.
- Dominical/festivo gradual: hasta jun-2025 75%, jul-2025/jun-2026 80%, **jul-2026/jun-2027 90% vigente**, desde jul-2027 100%.
- Ley 2101/2021: jornada máxima **42h/sem** desde 15-jul-2026. Hora ordinaria sube. Tope extras 12h/sem.
- 1-2 domingos/mes ocasional (pago o compensatorio), 3+ habitual (pago + compensatorio).

Fuentes: MinTrabajo 01-jul-2026 y 15-jul-2026, Ley 2466, Caracol 27-jul-2026.

## 2. Tabla a implementar (TH = tarifa empleado)
| Código | Concepto | Factor |
|---|---|---|
| HOD | Diurna normal | 1.00 |
| HON | Nocturna | 1.35 |
| HED | Extra diurna | 1.25 |
| HEN | Extra nocturna | 1.75 |
| HODF | Dom/fest diurna | 1.90 |
| HONDF | Dom/fest nocturna | 2.25 |
| HEDDF | Extra diurna fest | 2.15 |
| HENDF | Extra noct fest | 2.65 |

Configurable: REC_DF=0.90 hoy, 1.00 en 2027 sin tocar código.

## 3. Fórmula Fase 2 (mantiene ARL descontada)
```
Base = SUM(Horas_Tipo * TH * Factor)
BaseNeta = Base - Base*0.04 - Base*0.04 - Base*%ARL
Neto = BaseNeta + Subsidio/2
```
Ejemplo operario $12.500: 60 HOD (750k) +10 HON (168.750) +4 HED (62.500) +8 HODF (190k) = Base 1.171.250 (+146k vs plano).

## 4. Cambios requeridos
- RF-03B: 8 campos por tipo + calendario festivos precargado.
- RF-04B: motor recargos con config.
- BD: `horas_detalle` + `festivos` (ya creadas vacías en SQLite).
- PDF desglosado, alerta 12h extra y 3+ dominicales.
