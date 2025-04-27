import asyncio
import json
import httpx
import gradio as gr
import sys
import os
import socket
from pathlib import Path

# 设置导入路径
current_dir = Path(__file__).parent  # demo目录
parent_dir = current_dir.parent  # mcp-client目录

# 首先清理可能重复的路径
if str(parent_dir) in sys.path:
    sys.path.remove(str(parent_dir))

# 添加mcp-client目录到路径
sys.path.append(str(parent_dir))

# 导入MCP配置处理模块 - 使用直接导入
from json_mcp import MCPConfig

# 检测运行环境
def is_running_in_docker():
    """检查是否在Docker容器中运行"""
    path = '/proc/self/cgroup'
    return os.path.exists('/.dockerenv') or (os.path.isfile(path) and any('docker' in line for line in open(path)))

# 获取服务主机名和端口
DOCKER_ENV = is_running_in_docker()
# 如果在Docker中运行，使用服务名称；否则使用localhost
MCP_HOST = os.environ.get("MCP_HOST", "mcp_client" if DOCKER_ENV else "127.0.0.1")
MCP_CLIENT_PORT = os.environ.get("MCP_CLIENT_PORT", "18200")

# 构建基础URL
MCP_CLIENT_BASE_URL = f"http://{MCP_HOST}:{MCP_CLIENT_PORT}"

# 初始化MCP配置处理器
mcp_config = MCPConfig(os.path.join(parent_dir, "mcp.json"))

# 适配不同环境的服务URL
def adapt_service_url(url):
    """根据当前环境适配服务URL
    注意：此函数用于自定义注册时的URL适配，不会修改mcp.json中的URL
    """
    # 现在此函数仅供自定义注册使用，不再自动转换mcp.json中的URL
    # 如果需要连接Docker本地服务，请使用"Docker环境下添加本地工具"按钮
    return url

async def query_mcp_service(query_text):
    """向MCP客户端发送查询请求并获取响应"""
    url = f"{MCP_CLIENT_BASE_URL}/query"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"query": query_text},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["result"]
            else:
                return f"错误: HTTP状态码 {response.status_code}\n{response.text}"
    except Exception as e:
        return f"发生异常: {e}"

def add_user_message(query, history):
    """将用户消息添加到历史记录中"""
    if not query.strip():
        return "", history
    
    history = history or []
    # 只添加用户消息，不添加响应
    history.append((query, None))
    return "", history

def get_bot_response(history):
    """获取机器人响应并更新历史记录"""
    if not history or history[-1][1] is not None:
        # 如果没有历史记录或最后一条记录已经有响应，则不执行任何操作
        return history
    
    # 获取用户最后一条消息
    user_message = history[-1][0]
    
    # 获取响应
    response = asyncio.run(query_mcp_service(user_message))
    
    # 更新历史记录的最后一项，添加响应
    history[-1] = (user_message, response)
    
    return history

async def check_service_health():
    """检查MCP服务的健康状态"""
    url = f"{MCP_CLIENT_BASE_URL}/health"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            if response.status_code == 200:
                health_info = response.json()
                print(f"health_info{health_info}")
                return health_info
            else:
                return {"error": f"HTTP状态码: {response.status_code}"}
    except Exception as e:
        return {"error": f"无法连接到MCP服务: {e}"}

async def get_service_info(service_url):
    """获取特定服务的详细信息，包括工具列表"""
    url = f"{MCP_CLIENT_BASE_URL}/service_info"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={"url": service_url}, timeout=5)
            if response.status_code == 200:
                service_info = response.json()
                return service_info
            else:
                print(f"获取服务信息失败: {service_url}, 状态码: {response.status_code}")
                return None
    except Exception as e:
        print(f"获取服务信息异常: {service_url}, 错误: {e}")
        return None

def check_services():
    """检查服务状态的包装函数，供Gradio使用"""
    health_info = asyncio.run(check_service_health())
    
    if "error" in health_info:
        return f"❌ 服务检查失败: {health_info['error']}"
    
    active_services = health_info.get("active_services", 0)
    total_tools = health_info.get("total_tools", 0)
    services_details = health_info.get("connected_services_details", [])
    
    status_text = f"✅ MCP服务运行中\n"
    status_text += f"🔌 已连接服务: {active_services}\n"
    status_text += f"🛠️ 可用工具: {total_tools}\n\n"
    
    if services_details:
        status_text += "服务详情:\n"
        for service in services_details:
            status = "✅" if service.get("status") == "healthy" else "❌"
            service_name = service.get("name", service.get("url", "未知服务"))
            
            # 获取服务详细信息包括工具列表
            service_info = asyncio.run(get_service_info(service.get("url")))
            
            if service_info and "service" in service_info:
                service_detail = service_info["service"]
                tools = service_detail.get("tools", [])
                tools_str = ", ".join(tools) if tools else "无"
                status_text += f"{status} {service_name} ({service.get('url')}) - 工具: {tools_str}\n"
            else:
                status_text += f"{status} {service_name} ({service.get('url')}) - 工具: 获取失败\n"
    
    return status_text

