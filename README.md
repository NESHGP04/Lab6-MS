# Lab6-MS — Aula Abierta (Grupo 4)

Laboratorio de **Modelación y Simulación** sobre la plataforma educativa *Aula Abierta*.  
Se modela el crecimiento de usuarios activos y el dimensionamiento del clúster de servidores con un **modelo híbrido**:

| Capa | Qué es | Unidades |
|------|--------|----------|
| **SD (System Dynamics)** | Evolución continua de usuarios activos `U(t)` (adopción Bass + abandono por latencia/rechazos) | usuarios, tiempo en **días** |
| **DES (Discrete Event Simulation)** | Cola de servidores `M/M/c/K` en hora pico | solicitudes, tiempo en **segundos** |
| **Acoplamiento** | Cada `H` días el SD pasa `λ = a·U` y `c` al DES; el DES devuelve latencia `W` y fracción rechazada `r` | intercambio periódico |
| **Autoescalado** | Si la utilización prevista `ρ = a·U/(c·μ)` cruza el umbral `θ = 0.7`, se piden 2 servidores que llegan en `D` días | evento de estado + demora |

**Parámetros del grupo 4:** `q = 0.35` /día, `D = 6` días, `H = 1` día, `U(0) = 100`, `c(0) = 4`.

---

## Estructura del repositorio

```
Lab6-MS/
├── task_1_2.py                 # Task 1.2 — equilibrio con capacidad fija
├── figuras/
│   └── task_1_2_equilibrio.png # Figura del equilibrio (adopción vs abandono, W(U))
├── anexo/                      # Material de apoyo del Task 1.3
│   ├── task_1_3_prompt.md      # Prompt exacto usado para generar el baseline con IA
│   └── task_1_3_baseline.py    # Código híbrido baseline generado a partir de ese prompt
└── Task_2/                     # Task 2 — verificación completa del modelo
    ├── LEAME.txt               # Instrucciones de ejecución y descripción de salidas
    ├── task_2.py               # Simulación DES + SD + híbrido + verificaciones
    ├── crear_reporte.py        # Reconstruye el reporte Word desde resultados.json
    ├── resultados.json         # Resumen numérico (teorías, réplicas, IC, trayectorias)
    ├── stable.csv              # 30 réplicas DES en régimen estable (λ=6, K≈∞)
    ├── overload.csv            # 30 réplicas DES en sobrecarga (λ=10, K=60)
    ├── interface.csv           # 30 réplicas para comprobar conteos / Poisson en la interfaz
    ├── errores_sd.csv          # Error de Euler y RK4 vs solve_ivp al variar el paso
    ├── comparacion_eventos.csv # 30×3 réplicas: exacto vs revisión ingenua (1 d y 0.25 d)
    ├── ventanas_exact.csv      # Métricas por intercambio (réplica principal, modo exacto)
    ├── ventanas_naive1.csv     # Idem, revisión cada 1 día
    ├── ventanas_naive025.csv   # Idem, revisión cada 0.25 días
    └── figuras/
        ├── convergencia.png    # Convergencia numérica del SD
        └── eventos.png         # Comparación de detección de autoescalado
```

---

## Task 1.2 — Equilibrio con capacidad fija

**Archivo:** `task_1_2.py`  
**Figura:** `figuras/task_1_2_equilibrio.png`

Qué hace:

1. **Latencia M/M/c** (`c = 4` fijos, sin rechazos, `r = 0`) con fórmula de Erlang C: `W(U)` y su dominio válido (`U < c·μ/a = 16 000`).
2. **Equilibrio del lazo SD acoplado:** resuelve numéricamente `adopción(U*) = abandono(U*)` (método de Brent sobre cambios de signo).
3. Genera la figura adopción vs abandono y `W(U)` vs `W_ok`.

En este task **no hay autoescalado** (`D` no interviene).

```bash
python task_1_2.py
```

---

## Anexo Task 1.3 — Baseline híbrido (generado por IA)

