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

export interface AnalysisResponse {
  id: number;
  user_id: number;
  alert_content: string;
  context_data?: ContextData;
  analysis_result?: AnalysisResult;
  created_at: string;
}

export interface AnalysisListItem {
  id: number;
  alert_content: string;
  created_at: string;
  has_result: boolean;
}

export interface Ticket {
  ticket_no: string;
  session_id?: number;
  handler_id: number;
  title: string;
  root_cause?: string;
  level: 'P1' | 'P2' | 'P3';
  status: 'new' | 'processing' | 'closed';
  created_at: string;
  closed_at?: string;
}

export interface TicketCreate {
  session_id?: number;
  title: string;
  root_cause?: string;
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

export default api;
