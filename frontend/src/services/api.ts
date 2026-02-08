import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 60000, // 60 seconds for analysis requests
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>('/auth/login', { email, password }),
  getMe: () => api.get<User>('/auth/me'),
};

// DataSource API
export const datasourceApi = {
  list: () => api.get<DataSource[]>('/datasources'),
  create: (data: DataSourceCreate) => api.post<DataSource>('/datasources', data),
  update: (id: number, data: DataSourceUpdate) => api.put<DataSource>(`/datasources/${id}`, data),
  delete: (id: number) => api.delete(`/datasources/${id}`),
  test: (id: number) => api.post<DataSourceTestResponse>(`/datasources/${id}/test`),
};

// Analysis API
export const analysisApi = {
  create: (data: AnalysisRequest) => api.post<AnalysisResponse>('/analysis', data),
  list: (page: number = 1, pageSize: number = 20) =>
    api.get<AnalysisListItem[]>('/analysis', { params: { page, page_size: pageSize } }),
  get: (id: number) => api.get<AnalysisResponse>(`/analysis/${id}`),
  delete: (id: number) => api.delete(`/analysis/${id}`),
  cancel: (id: number) => api.post(`/analysis/${id}/cancel`),
  reanalyze: (id: number) => api.post(`/analysis/${id}/reanalyze`),
  
  // Streaming analysis - returns EventSource URL
  getStreamUrl: () => '/api/analysis/stream',
  getContinueUrl: (sessionId: number) => `/api/analysis/${sessionId}/continue`,
  getReanalyzeUrl: (sessionId: number) => `/api/analysis/${sessionId}/reanalyze`,
};

// Ticket API
export const ticketApi = {
  create: (data: TicketCreate) => api.post<Ticket>('/tickets', data),
  list: (params: TicketListParams) =>
    api.get<TicketListResponse>('/tickets', { params }),
  get: (ticketNo: string) => api.get<Ticket>(`/tickets/${ticketNo}`),
  update: (ticketNo: string, data: TicketUpdate) =>
    api.patch<Ticket>(`/tickets/${ticketNo}`, data),
};

// Types
export interface User {
  id: number;
  email: string;
  created_at: string;
  last_login_at: string | null;
}

export interface DataSource {
  id: number;
  name: string;
  type: 'elk' | 'loki' | 'prometheus';
  host: string;
  port: number;
  auth_token?: string;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface DataSourceCreate {
  name: string;
  type: 'elk' | 'loki' | 'prometheus';
  host: string;
  port: number;
  auth_token?: string;
  config?: Record<string, unknown>;
}

export interface DataSourceUpdate {
  name?: string;
  host?: string;
  port?: number;
  auth_token?: string;
  config?: Record<string, unknown>;
}

export interface DataSourceTestResponse {
  success: boolean;
  message: string;
  latency_ms?: number;
}

export interface AnalysisRequest {
  alert_content: string;
  time_range_minutes?: number;
  datasource_ids?: number[];
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  source?: string;
}

export interface ContextData {
  logs: LogEntry[];
  metrics: Record<string, unknown>[];
  collection_status: Record<string, string>;
}

export interface AnalysisResult {
  root_cause: string;
  evidence: string;
  category: string;
  temporary_solution: string;
  permanent_solution: string;
  confidence?: number;
}

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  stage?: string;
  data?: Record<string, unknown>;
}

export interface IntentResult {
  summary: string;
  alert_type: string;
  affected_system?: string;
  keywords: string[];
  suggested_metrics: string[];
}

export interface AnalysisResponse {
  id: number;
  user_id: number;
  alert_content: string;
  status: string;
  current_stage?: string;
  intent?: IntentResult;
  context_data?: ContextData;
  analysis_result?: AnalysisResult;
  messages: ConversationMessage[];
  created_at: string;
  updated_at?: string;
}

export interface AnalysisListItem {
  id: number;
  alert_content: string;
  status: string;
  created_at: string;
  has_result: boolean;
}

export interface StreamEvent {
  event: 'stage_start' | 'stage_progress' | 'stage_complete' | 'message' | 'error' | 'cancelled' | 'done';
  stage?: string;
  content?: string;
  data?: Record<string, unknown>;
  progress?: number;
}

export interface Ticket {
  ticket_no: string;
  session_id?: number;
  handler_id: number;
  title: string;
  root_cause?: string;
  ai_analysis?: string;
  level: 'P1' | 'P2' | 'P3';
  status: 'new' | 'processing' | 'closed';
  created_at: string;
  closed_at?: string;
}

export interface TicketCreate {
  session_id?: number;
  title: string;
  root_cause?: string;
  ai_analysis?: string;
  level?: 'P1' | 'P2' | 'P3';
}

export interface TicketUpdate {
  title?: string;
  root_cause?: string;
  level?: 'P1' | 'P2' | 'P3';
  status?: 'new' | 'processing' | 'closed';
}

export interface TicketListParams {
  page?: number;
  page_size?: number;
  status?: 'new' | 'processing' | 'closed';
  start_date?: string;
  end_date?: string;
}

export interface TicketListResponse {
  items: Ticket[];
  total: number;
  page: number;
  page_size: number;
}

// Test Data Types
export interface TestLog {
  id: string;
  timestamp: string;
  level: string;
  message: string;
  source: string;
  index: string;
}

export interface TestLogCreate {
  timestamp?: string;
  level: string;
  message: string;
  source?: string;
  index?: string;
}

export interface TestMetric {
  id: string;
  timestamp: string;
  name: string;
  labels: Record<string, string>;
  value: number;
  type: string;
}

export interface TestMetricCreate {
  timestamp?: string;
  name: string;
  labels?: Record<string, string>;
  value: number;
  type?: string;
}

export interface TestDataStats {
  logs_total: number;
  logs_by_level: Record<string, number>;
  metrics_total: number;
  metrics_by_name: Record<string, number>;
}

export interface TestDataSourceConfig {
  logs: {
    storage: string;
    note?: string;
  };
  prometheus: {
    host: string;
    port: number;
  };
}

// Test Data API
export const testDataApi = {
  // Logs
  listLogs: (query?: string, level?: string, limit?: number) =>
    api.get<TestLog[]>('/testdata/logs', { params: { query, level, limit } }),
  createLog: (data: TestLogCreate) => api.post<TestLog>('/testdata/logs', data),
  deleteLog: (id: string) => api.delete(`/testdata/logs/${id}`),
  clearLogs: () => api.delete('/testdata/logs'),

  // Metrics
  listMetrics: (name?: string, limit?: number) =>
    api.get<TestMetric[]>('/testdata/metrics', { params: { name, limit } }),
  createMetric: (data: TestMetricCreate) => api.post<TestMetric>('/testdata/metrics', data),
  deleteMetric: (id: string) => api.delete(`/testdata/metrics/${id}`),
  clearMetrics: () => api.delete('/testdata/metrics'),

  // General
  getStats: () => api.get<TestDataStats>('/testdata/stats'),
  regenerate: () => api.post<{ logs_count: number; metrics_count: number }>('/testdata/regenerate'),
  getConfig: () => api.get<TestDataSourceConfig>('/testdata/config'),
};

export default api;
