# MCP Client

## Introduction

This project is a FastAPI-based application acting as a central client and orchestrator for multiple MCP (Meta Call Protocol) compliant tool servers. It connects to these tool servers via SSE (Server-Sent Events), aggregates their available tools, and leverages a large language model (LLM) to understand user queries and intelligently invoke the appropriate tools. It also includes health checks and an automatic reconnection mechanism to enhance system robustness.

## Main Features

* **MCP Client:** Connects to MCP-compliant tool servers via SSE.
* **MCP Service Cluster Configuration:** This client service can be configured in a cluster mode to manage multiple tool servers.
* **Tool Aggregation:** Automatically discovers and aggregates tools from all connected servers.
* **LLM Integration:** Utilizes large language models to understand natural language queries.
* **Tool Invocation:** Routes tool execution requests to the correct server based on LLM decisions.
* **Health Checks:** Periodically checks the status of connected services via an HTTP `/health` endpoint.
* **Auto Disconnect & Reconnect:** Automatically disconnects unresponsive or timed-out services and periodically attempts to reconnect failed or disconnected ones.
* **API Interface:** Provides HTTP APIs for registering new MCP services, sending queries, and checking health.
* **Flexible Configuration:** Configured via a `pyproject.toml` file.

## Prerequisites

* Python 3.10+
* [uv](https://github.com/astral-sh/uv) (Recommended Python package installer and virtual environment manager)

## Installation & Setup

1.  **Clone the Repository**
    ```bash
    git clone git@gitee.com:callisto_atuo/mcp-agents.git
    cd mcp-agents
    ```

2.  **Create Virtual Environment**
    ```bash
    uv venv
    ```

3.  **Activate Virtual Environment**
    * Windows (Command Prompt/PowerShell):
        ```cmd
        .venv\Scripts\activate
        ```
    * Linux/macOS (Bash/Zsh):
        ```bash
        source .venv/bin/activate
        ```

4.  **Install Dependencies**
    ```bash
    uv pip install "mcp[cli]" fastapi uvicorn pydantic pandas openai zhipuai httpx toml
    ```
    *(Note: Consider creating a `requirements.txt` file for easier dependency management)*

## Configuration

Configuration is primarily done in the `pyproject.toml` file located in the project root (or parent directory, depending on the path settings in `config.py`).

The following sections need to be configured:

* **ZhipuAI Settings:**
    * `[tool.zhipu]`
        * `openai_api_key`: **Required**. Your API Key.
        * `model`: **(Can be set to other models supporting Tools)**. The model name to use (e.g., "glm-4", "glm-3-turbo").

* **Timing Settings (Optional):**
    * `[tool.timing]`
        * `heartbeat_interval_seconds`: Heartbeat check interval (seconds), default 60.
        * `heartbeat_timeout_seconds`: Service inactivity timeout (seconds), default 180.
        * `http_timeout_seconds`: Timeout for HTTP requests like health checks (seconds), default 10.
        * `reconnection_interval_seconds`: Interval for attempting to reconnect disconnected services (seconds), default 60.

**`pyproject.toml` Example Snippet:**

```toml
[tool.zhipu]
# Required: Replace with your actual ZhipuAI API Key
openai_api_key = "3b7b82927ac44f14bceb211a52f59031.****************"
# Required: Specify the model
model = "glm-4-plus"

[tool.timing]
# Optional: Customize timing parameters (unit: seconds)
# heartbeat_interval_seconds = 30
# heartbeat_timeout_seconds = 120
# reconnection_interval_seconds = 45
```

## Web Demo

The project includes a simple Gradio-based web interface for interacting with MCP services.

### Features

* **Weather Queries:** Get weather information for different cities
* **Vehicle Control:** Send vehicle control commands
* **Service Status Monitoring:** Real-time display of MCP service status
* **Example Commands:** Quick start with provided example commands

### Usage

#### 1. Start MCP Services

Before running the web demo, ensure all required services are running:

1. Vehicle Command Service (port 18080)
   ```bash
     mcp-server/vehicle_command/command_server.py
   ```

2. Weather Service (port 18081)
   ```bash
     mcp-server/weather/weather_server.py
   ```

3. MCP Client (FastAPI service, port 8000)
   ```bash
     mcp-client/main.py
   ```

#### 2. Launch Web Demo

After starting all services, run the web demo:

```bash
  mcp-client/demo/web_demo.py
```

The demo interface will be available at http://127.0.0.1:7860

#### Example Commands

* Weather queries: "What's the weather like in Beijing today?"
* Vehicle controls: "Turn on the AC", "Navigate to the nearest gas station"

## Project Structure
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
