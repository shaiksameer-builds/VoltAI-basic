"""
VoltAI Battery Optimization Service (Stage 7)

Implements deterministic linear programming solver (via scipy.optimize.linprog)
and baseline greedy dispatch for optimal 24-step battery storage scheduling.
"""

from datetime import datetime, timezone
import logging
from typing import List, Tuple, Optional
import numpy as np
from scipy.optimize import linprog
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.models import BatteryOptimizationPoint, BatteryOptimizationRun, EnergyReading
from backend.app.schemas.optimization import (
    BatteryConfig,
    GridPricingConfig,
    OptimizationPoint,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationSummary,
)
from backend.app.services.energy_forecasting import EnergyForecastingService

logger = logging.getLogger(__name__)


class BatteryOptimizationService:
    """
    Deterministic service handling battery storage optimization and baseline comparison.
    """

    @classmethod
    def calculate_baseline(
        cls,
        timestamps: List[datetime],
        renewable_kwh: List[float],
        demand_kwh: List[float],
        battery_config: BatteryConfig,
        pricing_config: GridPricingConfig,
    ) -> List[OptimizationPoint]:
        """
        Calculates a simple baseline schedule:
        - Charge battery using renewable surplus (R_t > D_t) up to max_charge or max_soc.
        - Discharge battery to meet deficit (D_t > R_t) up to max_discharge or min_soc.
        """
        N = len(timestamps)
        points: List[OptimizationPoint] = []

        cap_kwh = battery_config.battery_capacity_kwh
        min_e = cap_kwh * (battery_config.min_soc_pct / 100.0)
        max_e = cap_kwh * (battery_config.max_soc_pct / 100.0)
        max_c = battery_config.max_charge_power_kw  # 1h interval
        max_d = battery_config.max_discharge_power_kw

        eta_c = battery_config.charge_efficiency
        eta_d = battery_config.discharge_efficiency

        current_soc_pct = battery_config.initial_soc_pct
        current_e = cap_kwh * (current_soc_pct / 100.0)

        for t in range(N):
            ts = timestamps[t]
            r_t = renewable_kwh[t]
            d_t = demand_kwh[t]
            balance_t = r_t - d_t
            soc_before = current_soc_pct

            charge_kwh = 0.0
            discharge_kwh = 0.0
            curtail_kwh = 0.0

            if balance_t > 0:
                # Renewable Surplus: try charging
                max_storable_energy = (max_e - current_e) / eta_c
                charge_kwh = min(balance_t, max_c, max(0.0, max_storable_energy))
                surplus_remaining = balance_t - charge_kwh
                grid_export = surplus_remaining
                grid_import = 0.0
                reason = "Baseline: Charge from renewable surplus" if charge_kwh > 0 else "Baseline: Export surplus"
            else:
                # Renewable Deficit: try discharging
                deficit = abs(balance_t)
                max_drawable_energy = (current_e - min_e) * eta_d
                discharge_kwh = min(deficit, max_d, max(0.0, max_drawable_energy))
                unmet_deficit = deficit - discharge_kwh
                grid_import = unmet_deficit
                grid_export = 0.0
                reason = "Baseline: Discharge for deficit" if discharge_kwh > 0 else "Baseline: Import for deficit"

            current_e += (charge_kwh * eta_c) - (discharge_kwh / eta_d)
            current_soc_pct = round(min(100.0, max(0.0, (current_e / cap_kwh) * 100.0)), 4)

            grid_cost = (grid_import * pricing_config.import_price_per_kwh) - (grid_export * pricing_config.export_price_per_kwh)

            points.append(
                OptimizationPoint(
                    timestamp=ts,
                    forecast_renewable_kwh=round(r_t, 4),
                    forecast_demand_kwh=round(d_t, 4),
                    forecast_balance_kwh=round(balance_t, 4),
                    battery_soc_before_pct=round(soc_before, 4),
                    battery_charge_kwh=round(charge_kwh, 4),
                    battery_discharge_kwh=round(discharge_kwh, 4),
                    battery_soc_after_pct=current_soc_pct,
                    grid_import_kwh=round(grid_import, 4),
                    grid_export_kwh=round(grid_export, 4),
                    curtailed_energy_kwh=round(curtail_kwh, 4),
                    estimated_grid_cost=round(grid_cost, 4),
                    optimization_reason=reason,
                )
            )

        return points

    @classmethod
    def solve_linprog(
        cls,
        timestamps: List[datetime],
        renewable_kwh: List[float],
        demand_kwh: List[float],
        battery_config: BatteryConfig,
        pricing_config: GridPricingConfig,
        cycling_penalty: float = 0.001,
    ) -> List[OptimizationPoint]:
        """
        Solves 24-step LP optimal battery dispatch using scipy.optimize.linprog.

        Decision variables per step t (4N total):
            x = [C_0..C_N-1, X_0..X_N-1, G_imp_0..G_imp_N-1, G_exp_0..G_exp_N-1]

        Objective:
            min sum_{t=0}^{N-1} [ G_imp_t * p_imp - G_exp_t * p_exp + penalty * (C_t + X_t) ]
        """
        N = len(timestamps)
        cap_kwh = battery_config.battery_capacity_kwh
        min_e = cap_kwh * (battery_config.min_soc_pct / 100.0)
        max_e = cap_kwh * (battery_config.max_soc_pct / 100.0)
        max_c = battery_config.max_charge_power_kw
        max_d = battery_config.max_discharge_power_kw
        eta_c = battery_config.charge_efficiency
        eta_d = battery_config.discharge_efficiency
        initial_e = cap_kwh * (battery_config.initial_soc_pct / 100.0)

        p_imp = pricing_config.import_price_per_kwh
        p_exp = pricing_config.export_price_per_kwh

        # Cost vector c of length 4N
        # c = [ (cycling_penalty)*N, (cycling_penalty)*N, (p_imp)*N, (-p_exp)*N ]
        c_charge = np.full(N, cycling_penalty)
        c_discharge = np.full(N, cycling_penalty)
        c_import = np.full(N, p_imp)
        c_export = np.full(N, -p_exp)
        c = np.concatenate([c_charge, c_discharge, c_import, c_export])

        # Equality Constraints A_eq * x = b_eq
        # 1. Energy balance per step t: R_t + G_imp_t + X_t = D_t + C_t + G_exp_t
        #    ==> -C_t + X_t + G_imp_t - G_exp_t = D_t - R_t
        A_eq_balance = np.zeros((N, 4 * N))
        b_eq_balance = np.zeros(N)
        for t in range(N):
            A_eq_balance[t, t] = -1.0         # -C_t
            A_eq_balance[t, N + t] = 1.0     # +X_t
            A_eq_balance[t, 2 * N + t] = 1.0 # +G_imp_t
            A_eq_balance[t, 3 * N + t] = -1.0# -G_exp_t
            b_eq_balance[t] = demand_kwh[t] - renewable_kwh[t]

        A_eq = A_eq_balance
        b_eq = b_eq_balance

        # Inequality Constraints A_ub * x <= b_ub
        # Battery SOC bounds for k=0..N-1:
        # E_k = initial_e + sum_{t=0}^k (eta_c * C_t - X_t / eta_d)
        # min_e <= E_k <= max_e
        # 1) E_k <= max_e ==> sum_{t=0}^k (eta_c * C_t - X_t / eta_d) <= max_e - initial_e
        # 2) E_k >= min_e ==> sum_{t=0}^k (-eta_c * C_t + X_t / eta_d) <= initial_e - min_e
        A_ub_list = []
        b_ub_list = []

        for k in range(N):
            row_upper = np.zeros(4 * N)
            row_lower = np.zeros(4 * N)
            for t in range(k + 1):
                row_upper[t] = eta_c
                row_upper[N + t] = -1.0 / eta_d

                row_lower[t] = -eta_c
                row_lower[N + t] = 1.0 / eta_d

            A_ub_list.append(row_upper)
            b_ub_list.append(max_e - initial_e)

            A_ub_list.append(row_lower)
            b_ub_list.append(initial_e - min_e)

        A_ub = np.array(A_ub_list)
        b_ub = np.array(b_ub_list)

        # Variable bounds (0 <= x_i <= upper_bound)
        bounds = []
        for t in range(N):
            bounds.append((0.0, max_c))      # C_t
        for t in range(N):
            bounds.append((0.0, max_d))      # X_t
        for t in range(N):
            bounds.append((0.0, None))       # G_imp_t
        for t in range(N):
            bounds.append((0.0, None))       # G_exp_t

        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

        if not res.success:
            logger.warning(f"Linear programming optimization did not solve cleanly ({res.message}). Falling back to baseline.")
            return cls.calculate_baseline(timestamps, renewable_kwh, demand_kwh, battery_config, pricing_config)

        x_opt = res.x
        charges = x_opt[:N]
        discharges = x_opt[N:2*N]
        imports = x_opt[2*N:3*N]
        exports = x_opt[3*N:]

        # Post-process into OptimizationPoints
        points: List[OptimizationPoint] = []
        current_e = initial_e
        current_soc_pct = battery_config.initial_soc_pct

        for t in range(N):
            ts = timestamps[t]
            r_t = renewable_kwh[t]
            d_t = demand_kwh[t]
            balance_t = r_t - d_t
            soc_before = current_soc_pct

            c_t = max(0.0, float(charges[t]))
            x_t = max(0.0, float(discharges[t]))
            g_imp = max(0.0, float(imports[t]))
            g_exp = max(0.0, float(exports[t]))

            # Clean near-zero floating point artifacts
            if c_t < 1e-4: c_t = 0.0
            if x_t < 1e-4: x_t = 0.0
            if g_imp < 1e-4: g_imp = 0.0
            if g_exp < 1e-4: g_exp = 0.0

            current_e += (c_t * eta_c) - (x_t / eta_d)
            current_soc_pct = round(min(100.0, max(0.0, (current_e / cap_kwh) * 100.0)), 4)

            grid_cost = (g_imp * p_imp) - (g_exp * p_exp)

            reason = "Optimized: Idle"
            if c_t > 0: reason = f"Optimized: Charge {c_t:.2f} kWh"
            elif x_t > 0: reason = f"Optimized: Discharge {x_t:.2f} kWh"

            points.append(
                OptimizationPoint(
                    timestamp=ts,
                    forecast_renewable_kwh=round(r_t, 4),
                    forecast_demand_kwh=round(d_t, 4),
                    forecast_balance_kwh=round(balance_t, 4),
                    battery_soc_before_pct=round(soc_before, 4),
                    battery_charge_kwh=round(c_t, 4),
                    battery_discharge_kwh=round(x_t, 4),
                    battery_soc_after_pct=current_soc_pct,
                    grid_import_kwh=round(g_imp, 4),
                    grid_export_kwh=round(g_exp, 4),
                    curtailed_energy_kwh=0.0,
                    estimated_grid_cost=round(grid_cost, 4),
                    optimization_reason=reason,
                )
            )

        return points

    @classmethod
    def optimize_schedule(
        cls,
        db: Session,
        request: OptimizationRequest,
        persist: bool = True,
    ) -> OptimizationResponse:
        """
        Executes optimal battery dispatch workflow using Stage 6 forecasts and persists results.
        """
        # Fetch latest SOC from database telemetry if default is provided
        battery_cfg = request.battery_config
        stmt = (
            select(EnergyReading)
            .where(EnergyReading.site_id == request.site_id)
            .order_by(EnergyReading.timestamp.desc())
            .limit(1)
        )
        latest_reading = db.scalars(stmt).first()
        if latest_reading and latest_reading.battery_soc is not None:
            # Update initial SOC dynamically from current site telemetry
            updated_soc = max(battery_cfg.min_soc_pct, min(battery_cfg.max_soc_pct, latest_reading.battery_soc))
            battery_cfg = BatteryConfig(
                battery_capacity_kwh=battery_cfg.battery_capacity_kwh,
                min_soc_pct=battery_cfg.min_soc_pct,
                max_soc_pct=battery_cfg.max_soc_pct,
                max_charge_power_kw=battery_cfg.max_charge_power_kw,
                max_discharge_power_kw=battery_cfg.max_discharge_power_kw,
                charge_efficiency=battery_cfg.charge_efficiency,
                discharge_efficiency=battery_cfg.discharge_efficiency,
                initial_soc_pct=updated_soc,
            )

        # Retrieve Stage 6 forecasts
        renewable_resp = EnergyForecastingService.generate_forecast(
            db, request.site_id, "renewable", request.horizon_hours, persist=False
        )
        demand_resp = EnergyForecastingService.generate_forecast(
            db, request.site_id, "demand", request.horizon_hours, persist=False
        )

        timestamps = [p.target_timestamp for p in renewable_resp.predictions]
        ren_kwh = [p.predicted_value_kwh for p in renewable_resp.predictions]
        dem_kwh = [p.predicted_value_kwh for p in demand_resp.predictions]

        # Calculate baseline & optimized schedules
        baseline_schedule = cls.calculate_baseline(timestamps, ren_kwh, dem_kwh, battery_cfg, request.pricing_config)
        optimized_schedule = cls.solve_linprog(
            timestamps, ren_kwh, dem_kwh, battery_cfg, request.pricing_config, request.cycling_penalty_per_kwh
        )

        # Calculate summary comparison metrics
        tot_ren = sum(ren_kwh)
        tot_dem = sum(dem_kwh)

        base_imp = sum(p.grid_import_kwh for p in baseline_schedule)
        opt_imp = sum(p.grid_import_kwh for p in optimized_schedule)
        imp_red = base_imp - opt_imp
        imp_red_pct = (imp_red / base_imp * 100.0) if base_imp > 0 else 0.0

        base_cost = sum(p.estimated_grid_cost for p in baseline_schedule)
        opt_cost = sum(p.estimated_grid_cost for p in optimized_schedule)
        savings = base_cost - opt_cost
        savings_pct = (savings / base_cost * 100.0) if base_cost > 0 else 0.0

        summary = OptimizationSummary(
            total_renewable_kwh=round(tot_ren, 4),
            total_demand_kwh=round(tot_dem, 4),
            baseline_grid_import_kwh=round(base_imp, 4),
            optimized_grid_import_kwh=round(opt_imp, 4),
            grid_import_reduction_kwh=round(imp_red, 4),
            grid_import_reduction_pct=round(imp_red_pct, 4),
            baseline_grid_cost=round(base_cost, 4),
            optimized_grid_cost=round(opt_cost, 4),
            cost_savings=round(savings, 4),
            cost_savings_pct=round(savings_pct, 4),
        )

        now = datetime.now(timezone.utc)
        run_id = f"OPT-{request.site_id.upper()}-{now.strftime('%Y%m%d%H%M%S')}"

        response = OptimizationResponse(
            optimization_run_id=run_id,
            site_id=request.site_id,
            horizon_hours=request.horizon_hours,
            created_at=now,
            battery_config=battery_cfg,
            pricing_config=request.pricing_config,
            summary=summary,
            schedule=optimized_schedule,
        )

        if persist:
            cls._persist_optimization_run(db, response)

        return response

    @classmethod
    def _persist_optimization_run(cls, db: Session, response: OptimizationResponse) -> None:
        """Persists BatteryOptimizationRun and child points into database."""
        tot_charge = sum(p.battery_charge_kwh for p in response.schedule)
        tot_discharge = sum(p.battery_discharge_kwh for p in response.schedule)
        tot_import = sum(p.grid_import_kwh for p in response.schedule)
        tot_export = sum(p.grid_export_kwh for p in response.schedule)

        run_db = BatteryOptimizationRun(
            optimization_run_id=response.optimization_run_id,
            site_id=response.site_id,
            created_at=response.created_at,
            horizon_hours=response.horizon_hours,
            battery_capacity_kwh=response.battery_config.battery_capacity_kwh,
            initial_soc_pct=response.battery_config.initial_soc_pct,
            final_soc_pct=response.schedule[-1].battery_soc_after_pct if response.schedule else response.battery_config.initial_soc_pct,
            total_charge_kwh=round(tot_charge, 4),
            total_discharge_kwh=round(tot_discharge, 4),
            total_grid_import_kwh=round(tot_import, 4),
            total_grid_export_kwh=round(tot_export, 4),
            estimated_grid_cost=response.summary.optimized_grid_cost,
            grid_import_reduction_kwh=response.summary.grid_import_reduction_kwh,
            cost_savings=response.summary.cost_savings,
            optimizer_version="v1.0-linprog",
        )
        db.add(run_db)

        points_db = [
            BatteryOptimizationPoint(
                optimization_run_id=response.optimization_run_id,
                timestamp=p.timestamp,
                forecast_renewable_kwh=p.forecast_renewable_kwh,
                forecast_demand_kwh=p.forecast_demand_kwh,
                forecast_balance_kwh=p.forecast_balance_kwh,
                battery_soc_before_pct=p.battery_soc_before_pct,
                battery_charge_kwh=p.battery_charge_kwh,
                battery_discharge_kwh=p.battery_discharge_kwh,
                battery_soc_after_pct=p.battery_soc_after_pct,
                grid_import_kwh=p.grid_import_kwh,
                grid_export_kwh=p.grid_export_kwh,
                curtailed_energy_kwh=p.curtailed_energy_kwh,
                estimated_grid_cost=p.estimated_grid_cost,
                optimization_reason=p.optimization_reason,
            )
            for p in response.schedule
        ]
        db.add_all(points_db)
        db.commit()

    @classmethod
    def get_persisted_run(cls, db: Session, optimization_run_id: str) -> Optional[OptimizationResponse]:
        """Retrieves a persisted optimization run and schedule points."""
        run_db = db.scalars(
            select(BatteryOptimizationRun).where(BatteryOptimizationRun.optimization_run_id == optimization_run_id)
        ).first()
        if not run_db:
            return None

        points_db = db.scalars(
            select(BatteryOptimizationPoint)
            .where(BatteryOptimizationPoint.optimization_run_id == optimization_run_id)
            .order_by(BatteryOptimizationPoint.timestamp.asc())
        ).all()

        schedule = [
            OptimizationPoint(
                timestamp=pt.timestamp,
                forecast_renewable_kwh=pt.forecast_renewable_kwh,
                forecast_demand_kwh=pt.forecast_demand_kwh,
                forecast_balance_kwh=pt.forecast_balance_kwh,
                battery_soc_before_pct=pt.battery_soc_before_pct,
                battery_charge_kwh=pt.battery_charge_kwh,
                battery_discharge_kwh=pt.battery_discharge_kwh,
                battery_soc_after_pct=pt.battery_soc_after_pct,
                grid_import_kwh=pt.grid_import_kwh,
                grid_export_kwh=pt.grid_export_kwh,
                curtailed_energy_kwh=pt.curtailed_energy_kwh,
                estimated_grid_cost=pt.estimated_grid_cost,
                optimization_reason=pt.optimization_reason,
            )
            for pt in points_db
        ]

        # Construct dummy configs for response reconstruct
        battery_cfg = BatteryConfig(
            battery_capacity_kwh=run_db.battery_capacity_kwh,
            initial_soc_pct=run_db.initial_soc_pct,
        )
        pricing_cfg = GridPricingConfig()

        summary = OptimizationSummary(
            total_renewable_kwh=round(sum(p.forecast_renewable_kwh for p in schedule), 4),
            total_demand_kwh=round(sum(p.forecast_demand_kwh for p in schedule), 4),
            baseline_grid_import_kwh=round(run_db.total_grid_import_kwh + run_db.grid_import_reduction_kwh, 4),
            optimized_grid_import_kwh=round(run_db.total_grid_import_kwh, 4),
            grid_import_reduction_kwh=run_db.grid_import_reduction_kwh,
            grid_import_reduction_pct=0.0,
            baseline_grid_cost=round(run_db.estimated_grid_cost + run_db.cost_savings, 4),
            optimized_grid_cost=run_db.estimated_grid_cost,
            cost_savings=run_db.cost_savings,
            cost_savings_pct=0.0,
        )

        return OptimizationResponse(
            optimization_run_id=run_db.optimization_run_id,
            site_id=run_db.site_id,
            horizon_hours=run_db.horizon_hours,
            created_at=run_db.created_at,
            battery_config=battery_cfg,
            pricing_config=pricing_cfg,
            summary=summary,
            schedule=schedule,
        )
