import React from 'react';
import { Battery, Zap, DollarSign, Sparkles, ShieldCheck } from 'lucide-react';

export default function BatteryOptimizationPanel({ optimizationData, onExplainOptimization }) {
  const summary = optimizationData?.summary || {};
  const schedule = optimizationData?.schedule || [];

  return (
    <div className="glass-card p-5 border border-slate-800 flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <Battery className="w-5 h-5 text-emerald-400" />
              Battery Storage LP Optimization
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Linear Programming (scipy.optimize.linprog) cost-minimizing schedule
            </p>
          </div>

          <div className="flex items-center space-x-1 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Exclusive Mode</span>
          </div>
        </div>

        {/* Key Metrics Row */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Est. Cost Savings</span>
            <span className="text-base font-bold text-emerald-400">
              ₹{summary.cost_savings_inr ? summary.cost_savings_inr.toLocaleString() : '0.00'}
            </span>
          </div>

          <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Grid Import Reduced</span>
            <span className="text-base font-bold text-cyan-400">
              {summary.grid_import_reduction_kwh ? summary.grid_import_reduction_kwh.toLocaleString() : '0'} kWh
            </span>
          </div>

          <div className="bg-dark-800/80 p-3 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 block">Total Discharged</span>
            <span className="text-base font-bold text-amber-400">
              {summary.total_battery_discharge_kwh ? summary.total_battery_discharge_kwh.toLocaleString() : '0'} kWh
            </span>
          </div>
        </div>

        {/* Schedule Mini Timeline */}
        <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
          {schedule.slice(0, 6).map((pt, i) => (
            <div key={i} className="flex items-center justify-between text-xs bg-dark-800/50 px-3 py-1.5 rounded border border-slate-800">
              <span className="text-slate-300 font-mono">Hour +{pt.hour_step || i + 1}</span>
              <div className="flex items-center space-x-3">
                <span className="text-slate-400">SOC: {pt.battery_soc_pct || pt.soc}%</span>
                {pt.battery_charge_kwh > 0 && (
                  <span className="text-emerald-400 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded">
                    +Charge {pt.battery_charge_kwh} kW
                  </span>
                )}
                {pt.battery_discharge_kwh > 0 && (
                  <span className="text-amber-400 font-semibold bg-amber-500/10 px-1.5 py-0.5 rounded">
                    -Discharge {pt.battery_discharge_kwh} kW
                  </span>
                )}
                {!pt.battery_charge_kwh && !pt.battery_discharge_kwh && (
                  <span className="text-slate-500">Idle</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer AI Action */}
      <div className="mt-4 pt-3 flex items-center justify-between text-xs border-t border-slate-800">
        <span className="text-slate-500 text-[11px]">Constraints: 10–90% SOC, Peak Rate ₹12/kWh</span>
        <button
          onClick={onExplainOptimization}
          className="flex items-center space-x-2 bg-gradient-to-r from-purple-600/30 to-purple-500/20 hover:from-purple-600/50 hover:to-purple-500/40 text-purple-300 border border-purple-500/40 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm shadow-purple-500/10"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
          <span>Explain Schedule with AI</span>
        </button>
      </div>
    </div>
  );
}
