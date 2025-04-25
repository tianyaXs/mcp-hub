import asyncio
import json
import httpx
import gradio as gr
import sys
import os
from pathlib import Path

# 添加上层目录到Python路径，以便导入mcp-client模块
sys.path.append(str(Path(__file__).parent.parent.parent))

async def query_mcp_service(query_text):
    """向MCP客户端发送查询请求并获取响应"""
    url = "http://127.0.0.1:8000/query"
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

def process_query(query, history):
    """处理用户查询并调用MCP服务"""
    if not query.strip():
        return "", history
    
    history = history or []
    response = asyncio.run(query_mcp_service(query))
    history.append((query, response))
    return "", history  # 返回空字符串作为消息输入框的新值

async def check_service_health():
    """检查MCP服务的健康状态"""
    url = "http://127.0.0.1:8000/health"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            if response.status_code == 200:
                health_info = response.json()
                return health_info
            else:
                return {"error": f"HTTP状态码: {response.status_code}"}
    except Exception as e:
        return {"error": f"无法连接到MCP服务: {e}"}

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
            status_text += f"{status} {service.get('url')} - 工具: {', '.join(service.get('tools', []))}\n"
    
    return status_text

async def register_mcp_services():
    """注册MCP服务到客户端"""
    services = [
        "http://localhost:18080/sse",  # vehicle_command服务
        "http://localhost:18081/sse"   # weather服务
    ]
    
    results = []
    for service_url in services:
        try:
            async with httpx.AsyncClient() as client:
                print(f"正在注册服务: {service_url}")
                response = await client.post(
                    "http://127.0.0.1:8000/register",
                    json={"url": service_url},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 服务注册成功: {service_url} - {result['message']}")
                    results.append(f"✅ 服务注册成功: {service_url}")
                else:
                    error_detail = response.text
                    print(f"❌ 服务注册失败: {service_url} - HTTP {response.status_code}\n{error_detail}")
                    results.append(f"❌ 服务注册失败: {service_url} - HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ 服务注册出错: {service_url} - {e}")
            results.append(f"❌ 服务注册出错: {service_url} - {e}")
    
    return "\n".join(results)

def update_services():
    """更新服务状态信息"""
    return check_services()

def create_examples():
    """创建示例查询"""
    return [
        ["北京今天天气怎么样？"],
        ["打开空调"],
        ["导航到最近的加油站"],
        ["上海明天会下雨吗"],
        ["播放音乐"]
    ]

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
            register_btn = gr.Button("注册服务")
            
            with gr.Accordion("使用说明", open=True):
                gr.Markdown("""
                ## 使用指南
                
                ### 天气查询
                示例: "北京今天天气怎么样？", "上海明天会下雨吗"
                
                ### 车辆控制
                示例: "打开空调", "导航到最近的加油站", "播放音乐"
                
                ### 注意事项
                - 确保已启动MCP服务端 (vehicle_command和weather服务)
                - 确保已启动MCP客户端 (FastAPI服务)
                - 如果服务状态显示错误，请检查服务是否正在运行
                - 如果服务未连接，点击"注册服务"按钮进行注册
                """)
    
    # 事件处理
    msg.submit(process_query, inputs=[msg, chatbot], outputs=[msg, chatbot])
    submit_btn.click(process_query, inputs=[msg, chatbot], outputs=[msg, chatbot])
    refresh_btn.click(update_services, inputs=[], outputs=[status_display])
    register_btn.click(lambda: asyncio.run(register_mcp_services()), inputs=[], outputs=[status_display])
    
    # 初始化服务状态
    demo.load(check_services, inputs=[], outputs=[status_display])
    # 自动注册服务
    demo.load(lambda: asyncio.run(register_mcp_services()), inputs=[], outputs=[])

if __name__ == "__main__":
    print("===== MCP服务网页演示 =====")
    print("确保已启动:")
    print("   - vehicle_command服务 (端口18080)")
    print("   - weather服务 (端口18081)")
    print("   - FastAPI客户端服务 (端口8000)")
    
    # 启动Gradio界面
    demo.launch(share=False, server_name="0.0.0.0", server_port=7860)
