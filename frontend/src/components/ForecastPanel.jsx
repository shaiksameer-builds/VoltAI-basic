import React, { useState } from 'react';
import { TrendingUp, Sparkles, Sun, Activity, RefreshCw } from 'lucide-react';

export default function ForecastPanel({
  forecastData,
  activeTarget,
  setActiveTarget,
  onExplainForecast,
  isLoadingForecast,
}) {
  const predictions = forecastData?.predictions || [];
  const modelVer = forecastData?.model_version || 'v1.0-multioutput';

  const maxVal = Math.max(...predictions.map((p) => p.predicted_value_kwh || 0), 10);

  return (
    <div className="glass-card p-5 border border-slate-800 flex flex-col justify-between">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-amber-400" />
              24-Hour Predictive Forecast
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Multi-step ML predictions (HistGradientBoosting / RidgeCV)
            </p>
          </div>

          {/* Target Tabs */}
          <div className="flex bg-dark-800 p-1 rounded-lg border border-slate-700">
            <button
              onClick={() => setActiveTarget('solar')}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeTarget === 'solar'
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Sun className="w-3.5 h-3.5" />
              <span>Solar</span>
            </button>

            <button
              onClick={() => setActiveTarget('demand')}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                activeTarget === 'demand'
                  ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Demand</span>
            </button>
          </div>
        </div>

        {/* Forecast Visual Curve */}
        {isLoadingForecast ? (
          <div className="h-44 flex items-center justify-center text-slate-500 text-xs">
            <RefreshCw className="w-5 h-5 animate-spin mr-2" />
            Computing ML forecast model...
          </div>
        ) : predictions.length === 0 ? (
          <div className="h-44 flex items-center justify-center text-slate-500 text-xs">
            No forecast predictions generated.
          </div>
        ) : (
          <div className="h-44 w-full flex items-end gap-1 pt-4 pb-2 px-1 border-b border-slate-800/80">
            {predictions.map((p, idx) => {
              const heightPct = (p.predicted_value_kwh / maxVal) * 100;
              return (
                <div key={idx} className="flex-1 flex flex-col items-center h-full justify-end group relative">
                  {/* Tooltip */}
                  <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col bg-dark-800 text-[11px] text-slate-200 border border-slate-700 rounded p-1.5 shadow-xl z-20 whitespace-nowrap">
                    <span className="font-bold text-white">Hour +{p.horizon_step}</span>
                    <span className={activeTarget === 'solar' ? 'text-amber-400' : 'text-cyan-400'}>
                      {p.predicted_value_kwh} kWh
                    </span>
                  </div>

                  {/* Bar */}
                  <div
                    style={{ height: `${Math.max(heightPct, 4)}%` }}
                    className={`w-full rounded-t transition-all ${
                      activeTarget === 'solar'
                        ? 'bg-gradient-to-t from-amber-600/60 to-amber-400 group-hover:to-amber-300'
                        : 'bg-gradient-to-t from-cyan-600/60 to-cyan-400 group-hover:to-cyan-300'
                    }`}
                  />
                  <span className="text-[9px] text-slate-500 mt-1">+{p.horizon_step}h</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info & AI Explain Button */}
      <div className="mt-4 pt-3 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs border-t border-slate-800">
        <div className="flex items-center space-x-2 text-slate-400">
          <span className="px-2 py-0.5 rounded bg-dark-700 border border-slate-700 text-[10px] font-mono text-emerald-400">
            {modelVer}
          </span>
          <span>Max: {Math.round(maxVal)} kWh</span>
        </div>

        <button
          onClick={() => onExplainForecast(activeTarget)}
          className="w-full sm:w-auto flex items-center justify-center space-x-2 bg-gradient-to-r from-purple-600/30 to-purple-500/20 hover:from-purple-600/50 hover:to-purple-500/40 text-purple-300 border border-purple-500/40 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm shadow-purple-500/10"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
          <span>Explain Forecast with AI</span>
        </button>
      </div>
    </div>
  );
}
