import React, { useState } from 'react';
import { BarChart2, Filter } from 'lucide-react';

export default function EnergyOverviewChart({ dailyData }) {
  const [activeSeries, setActiveSeries] = useState({
    consumption: true,
    solar: true,
    wind: true,
    gridImport: true,
  });

  const toggleSeries = (key) => {
    setActiveSeries((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const metrics = dailyData?.daily_metrics || [];

  if (!metrics || metrics.length === 0) {
    return (
      <div className="glass-card p-6 min-h-[300px] flex flex-col items-center justify-center text-slate-400">
        <BarChart2 className="w-10 h-10 mb-2 stroke-[1.5] text-slate-500" />
        <p className="text-sm">No historical telemetry available for this time range.</p>
        <span className="text-xs text-slate-500 mt-1">Upload a CSV or select a different site/time range.</span>
      </div>
    );
  }

  // Calculate max scaling
  const maxVal = Math.max(
    ...metrics.map((m) =>
      Math.max(
        m.total_consumption_kwh || 0,
        m.solar_generation_kwh || 0,
        m.wind_generation_kwh || 0,
        m.grid_import_kwh || 0
      )
    ),
    100
  );

  return (
    <div className="glass-card p-5 border border-slate-800">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-emerald-400" />
            Energy Telemetry Overview
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Daily interval totals: Consumption, Solar, Wind, and Grid Import (kWh)
          </p>
        </div>

        {/* Legend / Toggles */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => toggleSeries('consumption')}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
              activeSeries.consumption
                ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40'
                : 'bg-dark-700 text-slate-400 border-slate-700 opacity-60'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-cyan-400" />
            <span>Consumption</span>
          </button>

          <button
            onClick={() => toggleSeries('solar')}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
              activeSeries.solar
                ? 'bg-amber-500/20 text-amber-400 border-amber-500/40'
                : 'bg-dark-700 text-slate-400 border-slate-700 opacity-60'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>Solar</span>
          </button>

          <button
            onClick={() => toggleSeries('wind')}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
              activeSeries.wind
                ? 'bg-sky-500/20 text-sky-400 border-sky-500/40'
                : 'bg-dark-700 text-slate-400 border-slate-700 opacity-60'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            <span>Wind</span>
          </button>

          <button
            onClick={() => toggleSeries('gridImport')}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
              activeSeries.gridImport
                ? 'bg-purple-500/20 text-purple-400 border-purple-500/40'
                : 'bg-dark-700 text-slate-400 border-slate-700 opacity-60'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            <span>Grid Import</span>
          </button>
        </div>
      </div>

      {/* SVG Bar / Area Chart Container */}
      <div className="h-64 w-full relative flex items-end gap-2 pt-6 pb-6 px-2 border-b border-slate-800">
        {metrics.map((item, idx) => {
          const cHeight = (item.total_consumption_kwh / maxVal) * 100;
          const sHeight = (item.solar_generation_kwh / maxVal) * 100;
          const wHeight = (item.wind_generation_kwh / maxVal) * 100;
          const gHeight = (item.grid_import_kwh / maxVal) * 100;

          return (
            <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group relative">
              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 hidden group-hover:flex flex-col bg-dark-800 text-xs text-slate-200 border border-slate-700 rounded p-2 shadow-xl z-20 whitespace-nowrap">
                <span className="font-bold text-white mb-1">{item.date}</span>
                <span className="text-cyan-400">Consumption: {item.total_consumption_kwh} kWh</span>
                <span className="text-amber-400">Solar: {item.solar_generation_kwh} kWh</span>
                <span className="text-sky-400">Wind: {item.wind_generation_kwh} kWh</span>
                <span className="text-purple-400">Grid Import: {item.grid_import_kwh} kWh</span>
              </div>

              {/* Bars Group */}
              <div className="w-full flex items-end justify-center gap-0.5 h-full">
                {activeSeries.consumption && (
                  <div
                    style={{ height: `${cHeight}%` }}
                    className="w-1.5 bg-cyan-400/80 rounded-t transition-all group-hover:bg-cyan-300"
                  />
                )}
                {activeSeries.solar && (
                  <div
                    style={{ height: `${sHeight}%` }}
                    className="w-1.5 bg-amber-400/80 rounded-t transition-all group-hover:bg-amber-300"
                  />
                )}
                {activeSeries.wind && (
                  <div
                    style={{ height: `${wHeight}%` }}
                    className="w-1.5 bg-sky-400/80 rounded-t transition-all group-hover:bg-sky-300"
                  />
                )}
                {activeSeries.gridImport && (
                  <div
                    style={{ height: `${gHeight}%` }}
                    className="w-1.5 bg-purple-400/80 rounded-t transition-all group-hover:bg-purple-300"
                  />
                )}
              </div>

              {/* X Axis Label */}
              <span className="text-[10px] text-slate-500 mt-2 truncate w-full text-center">
                {item.date?.slice(5)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="flex justify-between items-center text-[11px] text-slate-500 mt-2 px-1">
        <span>Scale Max: {Math.round(maxVal)} kWh</span>
        <span>Showing {metrics.length} daily intervals</span>
      </div>
    </div>
  );
}
