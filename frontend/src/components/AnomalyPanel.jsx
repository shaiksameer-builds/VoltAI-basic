import React from 'react';
import { AlertOctagon, ShieldAlert, Sparkles, CheckCircle2 } from 'lucide-react';

export default function AnomalyPanel({ anomalies, onExplainAnomaly, onTriggerDetection }) {
  const getSeverityBadge = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
      case 'WARNING':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      default:
        return 'bg-sky-500/20 text-sky-400 border-sky-500/40';
    }
  };

  return (
    <div className="glass-card p-5 border border-slate-800 flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <AlertOctagon className="w-5 h-5 text-rose-400" />
              Energy Anomaly Engine
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Physical rules & MAD z-score statistical detection (Stage 8)
            </p>
          </div>

          <button
            onClick={onTriggerDetection}
            className="text-xs font-semibold bg-dark-700 hover:bg-dark-600 text-slate-300 border border-slate-700 px-2.5 py-1 rounded-lg transition-colors"
          >
            Run Scan
          </button>
        </div>

        {/* Anomalies List */}
        {!anomalies || anomalies.length === 0 ? (
          <div className="min-h-[140px] flex flex-col items-center justify-center text-slate-400 text-xs">
            <CheckCircle2 className="w-8 h-8 text-emerald-400/80 mb-1.5" />
            <span className="font-semibold text-slate-300">No anomalies detected</span>
            <span className="text-[11px] text-slate-500 mt-0.5">System operates strictly within nominal physical constraints.</span>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
            {anomalies.map((a, idx) => (
              <div
                key={a.anomaly_id || idx}
                className="bg-dark-800/60 border border-slate-800 p-3 rounded-lg flex flex-col justify-between gap-1.5 hover:border-slate-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase ${getSeverityBadge(a.severity)}`}>
                      {a.severity}
                    </span>
                    <span className="text-xs font-semibold text-slate-200">{a.anomaly_type}</span>
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">
                    {a.timestamp ? new Date(a.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </div>

                <p className="text-xs text-slate-300 leading-snug">{a.description}</p>

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-800/80">
                  <span>Observed: <strong className="text-slate-200">{a.observed_value}</strong></span>
                  <span>Expected: <strong className="text-slate-200">{a.expected_value}</strong></span>
                  <span>Confidence: <strong className="text-emerald-400">{Math.round((a.confidence || 1.0) * 100)}%</strong></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 flex items-center justify-between text-xs border-t border-slate-800">
        <span className="text-slate-500 text-[11px]">Deduplicated & Persisted to DB</span>
        <button
          onClick={onExplainAnomaly}
          className="flex items-center space-x-2 bg-gradient-to-r from-purple-600/30 to-purple-500/20 hover:from-purple-600/50 hover:to-purple-500/40 text-purple-300 border border-purple-500/40 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-sm shadow-purple-500/10"
        >
          <Sparkles className="w-3.5 h-3.5 text-purple-400 animate-pulse" />
          <span>Explain Anomaly with AI</span>
        </button>
      </div>
    </div>
  );
}
