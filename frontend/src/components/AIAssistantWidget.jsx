import React, { useState } from 'react';
import { Bot, Send, Sparkles, AlertCircle, CheckCircle, Info, RefreshCw } from 'lucide-react';

export default function AIAssistantWidget({ aiResponse, onAskAI, isLoadingAI, aiStatus }) {
  const [inputQuery, setInputQuery] = useState('');

  const QUICK_PROMPTS = [
    "Explain today's energy performance",
    "Why is grid import high?",
    "Explain the solar forecast",
    "Why is the battery discharging?",
    "Are there any serious anomalies?",
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;
    onAskAI(inputQuery.trim());
    setInputQuery('');
  };

  const handleQuickClick = (prompt) => {
    setInputQuery(prompt);
    onAskAI(prompt);
  };

  return (
    <div className="glass-card p-5 border border-purple-500/30 flex flex-col justify-between h-full min-h-[420px]">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-gradient-to-tr from-purple-600 to-indigo-600 rounded-xl shadow-lg shadow-purple-500/20">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                VoltAI Energy Assistant
                <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
              </h3>
              <p className="text-xs text-slate-400">Grounded explanation & natural language reasoning</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span
              className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
                aiStatus?.api_key_configured
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
              }`}
            >
              {aiStatus?.api_key_configured ? 'GEMINI ACTIVE' : 'DETERMINISTIC FALLBACK'}
            </span>
          </div>
        </div>

        {/* Quick Prompts Chips */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {QUICK_PROMPTS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleQuickClick(p)}
              disabled={isLoadingAI}
              className="text-[11px] font-medium bg-dark-800 hover:bg-dark-700 text-purple-300 border border-purple-500/20 hover:border-purple-500/40 px-2.5 py-1 rounded-full transition-all"
            >
              {p}
            </button>
          ))}
        </div>

        {/* AI Output Box */}
        <div className="bg-dark-900/90 border border-slate-800 rounded-xl p-4 min-h-[200px] max-h-[300px] overflow-y-auto mb-4 flex flex-col justify-between">
          {isLoadingAI ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400 text-xs py-8">
              <RefreshCw className="w-6 h-6 animate-spin text-purple-400 mb-2" />
              <span>Analyzing VoltAI context & generating grounded explanation...</span>
            </div>
          ) : aiResponse ? (
            <div>
              {/* Intent & Fallback Indicator */}
              <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-800 text-xs">
                <span className="font-mono text-purple-400 font-semibold uppercase text-[11px]">
                  INTENT: {aiResponse.intent}
                </span>

                {aiResponse.is_fallback && (
                  <span className="flex items-center space-x-1 text-amber-400 text-[10px] bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                    <AlertCircle className="w-3 h-3" />
                    <span>Fallback Mode Active</span>
                  </span>
                )}
              </div>

              {/* Main Natural Language Text */}
              <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-line font-normal">
                {aiResponse.response}
              </div>

              {/* Grounding Facts Used */}
              {aiResponse.facts_used && aiResponse.facts_used.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Grounded VoltAI Facts Used:
                  </span>
                  <ul className="text-[11px] text-slate-300 space-y-0.5">
                    {aiResponse.facts_used.map((fact, fIdx) => (
                      <li key={fIdx} className="flex items-center space-x-1.5">
                        <CheckCircle className="w-3 h-3 text-emerald-400 shrink-0" />
                        <span>{fact}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-500 text-xs py-8">
              <Info className="w-8 h-8 text-purple-400/40 mb-2" />
              <p className="text-center font-medium">Ask any question about site energy performance, forecasts, anomalies, or battery schedules.</p>
            </div>
          )}
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask VoltAI AI assistant..."
          disabled={isLoadingAI}
          className="flex-1 bg-dark-800 text-white text-xs border border-slate-700 rounded-lg px-3 py-2.5 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 placeholder-slate-500"
        />
        <button
          type="submit"
          disabled={isLoadingAI || !inputQuery.trim()}
          className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white p-2.5 rounded-lg shadow-md shadow-purple-600/20 transition-all"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
