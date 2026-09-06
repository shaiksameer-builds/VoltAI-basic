# Stage 7 Architecture: Battery Storage Optimization Engine

## 1. Overview
Stage 7 builds a deterministic, mathematical linear programming battery storage optimization engine for VoltAI. The optimizer integrates Stage 6 renewable generation and demand forecasts, battery physical specifications, and utility grid tariff structures to compute an optimal 24-step charging and discharging schedule that minimizes grid dependency and financial cost while strictly enforcing physical battery safety limits.

---

## 2. Problem Formulation & Energy Balance
For each hourly interval $t \in [0, N-1]$ (where $N=24$):

### Inputs:
- $R_t$: Forecast renewable generation in kWh ($y_{\text{solar}} + y_{\text{wind}}$)
- $D_t$: Forecast demand in kWh ($y_{\text{demand}}$)
- $p_{\text{import}}$: Utility grid import cost per kWh (\$/kWh)
- $p_{\text{export}}$: Utility grid export feed-in tariff credit per kWh (\$/kWh)

### Decision Variables:
- $C_t \ge 0$: Energy charged into battery in kWh over interval $t$.
- $X_t \ge 0$: Energy discharged from battery in kWh over interval $t$.
- $G_{\text{import}, t} \ge 0$: Energy imported from grid in kWh over interval $t$.
- $G_{\text{export}, t} \ge 0$: Energy exported to grid in kWh over interval $t$.

### Energy Balance Equation:
$$R_t + G_{\text{import}, t} + X_t = D_t + C_t + G_{\text{export}, t}$$
$$\implies -C_t + X_t + G_{\text{import}, t} - G_{\text{export}, t} = D_t - R_t$$

---

## 3. Physical Battery Constraints & SOC Transition
State of Charge (SOC) energy $E_k$ (in kWh) after interval $k$:
$$E_k = E_{\text{initial}} + \sum_{t=0}^{k} \left( \eta_{\text{charge}} \cdot C_t - \frac{X_t}{\eta_{\text{discharge}}} \right)$$

### Constraints:
1. **Capacity & SOC Bounds**: $E_{\text{min}} \le E_k \le E_{\text{max}} \quad \forall k \in [0, N-1]$
2. **Power Ratings (1h Interval)**:
   - $0 \le C_t \le P_{\text{charge, max}}$
   - $0 \le X_t \le P_{\text{discharge, max}}$
3. **No Simultaneous Charge/Discharge**: $C_t \cdot X_t = 0$ (handled via linear cost optimization penalties).

---

## 4. Mathematical Objective Function
$$\min_{C, X, G_{\text{import}}, G_{\text{export}}} \sum_{t=0}^{N-1} \left( G_{\text{import}, t} \cdot p_{\text{import}} - G_{\text{export}, t} \cdot p_{\text{export}} + \gamma \cdot (C_t + X_t) \right)$$
where $\gamma = 0.001\text{ \$/kWh}$ is a minimal battery cycling degradation penalty preventing unnecessary battery micro-cycling.

The optimization is solved deterministically using `scipy.optimize.linprog` (HiGHS interior-point / simplex solver).

---

## 5. Baseline Comparison Strategy
The optimizer includes a heuristic greedy baseline dispatch for comparison:
- **Renewable Surplus ($R_t > D_t$)**: Charges battery up to max power or $E_{\text{max}}$, exports remaining surplus.
- **Renewable Deficit ($D_t > R_t$)**: Discharges battery up to max power or $E_{\text{min}}$, imports remaining deficit.

Summary performance metrics compute grid import reduction (kWh and %) and net financial cost savings (\$) compared to baseline.

---

## 6. Database Persistence Schema
- **`battery_optimization_runs`** (`BatteryOptimizationRun`): Stores run execution ID (`optimization_run_id`), site ID, initial/final SOC, total charge/discharge/import/export kWh, total grid cost, and cost savings achieved.
- **`battery_optimization_points`** (`BatteryOptimizationPoint`): Relational child table storing per-hour forecast balance, SOC before/after, charge/discharge kWh, grid import/export kWh, cost, and dispatch explanations.

---

## 7. API Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/optimization/run` | Triggers a 24-step battery optimization schedule execution using Stage 6 forecasts. |
| `GET` | `/optimization/{optimization_run_id}` | Retrieves a previously persisted optimization run and dispatch schedule. |

---

## 8. Migration Path for Real Telemetry & Dynamic Tariffs
The optimization service is decoupled from data sources and consumes normalized Pydantic schemas and ORM interfaces. When real smart meters or dynamic time-of-use (TOU) electricity tariffs are added, they can be passed directly into `GridPricingConfig` or ingested via adapters without modifying the optimization engine logic.
