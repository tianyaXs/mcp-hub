FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Environment variables to optimize Python execution
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Use standard Python venv and pip to install dependencies (using a Chinese mirror for faster downloads)
RUN set -ex && \
    python -m venv /app/.venv && \
    . /app/.venv/bin/activate && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    # Install mcp[cli] with version constraint
    pip install --no-cache-dir "mcp[cli]>=1.6.0" && \
    # Install other dependencies
    pip install --no-cache-dir --verbose fastapi uvicorn pydantic pandas openai zhipuai httpx toml gradio && \
    # Simple import verification
    python -c "import mcp; print('MCP package successfully installed')"

# Create log directory and set permissions
RUN mkdir -p /var/log && chmod 777 /var/log

# Ensure virtual environment is in PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Expose required ports
# Vehicle control service ports
EXPOSE 18100 18101
# Weather service ports
EXPOSE 18150 18151
# API service port
EXPOSE 18200
# Web demo interface port
EXPOSE 18300

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "python" || exit 1