| Archivo | Qué es |
|---------|--------|
| `anexo/task_1_3_prompt.md` | Texto **exacto** del prompt con el enunciado del modelo híbrido (SD + DES + autoescalado + acoplamiento) y la petición de una réplica a 100 días. |
| `anexo/task_1_3_baseline.py` | Implementación **línea base** generada a partir de ese prompt: DES por eventos, integración SD con `solve_ivp`, pedidos de servidores con demora `D`. |

Sirve de referencia / punto de partida frente a la implementación verificada del Task 2.

---

## Task 2 — Verificación del modelo híbrido

**Carpeta:** `Task_2/`  
**Entrada principal:** `task_2.py`  
**Guía local:** `LEAME.txt`

Implementación y verificaciones **completas** (no depende del código del Task 1). Incluye:

### 2.1 Verificación del clúster (DES)

Simulador FCFS `M/M/c/K` con calentamiento 120 s, horizonte 720 s y drenaje final (sin nuevas llegadas) para completar tiempos de la cohorte medida.

| Experimento | Archivo CSV | Qué comprueba |
|-------------|-------------|----------------|
| Estable | `stable.csv` | `λ = 6`, `K` muy grande ≈ M/M/c; compara `W`, `Wq`, utilización con Erlang C |
| Sobrecarga | `overload.csv` | `λ = 10`, `K = 60`; fracción rechazada `r` vs teoría M/M/c/K y aproximación de saturación |
| Interfaz | `interface.csv` | Conteos, balances, identidad de Little y dispersión Poisson de llegadas |

Intervalos al **95 %** con *t* de Student sobre **30 réplicas** independientes (semilla base `20261022`).

### 2.2 Verificación del SD

Integración de `dU/dt` con Euler y RK4 frente a `solve_ivp` (y solución analítica tipo Riccati).  
Salida: `errores_sd.csv` y `figuras/convergencia.png` (órdenes de convergencia).

### 2.3 Híbrido y detección de eventos de autoescalado

Tres versiones del mismo modelo (mismo integrador; se aísla el error de **detección** del umbral):

| Modo | Qué es | Salida de ventanas |
|------|--------|--------------------|
| `exact` | Localiza el cruce `ρ = θ` con eventos de `solve_ivp` | `ventanas_exact.csv` |
| `naive1` | Revisa el umbral en una malla global cada **1 día** | `ventanas_naive1.csv` |
| `naive025` | Revisa cada **0.25 días** | `ventanas_naive025.csv` |

Comparación agregada: `comparacion_eventos.csv` (primera orden, primera entrega, `W_max`, `r_max`, `U(100)`, `c(100)`).  
Figura: `figuras/eventos.png`.

### 2.4 Resultados y reporte

| Archivo | Qué es |
|---------|--------|
| `resultados.json` | Empaqueta teorías, resúmenes con IC, trayectorias principales, comparaciones pareadas y chequeo Poisson |
| `crear_reporte.py` | Regenera el documento Word del Task 2 a partir de `resultados.json` (requiere `python-docx`) |

```bash
cd Task_2
pip install numpy scipy matplotlib
python task_2.py                 # simulación completa (puede tardar varios minutos)

pip install python-docx
python crear_reporte.py          # reconstruir el Word
```

---

## Ideas clave del modelo (referencia rápida)

- **Adopción (Bass):** `(p + q·U/M)(M − U)`
- **Abandono:** `δ·U` con `δ = δ0 + κ_W·max(0, W − W_ok) + κ_R·r`
- **DES:** llegadas Poisson `λ = a·U`, servicio exp. `μ = 2` s⁻¹, capacidad `K = 60` (salvo el caso “estable” casi ilimitado)
- **Autoescalado:** al cruzar `θ = 0.7` sin pedido pendiente → +2 servidores en `D` días; si al llegar sigue alto, se pide de nuevo
---

## Task 3 — Sensibilidad, baseline y políticas

Ver carpeta [`Task_3/`](Task_3/) (no modifica Tasks 1–2):

```bash
python Task_3/task_3.py --all
```

Incluye sensibilidad a `H`, comparación con el baseline IA, 12 políticas `(θ,k)` a 150 días y defensa 3.4. Detalle en `Task_3/README.md` y `Task_3/resumen_para_reporte.md`.