async def register_mcp_services():
    """从mcp.json注册服务到客户端"""
    services = mcp_config.load_services()
    
    if not services:
        return "❌ mcp.json中没有服务配置"
    
    results = []
    for service in services:
        service_url = service.get("url")
        # 不再自动转换URL，保持原样
        # service_url = adapt_service_url(service_url)
        service_name = service.get("name", "")
        
        if not service_url:
            results.append(f"❌ 服务配置错误: 缺少URL")
            continue
        
        # 检查是否有环境变量需要设置
        env_vars = service.get("env", {})
        if env_vars:
            env_info = ", ".join([f"{k}={v}" for k, v in env_vars.items()])
            print(f"服务 {service_name} 包含环境变量: {env_info}")
            
        try:
            async with httpx.AsyncClient() as client:
                print(f"正在注册服务: {service_name} ({service_url})")
                response = await client.post(
                    f"{MCP_CLIENT_BASE_URL}/register",
                    json={"url": service_url, "name": service_name},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 服务注册成功: {service_name} ({service_url}) - {result['message']}")
                    results.append(f"✅ 服务注册成功: {service_name} ({service_url})")
                else:
                    error_detail = response.text
                    print(f"❌ 服务注册失败: {service_name} ({service_url}) - HTTP {response.status_code}\n{error_detail}")
                    results.append(f"❌ 服务注册失败: {service_name} ({service_url}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 服务注册出错: {service_name} ({service_url}) - {e}")
            results.append(f"❌ 服务注册出错: {service_name} ({service_url}) - {e}")
    
    return "\n".join(results)

async def register_custom_service(url, name, api_key=None):
    """注册自定义MCP服务并保存到mcp.json"""
    if not url:
        return "❌ 请输入有效的服务URL"
    
    # 根据环境适配URL
    adapted_url = adapt_service_url(url)
    
    # 如果name为空，使用URL的一部分作为服务名称
    if not name:
        # 提取URL中的域名部分作为名称
        try:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            name = parsed_url.netloc.split(':')[0] or parsed_url.path.split('/')[1]
        except:
            name = url.split('/')[-2]
    
    # 构建服务配置
    service_config = {
        "name": name,
        "url": url  # 保存原始URL到配置文件，不保存adapted_url
    }
    
    # 如果提供了API密钥，添加到环境变量
    if api_key:
        service_config["env"] = {"API_KEY": api_key}
        
    try:
        async with httpx.AsyncClient() as client:
            print(f"正在注册自定义服务: {name} ({adapted_url})")
            response = await client.post(
                f"{MCP_CLIENT_BASE_URL}/register",
                json={"url": adapted_url, "name": name},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                # 保存到mcp.json
                if mcp_config.add_service(service_config):
                    api_key_info = "并配置API密钥" if api_key else ""
                    success_msg = f"✅ 服务注册成功{api_key_info}并保存到mcp.json: {name} ({url}) - {result['message']}"
                else:
                    success_msg = f"✅ 服务注册成功但保存到mcp.json失败: {name} ({url}) - {result['message']}"
                print(success_msg)
                return success_msg
            else:
                error_detail = response.text
                error_msg = f"❌ 服务注册失败: {name} ({url}) - HTTP {response.status_code}\n{error_detail}"
                print(error_msg)
                return error_msg
    except Exception as e:
        error_msg = f"❌ 服务注册出错: {name} ({url}) - {e}"
        print(error_msg)
        return error_msg

def update_services():
    """更新服务状态信息"""
    return check_services()

def show_mcp_json():
    """显示当前mcp.json内容"""
    config = mcp_config.load_config()
    
    if not config or not config.get("mcpServers"):
        return "mcp.json 文件为空或不存在。"
    
    json_content = json.dumps(config, ensure_ascii=False, indent=2)
    return json_content

def update_mcp_json(content):
    """更新mcp.json文件内容"""
    if not content.strip():
        return "❌ 内容不能为空"
    
    try:
        config = json.loads(content)
        
        # 验证基本结构
        if "mcpServers" not in config:
            return "❌ 配置缺少 mcpServers 字段"
        
        servers = config["mcpServers"]
        if not isinstance(servers, dict):
            return "❌ mcpServers 必须是一个对象，格式为: {\"server-name\": {\"url\": \"...\"}}"
        
        # 验证每个服务器配置
        for name, server in servers.items():
            if not isinstance(server, dict):
                return f"❌ 服务器 {name} 的配置必须是一个对象"
            if "url" not in server:
                return f"❌ 服务器 {name} 缺少 url 字段"
        
        # 保存配置
        if mcp_config.save_config(config):
            server_count = len(servers)
            return f"✅ mcp.json 更新成功，包含 {server_count} 个服务"
        else:
            return "❌ 保存 mcp.json 失败"
            
    except json.JSONDecodeError as e:
        return f"❌ JSON 解析错误: {e}"
    except Exception as e:
        return f"❌ 更新 mcp.json 出错: {e}"

def create_examples():
    """创建示例查询"""
    return [
        ["北京今天天气怎么样？"],
        ["打开空调"],
        ["导航到最近的加油站"],
        ["上海明天会下雨吗"],
        ["播放音乐"]
    ]

async def register_docker_local_services():
    """专门用于Docker环境下注册本地工具服务（vehicle-control和weather-service）"""
    # 预定义的Docker环境下的本地服务
    docker_services = [
        {
            "name": "vehicle-control",
            "url": "http://mcp_local_services:18100/sse"
        },
        {
            "name": "weather-service",
            "url": "http://mcp_local_services:18150/sse"
        }
    ]
    
    results = []
    
    # 检查是否在Docker环境中
    if not DOCKER_ENV:
        return "❌ 当前不在Docker环境中，此功能仅适用于Docker部署"
    
    for service in docker_services:
        service_url = service["url"]
        service_name = service["name"]
        
        try:
            async with httpx.AsyncClient() as client:
                print(f"正在注册Docker本地服务: {service_name} ({service_url})")
                response = await client.post(
                    f"{MCP_CLIENT_BASE_URL}/register",
                    json={"url": service_url, "name": service_name},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Docker本地服务注册成功: {service_name} ({service_url}) - {result['message']}")
                    results.append(f"✅ Docker本地服务注册成功: {service_name} ({service_url})")
                else:
                    error_detail = response.text
                    print(f"❌ Docker本地服务注册失败: {service_name} ({service_url}) - HTTP {response.status_code}\n{error_detail}")
                    results.append(f"❌ Docker本地服务注册失败: {service_name} ({service_url}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Docker本地服务注册出错: {service_name} ({service_url}) - {e}")
            results.append(f"❌ Docker本地服务注册出错: {service_name} ({service_url}) - {e}")
    
    return "\n".join(results)

# 创建Gradio界面
with gr.Blocks(title="MCP服务演示", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# MCP服务交互演示")
    gr.Markdown("这个演示界面展示了MCP服务的天气查询和车辆控制功能。确保已经启动了MCP服务和客户端。")
    
    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                height=500,
                label="对话记录"
            )
            with gr.Row():
                msg = gr.Textbox(
                    placeholder="输入您的问题或指令，如'北京天气怎么样'或'打开空调'",
                    label="输入",
                    scale=7
                )
                submit_btn = gr.Button("发送", variant="primary", scale=1)
            
            with gr.Accordion("示例命令", open=False):
                examples = gr.Examples(
                    examples=create_examples(),
                    inputs=[msg],
                )
                
        with gr.Column(scale=1):
            status_display = gr.Textbox(
                label="服务状态",
                value="正在检查服务状态...",
                lines=10,
                interactive=False
            )
            refresh_btn = gr.Button("刷新状态")
            register_btn = gr.Button("注册mcp.json服务")
            
            # 添加Docker本地工具注册按钮（仅在Docker环境下启用）
            docker_tools_btn = gr.Button(
                "Docker环境下添加本地工具", 
                variant="secondary",
                interactive=DOCKER_ENV  # 仅在Docker环境下可用
            )
            if not DOCKER_ENV:
                gr.Markdown("*注意：Docker环境下添加本地工具按钮仅在Docker部署中可用*")
            
            with gr.Accordion("自定义服务注册", open=True):
                service_url = gr.Textbox(
                    placeholder="输入服务URL，例如: http://127.0.0.1:8080/sse",
                    label="服务URL"
                )
                service_name = gr.Textbox(
                    placeholder="输入服务名称（可选）",
                    label="服务名称"
                )
                api_key = gr.Textbox(
                    placeholder="输入API密钥（可选）",
                    label="API密钥",
                    type="password"
                )
                custom_register_btn = gr.Button("注册自定义服务", variant="secondary")
            
            with gr.Accordion("mcp.json管理", open=True):
                mcp_json_content = gr.Textbox(
                    label="mcp.json内容",
                    lines=10,
                    value="正在加载...",
                    interactive=True
                )
                with gr.Row():
                    show_json_btn = gr.Button("查看mcp.json")
                    update_json_btn = gr.Button("更新mcp.json", variant="primary")
            
            with gr.Accordion("使用说明", open=True):
                gr.Markdown("""
                ## 使用指南
                
                ### 天气查询
                示例: "北京今天天气怎么样？", "上海明天会下雨吗"
                
                ### 车辆控制
                示例: "打开空调", "导航到最近的加油站", "播放音乐"
                
                ### 服务注册
                - 点击"注册mcp.json服务"按钮注册mcp.json中的服务
                - 点击"Docker环境下添加本地工具"按钮注册Docker环境下的本地服务（仅在Docker环境中有效）
                - 使用"自定义服务注册"面板注册其他MCP服务
                - 可选择为服务提供API密钥，将存储在环境变量中
                - 所有注册的服务会自动保存到mcp.json
                
                ### mcp.json格式
                ```json
                {
                  "mcpServers": {
                    "服务名称": {
                      "url": "http://服务地址:端口/sse",
                      "env": {
                        "API_KEY": "密钥值"
                      }
                    }
                  }
                }
                ```
                
                ### mcp.json管理
                - 点击"查看mcp.json"显示当前文件内容
                - 修改文本框中的内容并点击"更新mcp.json"保存更改
                
                ### 注意事项
                - 确保已启动MCP服务端 (vehicle_command和weather服务)
                - 确保已启动MCP客户端 (FastAPI服务)
                - 如果服务状态显示错误，请检查服务是否正在运行
                - Docker环境中使用"Docker环境下添加本地工具"按钮注册本地服务
                - 在本地环境中，请确保mcp.json中的URL可以正确访问
                """)
    
    # 事件处理
    # 使用回调链：先添加用户消息，然后获取机器人响应
    msg.submit(
        add_user_message, 
        inputs=[msg, chatbot], 
        outputs=[msg, chatbot]
    ).then(
        get_bot_response,
        inputs=[chatbot],
        outputs=[chatbot]
    )
    
    submit_btn.click(
        add_user_message, 
        inputs=[msg, chatbot], 
        outputs=[msg, chatbot]
    ).then(
        get_bot_response,
        inputs=[chatbot],
        outputs=[chatbot]
    )
    
    refresh_btn.click(update_services, inputs=[], outputs=[status_display])
    register_btn.click(lambda: asyncio.run(register_mcp_services()), inputs=[], outputs=[status_display])
    
    # Docker本地工具注册按钮事件
    docker_tools_btn.click(
        lambda: asyncio.run(register_docker_local_services()),
        inputs=[],
        outputs=[status_display]
    )
    
    # 自定义服务注册
    custom_register_btn.click(
        lambda url, name, key: asyncio.run(register_custom_service(url, name, key)),
        inputs=[service_url, service_name, api_key],
        outputs=[status_display]
    )
    
    # mcp.json管理
    show_json_btn.click(show_mcp_json, inputs=[], outputs=[mcp_json_content])
    update_json_btn.click(update_mcp_json, inputs=[mcp_json_content], outputs=[status_display])
    
    # 初始化服务状态
    demo.load(check_services, inputs=[], outputs=[status_display])
    # 初始化mcp.json内容
    demo.load(show_mcp_json, inputs=[], outputs=[mcp_json_content])
    # 自动注册服务
    demo.load(lambda: asyncio.run(register_mcp_services()), inputs=[], outputs=[])

if __name__ == "__main__":
    print("===== MCP服务网页演示 =====")
    print("确保已启动:")
    print("   - vehicle_command服务 (端口18100)")
    print("   - weather服务 (端口18150)")
    print("   - FastAPI客户端服务 (端口18200)")
    print(f"   - 当前服务主机: {MCP_HOST}")
    print(f"   - 运行环境: {'Docker' if DOCKER_ENV else '本地'}")
    print(f"   - mcp.json路径: {mcp_config.json_path}")
    
    # 启动Gradio界面
    demo.launch(share=False, server_name="0.0.0.0", server_port=18300)
