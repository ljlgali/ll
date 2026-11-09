@echo off
cd /d %~dp0
start "AnythingLLM-MCP" /B python server.py > server.log 2>&1
echo MCP 已启动: http://127.0.0.1:8000/mcp
