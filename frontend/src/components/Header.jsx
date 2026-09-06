import React from 'react';
import { Zap, Server, Upload, RefreshCw, Activity } from 'lucide-react';

export default function Header({
  selectedSite,
  setSelectedSite,
  timeRange,
  setTimeRange,
  onRefresh,
  onOpenUpload,
  healthStatus,
  isLiveMode,
  setIsLiveMode,
}) {
  const SITES = [
    { id: 'site_001', name: 'Site 001 (Pune HQ)' },
    { id: 'site_002', name: 'Site 002 (Mumbai Facility)' },
    { id: 'site_003', name: 'Site 003 (Solar Farm)' },
    { id: 'site_anom_01', name: 'Site Anom 01 (Test Lab)' },
  ];

  return (
    <header className="bg-dark-800/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-30 px-6 py-4">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-gradient-to-tr from-emerald-500 to-cyan-500 rounded-xl shadow-lg shadow-emerald-500/20">
            <Zap className="w-6 h-6 text-dark-900 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold tracking-tight text-white">VoltAI</h1>
              <span className="px-2 py-0.5 text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
                SIH26200
              </span>
            </div>
            <p className="text-xs text-slate-400">Renewable Energy Intelligence & Battery Optimization</p>
          </div>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Site Selector */}
          <div className="relative">
            <select
              value={selectedSite}
              onChange={(e) => setSelectedSite(e.target.value)}
              className="bg-dark-700 text-slate-200 text-sm font-medium border border-slate-700 rounded-lg px-3 py-2 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            >
              {SITES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Time Range */}
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-dark-700 text-slate-200 text-sm font-medium border border-slate-700 rounded-lg px-3 py-2 focus:outline-none focus:border-emerald-500"
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>

          {/* Live Mode Toggle */}
          <button
            onClick={() => setIsLiveMode(!isLiveMode)}
            className={`flex items-center space-x-1.5 text-xs font-semibold px-3 py-2 rounded-lg border transition-all ${
              isLiveMode
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 shadow-sm shadow-emerald-500/20'
                : 'bg-dark-700 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
          >
            <Activity className={`w-3.5 h-3.5 ${isLiveMode ? 'animate-pulse text-emerald-400' : ''}`} />
            <span>{isLiveMode ? 'LIVE STREAM' : 'HISTORICAL'}</span>
          </button>

          {/* Refresh */}
          <button
            onClick={onRefresh}
            className="p-2 bg-dark-700 hover:bg-dark-600 text-slate-300 hover:text-white rounded-lg border border-slate-700 transition-colors"
            title="Refresh Data"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* Upload CSV */}
          <button
            onClick={onOpenUpload}
            className="flex items-center space-x-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white text-xs font-semibold px-3.5 py-2 rounded-lg shadow-md shadow-emerald-600/20 transition-all"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Ingest CSV</span>
          </button>

          {/* System Health */}
          <div className="flex items-center space-x-2 bg-dark-700/60 border border-slate-700/50 px-3 py-1.5 rounded-lg text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                healthStatus === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-slate-300 font-medium capitalize">
              {healthStatus || 'Checking'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
