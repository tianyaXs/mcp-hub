import argparse
import json
 
import httpx
import uvicorn
from mcp.server import FastMCP, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
import random
import time
import requests
from fastapi.responses import JSONResponse
 
mcp = FastMCP("sse_WeatherServer")
 
OPENWEATHER_API_KEY = "8def2ecbdf06314b8a80c7df53d8810e"
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
USER_AGENT = "weather-app/1.0"
 
async def get_weather(city):
    """
    Get weather information from OpenWeather API
    :param city: City name (must be in English, e.g., 'beijing')
    :return: Weather data dictionary; if error occurs, returns dictionary with error information
    """
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "zh_cn",
    }
    headers = {"User-Agent": USER_AGENT}
 
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(OPENWEATHER_BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP Request Error: {e}"}
        except Exception as e:
            return {"error": f"An error occurred: {e}"}
 
def format_weather_data(data):
    """
    Format weather data
    :param data: Weather data dictionary
    :return: Formatted string; if error occurs, returns string with error information
    """
 
    # If input is a string, convert it to dictionary first
    if isinstance(data, str):
        data = json.loads(data)
 
    if "error" in data:
        return data["error"]
    weather = data["weather"][0]["description"]
    temperature = data["main"]["temp"]
    city = data["name"]
    country = data["sys"]["country"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"]
 
    return f"City: {city}, {country}\nWeather: {weather}\nTemperature: {temperature}°C\nHumidity: {humidity}%\nWind Speed: {wind}m/s"
 
def get_current_timestamp():
    return int(time.time())
 
@mcp.tool()
async def get_weather_tool(city: str):
    """
    Get weather information for a city
    :param city: City name (must be in English, e.g., 'beijing')
    :return: Weather data dictionary; if error occurs, returns dictionary with error information
    """
    weather_data = await get_weather(city)
    return format_weather_data(weather_data)
 
 
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
    parser.add_argument("--port", default=18150, type=int, help="MCP server port")
    args = parser.parse_args()
 
    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)
