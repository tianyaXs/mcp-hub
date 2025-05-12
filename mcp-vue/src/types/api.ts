// 查询请求参数类型
export interface QueryRequest {
  query: string;
  include_trace?: boolean; // 是否在响应中包含执行轨迹
  stream?: boolean; // 是否使用流式返回
}

// 查询响应类型
export interface QueryResponse {
  result: string;
  execution_trace?: ThinkingStep[]; // 执行轨迹
  thinking_step?: ThinkingStep; // 单个思考步骤（用于流式响应）
  is_final?: boolean; // 是否是最终结果（用于流式响应）
}

// 思考步骤类型
export interface ThinkingStep {
  type: 'thinking' | 'tool_call' | 'loading'; // 步骤类型：思考、工具调用或加载中
  content?: string;              // 思考内容
  tool?: string;                 // 工具名称
  result?: string;               // 工具调用结果
  status?: 'start' | 'complete'; // 步骤状态：开始或完成
  id?: string;                   // 用于标识步骤的唯一ID
  params?: any;                  // 工具调用参数，可以是任何JSON格式的数据
}

// 服务注册请求参数类型
export interface RegisterRequest {
  url: string;
  name: string;
}

// 服务注册响应类型
export interface RegisterResponse {
  status: string;
  message: string;
}

// 服务信息请求参数类型
export interface ServiceInfoRequest {
  url: string;
}

// 服务详情类型
export interface ServiceDetail {
  url: string;
  name: string;
  status: string;
  tools?: string[];
}

// 服务类型
export interface Service {
  url: string;
  name: string;
  tools?: string[];
}

// 服务健康状态类型
export interface ServiceHealth {
  healthy: boolean;
  lastCheck: string;
  url: string;
  tools: string[];  // 添加工具列表字段
}

// 服务信息响应类型
export interface ServiceInfoResponse {
  service: ServiceDetail;
}

// 服务健康状态响应类型
export interface HealthResponse {
  orchestrator_status: string;
  active_services: number;
  total_tools: number;
  pending_reconnection_count: number;
  connected_services_details: ServiceDetail[];
}

// MCP配置类型
export interface MCPConfig {
  mcpServers: {
    [key: string]: {
      url: string;
      env?: {
        [key: string]: string;
      };
    };
  };
  services?: {
    [key: string]: string;
  }
} 
