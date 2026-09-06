/**
 * VoltAI Frontend API Service
 * 
 * Interacts with backend FastAPI endpoints.
 */

const API_BASE = '';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const errorText = await response.text();
      let errorJson = {};
      try { errorJson = JSON.parse(errorText); } catch (_) {}
      throw new Error(errorJson.detail || `HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err.message);
    throw err;
  }
}

export const VoltAIAPI = {
  // System Health
  async getHealth() {
    return request('/health');
  },

  // Analytics
  async getSummary(siteId, startTime = null, endTime = null) {
    const params = new URLSearchParams();
    if (siteId) params.append('site_id', siteId);
    if (startTime) params.append('start_time', startTime);
    if (endTime) params.append('end_time', endTime);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/v1/analytics/summary${query}`);
  },

  async getDailyAnalytics(siteId) {
    const params = new URLSearchParams();
    if (siteId) params.append('site_id', siteId);
    const query = params.toString() ? `?${params.toString()}` : '';
    return request(`/api/v1/analytics/daily${query}`);
  },

  async getSiteComparison() {
    return request('/api/v1/analytics/sites');
  },

  // Forecasting
  async getForecast(siteId = 'site_001', target = 'solar', horizonHours = 24) {
    return request('/api/v1/forecast/generate', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
        target: target,
        horizon_hours: horizonHours,
        persist: false,
      }),
    });
  },

  // Battery Optimization
  async getOptimizationSchedule(siteId = 'site_001') {
    return request('/optimization/schedule', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
        battery_config: { capacity_kwh: 100.0, max_charge_kw: 25.0, max_discharge_kw: 25.0 },
        grid_pricing: { peak_rate: 12.0, off_peak_rate: 4.0 },
      }),
    });
  },

  // Anomaly Detection
  async getAnomalies(siteId = 'site_001') {
    return request(`/anomalies?site_id=${encodeURIComponent(siteId)}&limit=10`);
  },

  async triggerAnomalyDetection(siteId = 'site_001') {
    return request('/anomalies/detect', {
      method: 'POST',
      body: JSON.stringify({ site_id: siteId, z_threshold: 3.0, persist: true }),
    });
  },

  // Weather Integration
  async getWeatherStatus() {
    return request('/api/v1/weather/status');
  },

  async getWeatherRecords(siteId = 'site_001') {
    return request(`/api/v1/weather?site_id=${encodeURIComponent(siteId)}&limit=24`);
  },

  // AI Intelligence Layer
  async getAIStatus() {
    return request('/api/v1/ai/status');
  },

  async askAI(query, siteId = 'site_001', intentOverride = null) {
    return request('/api/v1/ai/chat', {
      method: 'POST',
      body: JSON.stringify({
        query,
        site_id: siteId,
        intent_override: intentOverride,
      }),
    });
  },

  async explainForecast(siteId = 'site_001', target = 'solar_generation') {
    return request('/api/v1/ai/explain/forecast', {
      method: 'POST',
      body: JSON.stringify({ site_id: siteId, target }),
    });
  },

  async explainOptimization(siteId = 'site_001') {
    return request('/api/v1/ai/explain/optimization', {
      method: 'POST',
      body: JSON.stringify({ site_id: siteId }),
    });
  },

  async explainAnomaly(siteId = 'site_001') {
    return request('/api/v1/ai/explain/anomaly', {
      method: 'POST',
      body: JSON.stringify({ site_id: siteId }),
    });
  },

  // Ingestion CSV
  async uploadCSV(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/api/v1/energy/ingest/csv', {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`CSV Upload failed: ${response.statusText}`);
    }
    return response.json();
  },
};
