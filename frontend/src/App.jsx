import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import KPICards from './components/KPICards';
import EnergyOverviewChart from './components/EnergyOverviewChart';
import ForecastPanel from './components/ForecastPanel';
import BatteryOptimizationPanel from './components/BatteryOptimizationPanel';
import AnomalyPanel from './components/AnomalyPanel';
import WeatherPanel from './components/WeatherPanel';
import AIAssistantWidget from './components/AIAssistantWidget';
import CSVUploadModal from './components/CSVUploadModal';
import { VoltAIAPI } from './services/api';

export default function App() {
  const [selectedSite, setSelectedSite] = useState('site_001');
  const [timeRange, setTimeRange] = useState('24h');
  const [isLiveMode, setIsLiveMode] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Data states
  const [healthStatus, setHealthStatus] = useState('healthy');
  const [summary, setSummary] = useState(null);
  const [dailyAnalytics, setDailyAnalytics] = useState(null);
  const [forecastTarget, setForecastTarget] = useState('solar');
  const [forecastData, setForecastData] = useState(null);
  const [optimizationData, setOptimizationData] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [weatherStatus, setWeatherStatus] = useState(null);
  const [weatherRecords, setWeatherRecords] = useState([]);
  const [aiStatus, setAIStatus] = useState(null);
  const [aiResponse, setAIResponse] = useState(null);

  // Loading states
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);
  const [isLoadingAI, setIsLoadingAI] = useState(false);

  // Fetch data for selected site
  const loadDashboardData = useCallback(async () => {
    try {
      // 1. Health check
      VoltAIAPI.getHealth().then((h) => setHealthStatus(h.status)).catch(() => setHealthStatus('degraded'));

      // 2. Summary & Daily analytics
      const [sum, daily] = await Promise.allSettled([
        VoltAIAPI.getSummary(selectedSite),
        VoltAIAPI.getDailyAnalytics(selectedSite),
      ]);
      if (sum.status === 'fulfilled') setSummary(sum.value);
      if (daily.status === 'fulfilled') setDailyAnalytics(daily.value);

      // 3. Optimization
      VoltAIAPI.getOptimizationSchedule(selectedSite)
        .then((opt) => setOptimizationData(opt))
        .catch((e) => console.warn('Opt fetch error:', e.message));

      // 4. Anomalies
      VoltAIAPI.getAnomalies(selectedSite)
        .then((anom) => setAnomalies(Array.isArray(anom) ? anom : []))
        .catch((e) => console.warn('Anom fetch error:', e.message));

      // 5. Weather
      VoltAIAPI.getWeatherStatus().then((w) => setWeatherStatus(w)).catch(() => {});
      VoltAIAPI.getWeatherRecords(selectedSite).then((w) => setWeatherRecords(w || [])).catch(() => {});

      // 6. AI Status
      VoltAIAPI.getAIStatus().then((ai) => setAIStatus(ai)).catch(() => {});
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    }
  }, [selectedSite]);

  // Forecast fetch
  const loadForecast = useCallback(async () => {
    setIsLoadingForecast(true);
    try {
      const data = await VoltAIAPI.getForecast(selectedSite, forecastTarget, 24);
      setForecastData(data);
    } catch (err) {
      console.warn('Forecast error:', err.message);
    } finally {
      setIsLoadingForecast(false);
    }
  }, [selectedSite, forecastTarget]);

  // Initial & site change trigger
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  useEffect(() => {
    loadForecast();
  }, [loadForecast]);

  // AI Actions
  const handleAskAI = async (query) => {
    setIsLoadingAI(true);
    try {
      const res = await VoltAIAPI.askAI(query, selectedSite);
      setAIResponse(res);
    } catch (err) {
      console.error('AI Error:', err);
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleExplainForecast = async (target) => {
    setIsLoadingAI(true);
    try {
      const res = await VoltAIAPI.explainForecast(selectedSite, target === 'solar' ? 'solar_generation' : 'energy_consumption');
      setAIResponse(res);
    } catch (err) {
      console.error('AI Forecast error:', err);
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleExplainOptimization = async () => {
    setIsLoadingAI(true);
    try {
      const res = await VoltAIAPI.explainOptimization(selectedSite);
      setAIResponse(res);
    } catch (err) {
      console.error('AI Opt error:', err);
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleExplainAnomaly = async () => {
    setIsLoadingAI(true);
    try {
      const res = await VoltAIAPI.explainAnomaly(selectedSite);
      setAIResponse(res);
    } catch (err) {
      console.error('AI Anom error:', err);
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleTriggerAnomalyDetection = async () => {
    try {
      const resp = await VoltAIAPI.triggerAnomalyDetection(selectedSite);
      if (resp && resp.anomalies) {
        setAnomalies(resp.anomalies);
      }
    } catch (err) {
      console.error('Trigger anomaly error:', err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-dark-900 text-slate-100">
      {/* Top Header Navigation */}
      <Header
        selectedSite={selectedSite}
        setSelectedSite={setSelectedSite}
        timeRange={timeRange}
        setTimeRange={setTimeRange}
        onRefresh={() => { loadDashboardData(); loadForecast(); }}
        onOpenUpload={() => setIsUploadOpen(true)}
        healthStatus={healthStatus}
        isLiveMode={isLiveMode}
        setIsLiveMode={setIsLiveMode}
      />

      {/* Main Dashboard Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* KPI Cards Row */}
        <KPICards summary={summary} latestTelemetry={null} />

        {/* Energy Overview Chart */}
        <EnergyOverviewChart dailyData={dailyAnalytics} />

        {/* 2-Column Grid: Forecast & Optimization */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ForecastPanel
            forecastData={forecastData}
            activeTarget={forecastTarget}
            setActiveTarget={setForecastTarget}
            onExplainForecast={handleExplainForecast}
            isLoadingForecast={isLoadingForecast}
          />

          <BatteryOptimizationPanel
            optimizationData={optimizationData}
            onExplainOptimization={handleExplainOptimization}
          />
        </div>

        {/* Weather Telemetry */}
        <WeatherPanel weatherStatus={weatherStatus} weatherRecords={weatherRecords} />

        {/* 2-Column Grid: Anomaly Engine & AI Assistant */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <AnomalyPanel
            anomalies={anomalies}
            onExplainAnomaly={handleExplainAnomaly}
            onTriggerDetection={handleTriggerAnomalyDetection}
          />

          <AIAssistantWidget
            aiResponse={aiResponse}
            onAskAI={handleAskAI}
            isLoadingAI={isLoadingAI}
            aiStatus={aiStatus}
          />
        </div>
      </main>

      {/* CSV Ingestion Modal */}
      <CSVUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => { loadDashboardData(); loadForecast(); }}
      />
    </div>
  );
}
