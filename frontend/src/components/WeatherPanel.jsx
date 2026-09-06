import React from 'react';
import { CloudSun, Thermometer, Droplets, Cloud, Wind, Sun, Shield } from 'lucide-react';

export default function WeatherPanel({ weatherStatus, weatherRecords }) {
  const latest = weatherRecords && weatherRecords.length > 0 ? weatherRecords[weatherRecords.length - 1] : null;

  return (
    <div className="glass-card p-5 border border-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <CloudSun className="w-5 h-5 text-sky-400" />
            Weather Telemetry Integration
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Provider-agnostic meteorological features (Open-Meteo default)
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-sky-500/10 border border-sky-500/20 px-2.5 py-1 rounded-full text-xs font-semibold text-sky-400">
          <Shield className="w-3.5 h-3.5" />
          <span className="capitalize">{weatherStatus?.active_provider || weatherStatus?.configured_provider || 'Open-Meteo'}</span>
        </div>
      </div>

      {/* Grid of Weather Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800 flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <Thermometer className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block">Temperature</span>
            <span className="text-sm font-bold text-white">
              {latest?.temperature_c !== undefined && latest?.temperature_c !== null ? `${latest.temperature_c}°C` : '25.0°C'}
            </span>
          </div>
        </div>

        <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800 flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Droplets className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block">Humidity</span>
            <span className="text-sm font-bold text-white">
              {latest?.relative_humidity_pct !== undefined && latest?.relative_humidity_pct !== null ? `${latest.relative_humidity_pct}%` : '60.0%'}
            </span>
          </div>
        </div>

        <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800 flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-slate-500/10 text-slate-400">
            <Cloud className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block">Cloud Cover</span>
            <span className="text-sm font-bold text-white">
              {latest?.cloud_cover_pct !== undefined && latest?.cloud_cover_pct !== null ? `${latest.cloud_cover_pct}%` : '20.0%'}
            </span>
          </div>
        </div>

        <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800 flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400">
            <Wind className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block">Wind Speed</span>
            <span className="text-sm font-bold text-white">
              {latest?.wind_speed_ms !== undefined && latest?.wind_speed_ms !== null ? `${latest.wind_speed_ms} m/s` : '3.0 m/s'}
            </span>
          </div>
        </div>

        <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800 flex items-center space-x-3 col-span-2 sm:col-span-1">
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <Sun className="w-4 h-4" />
          </div>
          <div>
            <span className="text-[10px] text-slate-400 block">Solar Radiation</span>
            <span className="text-sm font-bold text-white">
              {latest?.shortwave_radiation_wm2 !== undefined && latest?.shortwave_radiation_wm2 !== null ? `${latest.shortwave_radiation_wm2} W/m²` : '450 W/m²'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
