import os
import re
import argparse
import logging
import toml
import time
import random
import uvicorn
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from llm_config import load_llm_config
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from fastapi.responses import JSONResponse

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file (optional but recommended)
load_dotenv() 

# --- Code Generation Agent Class ---
class CodeGenerationAgent:
    def __init__(self): # Default to a strong OpenAI model
        """
        Initializes the agent.
        :param api_key: API key for the LLM provider. Reads from OPENAI_API_KEY env var if None.
        :param model: The specific LLM model to use (e.g., "gpt-4", "gpt-3.5-turbo", potentially a DeepSeek model identifier if using their API).
        """
        # Initialize LLM client
        config_dir = os.path.dirname(__file__)
        pyproject_file = os.path.join(config_dir, "..","..", "pyproject.toml")
        with open(pyproject_file, "r", encoding="utf-8") as f:
            config = toml.load(f)
        # Load LLM configuration
        config = load_llm_config(config)
        self.model = config.model
        print(config.api_key)
        if config:
            self.llm_client = self.create_llm_client(config)
            if self.llm_client:
                logger.info(f"{config.provider.capitalize()} Client initialized.")
            else:
                logger.warning("LLM Client initialization failed.")
        else:
            logger.warning("LLM client configuration not found.")
        logger.info(f"Code Generation Agent initialized with model: {self.model}")

    def _call_llm(self, prompt):
        """
        Internal method to call the LLM API.
        Replace this method's content if using a different provider like DeepSeek.
        """
        logger.info("Sending request to LLM...")
        # try:
            # Example using OpenAI ChatCompletion API
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant specialized in generating Python code. Only output the raw Python code based on the user's request, enclosed in ```python markdown blocks."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, # Adjust creativity vs determinism
        )
        logger.info(response)
        response_text = response.choices[0].message.content
        return response_text
        # except APIError as e:
        #     logger.error(f"OpenAI API Error: {e}")
        #     return f"# OpenAI API Error: {e}"
        # except Exception as e:
        #     logger.error(f"An unexpected error occurred during LLM call: {e}", exc_info=True)
        #     return f"# Error during LLM call: {e}"

    def _extract_code(self, response_text):
        """
        Extracts Python code block from the LLM's response.
        """
        # Regex to find ```python ... ``` code blocks
        # It handles potential variations like ``` Python or just ```
        code_blocks = re.findall(r"```(?:python|Python)?\s*([\s\S]*?)\s*```", response_text)
        
        if code_blocks:
            logger.info("Python code block extracted successfully.")
            # Join blocks if there are multiple, though typically we expect one
            return "\n".join(block.strip() for block in code_blocks)
        else:
            # Fallback: If no markdown block found, maybe the model output raw code?
            # Be cautious with this, might return explanatory text.
            logger.warning("No ```python ... ``` block found in response. Returning raw response (may contain non-code text).")
            # Basic check: does it look like Python code? (very simplistic)
            if "def " in response_text or "import " in response_text or "class " in response_text:
                 return response_text.strip()
            else:
                 logger.error("Fallback failed: Raw response doesn't seem like Python code.")
                 return None # Indicate failure to extract code

    def generate_code(self, description):
        """
        Generates Python code based on a natural language description.
        :param description: Text description of the desired code functionality.
        :return: Generated code string or None if generation/extraction fails.
        """
        example_code = self.read_python_file("example.py")
        # example_markdown = self.convert_to_markdown(example_code)
        prompt = f"Generate Python code for the following task:\n\n{description}\n\nEnsure the code is complete, correct, and follows best practices. Only output the code itself. Please strictly follow the following template example to implement MCP service:\n\n{example_code}\n\n It is strictly prohibited to output any explanatory content, only code can be output"
        print(prompt)
        raw_response = self._call_llm(prompt)
        logger.info(raw_response)
        if raw_response and not raw_response.startswith("# Error"):
            extracted_code = self._extract_code(raw_response)
            return extracted_code
        else:
            logger.error(f"Failed to get valid response from LLM. Raw response: {raw_response}")
            return None
    def generate_file_name(self, description):
        """
        :param description: Requirement.
        :return: file_name.
        """
        example_code = self.read_python_file("example.py")
        # example_markdown = self.convert_to_markdown(example_code)
        prompt = f"Output a Python code file name based on the description:\n\n{description}\n\n, such as' example. py '. It is strictly prohibited to output any other explanatory information, only the file name should be output"
        print(prompt)
        raw_response = self._call_llm(prompt)
        return raw_response   

    def save_code_to_file(self, code, directory, filename):
        """
        Saves the generated code to a specified file.
        :param code: The code string to save.
        :param directory: The target directory path.
        :param filename: The desired filename (e.g., 'my_script.py'). '.py' extension added if missing.
        :return: The full path to the saved file or None on failure.
        """
        if not code:
            logger.error("Cannot save empty code.")
            return None
            
        if not filename.endswith(".py"):
            filename += ".py"
            logger.info(f"Added '.py' extension. Filename is now: {filename}")
        absolute_directory = os.path.abspath(directory)
        full_path = os.path.join(absolute_directory, filename).replace("\\", "/")
        # full_path = os.path.join(directory, filename).replace("\\", "/")

        try:
            # Create directory if it doesn't exist
            os.makedirs(directory, exist_ok=True) 
            
            # Write the code to the file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)
            logger.info(f"Code successfully saved to: {full_path}")
            return full_path
        except OSError as e:
            logger.error(f"Error creating directory '{directory}': {e}")
            return None
        except IOError as e:
            logger.error(f"Error writing code to file '{full_path}': {e}")
            return None
        except Exception as e:
             logger.error(f"An unexpected error occurred during file saving: {e}", exc_info=True)
             return None
    def create_llm_client(self,config: None) -> Optional[Any]:
        """Create LLM client instance based on provider configuration"""
        if not config.api_key:
            logger.warning(f"Missing {config.provider} API key, cannot initialize LLM client")
            return None
            
        try:
            if config.provider == "zhipuai":
                from zhipuai import ZhipuAI
                return ZhipuAI(api_key=config.api_key)
                
            elif config.provider == "deepseek":
                from openai import OpenAI
                return OpenAI(
                    api_key=config.api_key,
                    base_url=config.base_url or "https://api.deepseek.com/v1"
                )
                
            elif config.provider == "openai_compatible":
                from openai import OpenAI
                if not config.base_url:
                    logger.error("base_url is required for openai_compatible provider")
                    return None
                    
                return OpenAI(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
                
            else:
                logger.error(f"Unsupported LLM provider: {config.provider}")
                return None
                
        except ImportError as e:
            logger.error(f"Cannot import module required for {config.provider}: {e}")
            if config.provider == "zhipuai":
                logger.error("Please install zhipuai: pip install zhipuai")
            elif config.provider in ["deepseek", "openai_compatible"]:
                logger.error("Please install openai: pip install openai")
            return None
            
        except Exception as e:
            logger.error(f"Error initializing {config.provider} client: {e}", exc_info=True)
            return None 
    def read_python_file(self, file_path):
        """
        读取指定路径的 Python 文件内容。
        :param file_path: Python 文件路径（支持相对路径）
        :return: 文件内容字符串
        """
        # 获取当前模块文件所在目录
        module_dir = os.path.dirname(__file__)
        # 构造绝对路径
        absolute_path = os.path.join(module_dir, file_path)

        try:
            with open(absolute_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except FileNotFoundError:
            print(f"Error: File '{absolute_path}' not found.")
            return None
        except Exception as e:
            print(f"Error reading file: {e}")
            return None    


    def convert_to_markdown(self,python_code):
        """
        将 Python 代码转换为 Markdown 格式。
        :param python_code: Python 文件内容
        :return: 转换后的 Markdown 内容
        """
        markdown_content = []
        
        # 添加标题
        markdown_content.append("# Python Code Documentation\n")
        
        # 按行处理代码
        lines = python_code.splitlines()
        in_function = False
        for line in lines:
            stripped_line = line.strip()

            # 处理函数定义
            if stripped_line.startswith("def "):
                in_function = True
                markdown_content.append(f"## Function: `{stripped_line}`\n")
            
            # 处理类定义
            elif stripped_line.startswith("class "):
                in_function = True
                markdown_content.append(f"## Class: `{stripped_line}`\n")
            
            # 处理单行注释
            elif stripped_line.startswith("#"):
                comment = stripped_line.lstrip("#").strip()
                if comment:
                    markdown_content.append(f"> {comment}\n")
            
            # 处理多行注释（文档字符串）
            elif stripped_line.startswith('"""') or stripped_line.startswith("'''"):
                docstring_lines = []
                if stripped_line.endswith('"""') or stripped_line.endswith("'''"):
                    docstring_lines.append(stripped_line.strip('"""').strip("'''"))
                else:
                    docstring_lines.append(line)
                    while not (line.endswith('"""') or line.endswith("'''")):
                        line = next(lines)
                        docstring_lines.append(line)
                docstring = " ".join(docstring_lines).strip('"""').strip("'''")
                markdown_content.append(f"\n> **Docstring:** {docstring}\n")
            
            # 添加代码块
            elif stripped_line:
                if not in_function:
                    markdown_content.append("```python\n")
                markdown_content.append(f"{line}\n")
                if in_function and not stripped_line:
                    markdown_content.append("```\n")
                    in_function = False
        
        # 确保最后结束代码块
        if in_function:
            markdown_content.append("```\n")
        
        return "".join(markdown_content)    
    
mcp = FastMCP("code_agent_server.py")
@mcp.tool()
def create_code_file(query: str, file_name: str):
    """
    Generate relevant MCP Python code based on the query and save it to the specified directory
    :param query: input query
    :param file_name: input file_name
    :return: saved_path: output saved_path
    """
    # Instantiate the agent
    agent = CodeGenerationAgent()
    
    # Generate code
    logger.info("Requesting code generation...")
    generated_code = agent.generate_code(query)
    
    if generated_code:
        # Save code to file
        logger.info("Attempting to save generated code...")
        full_path = os.path.join("./mcp-server/", file_name.replace(".py", ""))
        saved_path = agent.save_code_to_file(generated_code, full_path, file_name)
        if saved_path:
            print(f"\n✅ Code generation successful!")
            print(f"   Saved to: {saved_path}")
            return saved_path
        else:
            return "\n❌ Code generation succeeded, but saving to file failed. Check logs."
    else:
        return "\n❌ Code generation failed. Check logs for details."        


async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "timestamp": int(time.time())}) 
def create_starlette_app(mcp_server: Server, *, debug: bool = False):
    """Create Starlette application that provides MCP service through SSE"""
    sse = SseServerTransport("/messages/")
    
    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
    
    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
            Route("/sse/health", endpoint=health_check, methods=["GET"])
        ],
    )    

if __name__ == "__main__":
    mcp_server = mcp._mcp_server

    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument("--host", default="0.0.0.0", help="MCP server host")
    parser.add_argument("--port", default=12386, type=int, help="MCP server port")
    args = parser.parse_args()
 
    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)