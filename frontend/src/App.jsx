import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  const [latestTelemetry, setLatestTelemetry] = useState(null);

  // Loading states
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);
  const [isLoadingAI, setIsLoadingAI] = useState(false);

  // Live telemetry connection refs
  const websocketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const reconnectAttemptRef = useRef(0);

  // Fetch dashboard data
  const loadDashboardData = useCallback(async () => {
    try {
      VoltAIAPI.getHealth()
        .then((h) => setHealthStatus(h.status))
        .catch(() => setHealthStatus('degraded'));

      const [sum, daily] = await Promise.allSettled([
        VoltAIAPI.getSummary(selectedSite),
        VoltAIAPI.getDailyAnalytics(selectedSite),
      ]);

      if (sum.status === 'fulfilled') {
        setSummary(sum.value);
      }

      if (daily.status === 'fulfilled') {
        setDailyAnalytics(daily.value);
      }

      VoltAIAPI.getOptimizationSchedule(selectedSite)
        .then((opt) => setOptimizationData(opt))
        .catch((e) => console.warn('Opt fetch error:', e.message));

      VoltAIAPI.getAnomalies(selectedSite)
        .then((anom) => setAnomalies(Array.isArray(anom) ? anom : []))
        .catch((e) => console.warn('Anom fetch error:', e.message));

      VoltAIAPI.getWeatherStatus()
        .then((w) => setWeatherStatus(w))
        .catch(() => {});

      VoltAIAPI.getWeatherRecords(selectedSite)
        .then((w) => setWeatherRecords(w || []))
        .catch(() => {});

      VoltAIAPI.getAIStatus()
        .then((ai) => setAIStatus(ai))
        .catch(() => {});
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    }
  }, [selectedSite]);

  // Forecast fetch
  const loadForecast = useCallback(async () => {
    setIsLoadingForecast(true);

    try {
      const data = await VoltAIAPI.getForecast(
        selectedSite,
        forecastTarget,
        24
      );

      setForecastData(data);
    } catch (err) {
      console.warn('Forecast error:', err.message);
    } finally {
      setIsLoadingForecast(false);
    }
  }, [selectedSite, forecastTarget]);

  // Initial/site-change dashboard refresh
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Forecast refresh
  useEffect(() => {
    loadForecast();
  }, [loadForecast]);

  // Live telemetry WebSocket
  useEffect(() => {
    if (!isLiveMode) {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }

      reconnectAttemptRef.current = 0;
      setLatestTelemetry(null);

      return undefined;
    }

    let isEffectActive = true;

    const connectWebSocket = () => {
      if (!isEffectActive) {
        return;
      }

      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }

      const wsUrl =
        `ws://127.0.0.1:8000/api/v1/telemetry/stream/` +
        `${encodeURIComponent(selectedSite)}?interval_ms=1000`;

      console.info(`VoltAI telemetry connecting: ${wsUrl}`);

      const socket = new WebSocket(wsUrl);
      websocketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;
        console.info('VoltAI telemetry WebSocket connected');
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);

          if (payload.type === 'telemetry') {
            setLatestTelemetry(payload);
          }
        } catch (error) {
          console.warn('Invalid telemetry message:', error);
        }
      };

      socket.onerror = () => {
        console.warn('VoltAI telemetry WebSocket error');
      };

      socket.onclose = () => {
        if (websocketRef.current === socket) {
          websocketRef.current = null;
        }

        if (!isEffectActive) {
          return;
        }

        const attempt = reconnectAttemptRef.current;
        const delay = Math.min(1000 * 2 ** attempt, 10000);

        reconnectAttemptRef.current = attempt + 1;

        console.info(
          `VoltAI telemetry reconnecting in ${delay}ms ` +
          `(attempt ${attempt + 1})`
        );

        reconnectTimerRef.current = setTimeout(() => {
          if (isEffectActive) {
            connectWebSocket();
          }
        }, delay);
      };
    };

    connectWebSocket();

    return () => {
      isEffectActive = false;

      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    };
  }, [isLiveMode, selectedSite]);

  // AI actions
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
      const res = await VoltAIAPI.explainForecast(
        selectedSite,
        target === 'solar'
          ? 'solar_generation'
          : 'energy_consumption'
      );

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
      const resp =
        await VoltAIAPI.triggerAnomalyDetection(selectedSite);

      if (resp && resp.anomalies) {
        setAnomalies(resp.anomalies);
      }
    } catch (err) {
      console.error('Trigger anomaly error:', err);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-dark-900 text-slate-100">
      <Header
        selectedSite={selectedSite}
        setSelectedSite={setSelectedSite}
        timeRange={timeRange}
        setTimeRange={setTimeRange}
        onRefresh={() => {
          loadDashboardData();
          loadForecast();
        }}
        onOpenUpload={() => setIsUploadOpen(true)}
        healthStatus={healthStatus}
        isLiveMode={isLiveMode}
        setIsLiveMode={setIsLiveMode}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        <KPICards
          summary={summary}
          latestTelemetry={latestTelemetry}
        />

        <EnergyOverviewChart dailyData={dailyAnalytics} />

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

        <WeatherPanel
          weatherStatus={weatherStatus}
          weatherRecords={weatherRecords}
        />

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

      <CSVUploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          loadDashboardData();
          loadForecast();
        }}
      />
    </div>
  );
}
