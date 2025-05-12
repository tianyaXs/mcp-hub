export interface ServiceHealth {
  url: string;
  healthy: boolean;
  lastCheck: string;
  tools: string[]; // 添加工具列表字段
}

export interface ServiceHealthState {
  [key: string]: ServiceHealth;
}

export interface ServiceResponse {
  status: string;
  message?: string;
} 
