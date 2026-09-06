import React from 'react';
import { Activity, Sun, Wind, Battery, ArrowDownRight, ArrowUpRight, AlertTriangle } from 'lucide-react';

export default function KPICards({ summary, latestTelemetry }) {
  const cards = [
    {
      title: 'Total Consumption',
      value: summary ? `${summary.total_consumption_kwh?.toLocaleString()} kWh` : '--',
      subtitle: summary ? `Avg ${summary.avg_hourly_consumption_kwh} kWh/h` : 'Loading...',
      icon: Activity,
      color: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
      border: 'border-cyan-500/20',
    },
    {
      title: 'Solar Generation',
      value: summary ? `${summary.total_solar_generation_kwh?.toLocaleString()} kWh` : '--',
      subtitle: 'On-site PV Array',
      icon: Sun,
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
    },
    {
      title: 'Wind Generation',
      value: summary ? `${summary.total_wind_generation_kwh?.toLocaleString()} kWh` : '--',
      subtitle: 'Turbine Yield',
      icon: Wind,
      color: 'text-sky-400',
      bg: 'bg-sky-500/10',
      border: 'border-sky-500/20',
    },
    {
      title: 'Renewable Fraction',
      value: summary ? `${summary.renewable_contribution_pct}%` : '--',
      subtitle: summary ? `${summary.total_renewable_generation_kwh?.toLocaleString()} kWh total` : 'Loading...',
      icon: Sun,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      title: 'Grid Net Import',
      value: summary ? `${summary.total_grid_import_kwh?.toLocaleString()} kWh` : '--',
      subtitle: summary ? `Export: ${summary.total_grid_export_kwh} kWh` : 'Loading...',
      icon: ArrowDownRight,
      color: summary && summary.total_grid_import_kwh > 500 ? 'text-amber-400' : 'text-slate-300',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20',
    },
    {
      title: 'Battery State of Charge',
      value: latestTelemetry ? `${latestTelemetry.battery_soc_pct}%` : (summary ? '50.0%' : '--'),
      subtitle: summary ? `Charge: ${summary.total_battery_charge_kwh} kWh` : 'Loading...',
      icon: Battery,
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      title: 'Peak Hourly Demand',
      value: summary ? `${summary.peak_hourly_consumption_kwh} kWh` : '--',
      subtitle: summary ? `Independence: ${summary.energy_independence_pct}%` : 'Loading...',
      icon: AlertTriangle,
      color: 'text-rose-400',
      bg: 'bg-rose-500/10',
      border: 'border-rose-500/20',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <div key={i} className={`glass-card glass-card-hover p-4 border ${c.border}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">{c.title}</span>
              <div className={`p-2 rounded-lg ${c.bg}`}>
                <Icon className={`w-4 h-4 ${c.color}`} />
              </div>
            </div>
            <div className="mt-2">
              <span className="text-lg font-bold text-white tracking-tight">{c.value}</span>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">{c.subtitle}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
