# MCP Client

## 介绍

本项目是一个基于 FastAPI 的应用程序，作为多个兼容 MCP（Meta Call Protocol）的工具服务器的中心客户端和编排器。它通过 SSE (Server-Sent Events) 连接到这些工具服务器，聚合它们提供的工具，利用大型语言模型来理解用户查询并智能地调用合适的工具。它还包含健康检查和自动重连机制，以提高系统的健壮性。



## 主要功能

* **MCP 客户端:** 通过 SSE 连接到兼容 MCP 的工具服务器。
* **MCP 服务集群化配置:** 该客户端服务可以配置为集群模式，以管理多个工具服务器。
* **工具聚合:** 自动发现并聚合来自所有已连接服务器的工具。
* **LLM 集成:** 利用大模型的理解自然语言查询。
* **工具调用:** 根据 LLM 的决策，将工具调用请求路由到正确的服务器。
* **健康检查:** 定期通过 HTTP `/health` 端点检查已连接服务的状态。
* **自动断开与重连:** 自动断开无响应或超时的服务，并定期尝试重新连接失败或断开的服务。
* **API 接口:** 提供用于注册新的Mcp服务、发送查询和检查健康的 HTTP API。
* **配置灵活:** 通过 `pyproject.toml` 文件进行配置。

## 环境准备

* Python 3.10+
* [uv](https://github.com/astral-sh/uv)

## 安装与设置

1.  **克隆仓库** (如果代码在仓库中)
    ```bash
    git clone git@gitee.com:callisto_atuo/mcp-agents.git
    cd mcp-agents
    ```

2.  **创建虚拟环境**
    ```bash
    uv venv
    ```

3.  **激活虚拟环境**
    * Windows (Command Prompt/PowerShell):
        ```cmd
        .venv\Scripts\activate
        ```
    * Linux/macOS (Bash/Zsh):
        ```bash
        source .venv/bin/activate
        ```

4.  **安装依赖**
        ```bash
        uv pip install "mcp[cli]" fastapi uvicorn pydantic pandas openai zhipuai httpx toml
        ```
## 配置

主要配置在项目根目录（或上一级目录，取决于 `config.py` 中的路径设置）的 `pyproject.toml` 文件中完成。

需要配置以下部分：

* **大语言模型 (LLM) 设置:**
    * `[tool.llm]`
        * `provider`: 模型提供商 (例如 "zhipuai", "deepseek", "openai_compatible")。
        * `api_key`: **必需**. 你的API Key。
        * `model`: **必需**. 要使用的模型名称 (例如, "glm-4", "glm-3-turbo", "deepseek-chat")。
        * `base_url`: **可选**. 自定义API终端点，对于"openai_compatible"提供商是必需的。

* **时间设置 (可选):**
    * `[tool.timing]`
        * `heartbeat_interval_seconds`: 心跳检查间隔（秒），默认 60。
        * `heartbeat_timeout_seconds`: 服务无响应超时时间（秒），默认 180。
        * `http_timeout_seconds`: HTTP 请求（如健康检查）的超时时间（秒），默认 10。
        * `reconnection_interval_seconds`: 尝试重连断开服务的间隔（秒），默认 60。

**`pyproject.toml` 示例片段:**

```toml
[tool.llm]
provider = "zhipuai"
api_key = "3b7b82927ac44f14bceb211a52f59031.****************"
model = "glm-4-plus"
#base_url = "https://api.zhipuai.com/v1"

# DeepSeek配置示例
# [tool.llm]
# provider = "deepseek"
# api_key = "your-deepseek-api-key"
# model = "deepseek-chat"
# base_url = "https://api.deepseek.com/v1"  # 可选

# 自定义OpenAI兼容API示例
# [tool.llm]
# provider = "openai_compatible"
# api_key = "your-api-key"
# model = "model-name"
# base_url = "https://your-api-endpoint.com/v1"  # 必需

[tool.timing]
# 可选：自定义时间参数 (单位：秒)
# heartbeat_interval_seconds = 30
# heartbeat_timeout_seconds = 120
# reconnection_interval_seconds = 45
```


## 运行应用程序
配置好 pyproject.toml 文件后，在激活的虚拟环境中运行 FastAPI 应用：

Bash

uv run main

## Docker 部署

项目可以使用 Docker Compose 部署，包含以下服务：

1. `mcp_local_services`: 提供后端工具服务（车辆控制和天气）
   - 端口: 18100-18101（车辆控制）, 18150-18151（天气）

2. `mcp_client`: 主要的 MCP 编排服务
   - 端口: 18200
   - 依赖: mcp_local_services

3. `web_demo`: 演示用的 Web 界面
   - 端口: 18300
   - 依赖: mcp_client

使用 Docker 部署的命令：

```bash
# 构建并启动所有服务
docker-compose up -d

# 检查所有服务是否正常运行
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 项目结构
```
mcp-client/
├── .venv/                   # Virtual environment directory
├── config.py                # Configuration loading logic
├── registry.py              # Service state registry class (ServiceRegistry)
├── orchestrator.py          # Core orchestration logic class (MCPOrchestrator)
├── main.py                  # FastAPI application entrypoint, API endpoint definitions
├── pyproject.toml           # Project configuration, dependencies (needs configuration)
├── requirements.txt         # (Optional) Dependency list file
└── README.md                # This file
