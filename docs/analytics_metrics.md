# VoltAI Energy Analytics Specification

## 1. Overview & Architectural Principles

The VoltAI Energy Analytics engine computes deterministic metrics, efficiency indicators, and aggregations directly from normalized `EnergyReading` time-series records in the database.

- **Source Independence:** Analytics operate strictly on normalized database models. Whether data originates from CSV files, Smart Meters, IoT edge devices, or SCADA gateways, the analytics algorithms remain identical.
- **Deterministic Analytics (Not AI/ML):** These calculations are exact engineering aggregations and balance equations. They provide the ground-truth baseline and feature inputs for downstream forecasting and battery dispatch optimization models.

---

## 2. Measurement Semantics: Energy (kWh) vs. Power (kW)

- **Interval Energy (kWh):** All telemetry flows (`solar_generation`, `wind_generation`, `energy_consumption`, `battery_charge`, `battery_discharge`, `grid_import`, `grid_export`) represent total energy transferred over the measurement interval in **kilowatt-hours (kWh)**.
- **Hourly Equivalence:** For standard 1-hour recording intervals ($\Delta t = 1.0\text{ h}$), interval energy in kWh is numerically equal to the average active power in kilowatts:
  $$\bar{P}\text{ (kW)} = \frac{E\text{ (kWh)}}{1.0\text{ h}}$$
- **State of Charge (%):** `battery_soc` represents the instantaneous percentage ($0.0\% \le \text{SoC} \le 100.0\%$) of battery capacity remaining at the observation timestamp.

---

## 3. Metrics & Mathematical Formulas

### A. Total Renewable Generation
Sum of all renewable energy generation flows:
$$\text{Renewable Generation (kWh)} = \text{Solar Generation (kWh)} + \text{Wind Generation (kWh)}$$

### B. Renewable Contribution Percentage (%)
Measures the proportion of site energy consumption matched by on-site renewable generation:
$$\text{Renewable Contribution (\%)} = \begin{cases} 
\left(\frac{\text{Renewable Generation (kWh)}}{\text{Energy Consumption (kWh)}}\right) \times 100, & \text{if Consumption} > 0 \\ 
0.0\%, & \text{if Consumption} \le 0 
\end{cases}$$
*(Note: May exceed 100% when generation exceeds local consumption, representing an energy surplus exported or stored).*

### C. Grid Dependence Percentage (%)
The ratio of imported utility energy to total facility consumption:
$$\text{Grid Dependence (\%)} = \begin{cases} 
\left(\frac{\text{Grid Import (kWh)}}{\text{Energy Consumption (kWh)}}\right) \times 100, & \text{if Consumption} > 0 \\ 
0.0\%, & \text{if Consumption} \le 0 
\end{cases}$$

### D. Energy Independence Percentage (%)
Quantifies the percentage of site consumption fulfilled on-site without drawing energy from the public grid:
$$\text{Energy Independence (\%)} = \begin{cases} 
\max\left(0.0, \min\left(100.0, \frac{\text{Energy Consumption} - \text{Grid Import}}{\text{Energy Consumption}} \times 100\right)\right), & \text{if Consumption} > 0 \\ 
0.0\%, & \text{if Consumption} \le 0 
\end{cases}$$

### E. Net Grid Energy (kWh)
Net energy interchange with the utility grid:
$$\text{Net Grid Energy (kWh)} = \text{Grid Import (kWh)} - \text{Grid Export (kWh)}$$
- Positive: Net consumer of grid energy.
- Negative: Net exporter / supplier to the grid.

### F. Average and Peak Demand (kWh)
- **Average Hourly Consumption (kWh):** Mean interval consumption across all evaluated records.
- **Peak Hourly Consumption (kWh):** The maximum single-hour consumption observed in the query window.

---

## 4. Daily Aggregation Logic

When aggregating hourly telemetry to daily intervals:
1. Hourly timestamps are grouped by calendar date (`YYYY-MM-DD`).
2. Flow quantities (consumption, solar, wind, battery throughput, grid import/export) are summed over the 24 intervals of each date.
3. Daily peak consumption identifies the maximum single-hour interval within that calendar date and captures the timestamp of its occurrence.
4. Ratios (renewable contribution %, average consumption) are derived from the aggregated daily sums.

---

## 5. Filtering & Query Parameters

All analytics endpoints support standard query parameters:
- `site_id` (str, optional): Restricts calculation to a single facility or microgrid.
- `start` (ISO 8601 datetime, optional): Inclusive lower bound for interval timestamps.
- `end` (ISO 8601 datetime, optional): Inclusive upper bound for interval timestamps.

---

## 6. Zero & Empty Database Handling

When querying a database or filter window with zero matching records:
- Endpoints return **HTTP 200 OK** (not HTTP 500 or 404).
- Aggregated metrics return `0.0`.
- List fields return empty arrays `[]`.
- `reading_count` returns `0`.
- `PeakDemandResponse` returns `peak_consumption_kwh = 0.0` and `is_empty = true`.
