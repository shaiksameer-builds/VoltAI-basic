import { describe, it, expect } from 'vitest';
import { VoltAIAPI } from '../services/api';

describe('VoltAI API Service Client', () => {
  it('defines API client methods', () => {
    expect(typeof VoltAIAPI.getHealth).toBe('function');
    expect(typeof VoltAIAPI.getSummary).toBe('function');
    expect(typeof VoltAIAPI.getDailyAnalytics).toBe('function');
    expect(typeof VoltAIAPI.getForecast).toBe('function');
    expect(typeof VoltAIAPI.getOptimizationSchedule).toBe('function');
    expect(typeof VoltAIAPI.getAnomalies).toBe('function');
    expect(typeof VoltAIAPI.getWeatherStatus).toBe('function');
    expect(typeof VoltAIAPI.getAIStatus).toBe('function');
    expect(typeof VoltAIAPI.askAI).toBe('function');
  });
});
