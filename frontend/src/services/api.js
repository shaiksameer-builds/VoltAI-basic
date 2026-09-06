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

      try {
        errorJson = JSON.parse(errorText);
      } catch (_) {}

      throw new Error(
        errorJson.detail || `HTTP ${response.status}: ${response.statusText}`
      );
    }

    return await response.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err.message);
    throw err;
  }
}

export const VoltAIAPI = {
  // Health
  async getHealth() {
    return request('/health');
  },

  // Analytics
  async getSummary(siteId, startTime = null, endTime = null) {
    const params = new URLSearchParams();

    if (siteId) params.set('site_id', siteId);
    if (startTime) params.set('start_time', startTime);
    if (endTime) params.set('end_time', endTime);

    const query = params.toString();
    return request(`/api/v1/analytics/summary${query ? `?${query}` : ''}`);
  },

  async getDailyAnalytics(siteId = 'site_001') {
    return request(
      `/api/v1/analytics/daily?site_id=${encodeURIComponent(siteId)}`
    );
  },

  async getSiteComparison() {
    return request('/api/v1/analytics/sites');
  },

  // Forecasting
  async getForecast(
    siteId = 'site_001',
    target = 'solar',
    horizonHours = 24
  ) {
    const params = new URLSearchParams({
      site_id: siteId,
      target,
      horizon_hours: String(horizonHours),
    });

    return request(`/forecast/generation?${params.toString()}`);
  },

  async getDemandForecast(
    siteId = 'site_001',
    horizonHours = 24
  ) {
    const params = new URLSearchParams({
      site_id: siteId,
      horizon_hours: String(horizonHours),
    });

    return request(`/forecast/demand?${params.toString()}`);
  },

  async getBalanceForecast(
    siteId = 'site_001',
    horizonHours = 24
  ) {
    const params = new URLSearchParams({
      site_id: siteId,
      horizon_hours: String(horizonHours),
    });

    return request(`/forecast/balance?${params.toString()}`);
  },

  // Battery Optimization
  async getOptimizationSchedule(siteId = 'site_001') {
    return request('/optimization/run', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
        horizon_hours: 24,
        battery_config: {
          battery_capacity_kwh: 100.0,
          min_soc_pct: 10.0,
          max_soc_pct: 90.0,
          max_charge_power_kw: 25.0,
          max_discharge_power_kw: 25.0,
          charge_efficiency: 0.95,
          discharge_efficiency: 0.95,
          initial_soc_pct: 50.0,
        },
        pricing_config: {
          import_price_per_kwh: 12.0,
          export_price_per_kwh: 4.0,
        },
        cycling_penalty_per_kwh: 0.001,
      }),
    });
  },

  // Anomaly Detection
  async getAnomalies(siteId = 'site_001') {
    return request(
      `/anomalies?site_id=${encodeURIComponent(siteId)}&limit=10`
    );
  },

  async triggerAnomalyDetection(siteId = 'site_001') {
    return request('/anomalies/detect', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
        z_threshold: 3.0,
        persist: true,
      }),
    });
  },

  // Weather
  async getWeatherStatus() {
    return request('/api/v1/weather/status');
  },

  async getWeatherRecords(siteId = 'site_001') {
    return request(
      `/api/v1/weather?site_id=${encodeURIComponent(siteId)}&limit=24`
    );
  },

  // AI Intelligence Layer
  async getAIStatus() {
    return request('/api/v1/ai/status');
  },

  async askAI(message, siteId = 'site_001') {
    return request('/api/v1/ai/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        site_id: siteId,
      }),
    });
  },

  async explainForecast(siteId = 'site_001', target = 'solar_generation') {
    return request('/api/v1/ai/explain/forecast', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
        target,
      }),
    });
  },

  async explainOptimization(siteId = 'site_001') {
    return request('/api/v1/ai/explain/optimization', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
      }),
    });
  },

  async explainAnomaly(siteId = 'site_001') {
    return request('/api/v1/ai/explain/anomaly', {
      method: 'POST',
      body: JSON.stringify({
        site_id: siteId,
      }),
    });
  },

  // CSV Upload
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
