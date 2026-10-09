# UPGRADE_PROMPT — Pet Hospital MCP 阶段二

本文件用于下一阶段开发。阶段二将在现有 `pet_hospital_mcp/` 模块上**新增多个 MCP 工具**，
继续暴露 Go 宠物医院 REST API 的其它能力，复用阶段一已建立的 `rest_client`、`errors`、`logging_config` 与统一错误结构。

## 范围

在阶段一 `list_pets` 之外，新增以下工具（工具名使用 snake_case）：

- `get_pet`            — `GET /api/v1/pets/{id}`
- `create_pet`         — `POST /api/v1/pets`
- `update_pet`         — `PUT /api/v1/pets/{id}`（全量更新）
- `patch_pet`          — `PATCH /api/v1/pets/{id}`（局部更新）
- `delete_pet`         — `DELETE /api/v1/pets/{id}`
- `search_pets`        — `GET /api/v1/pets/search?q=`
- `list_pet_records`   — `GET /api/v1/pets/{id}/records`
- `add_pet_record`     — `POST /api/v1/pets/{id}/records`
- `list_pet_charges`   — `GET /api/v1/pets/{id}/charges`
- `add_pet_charge`     — `POST /api/v1/pets/{id}/charges`
- `get_pet_summary`    — `GET /api/v1/pets/{id}/summary`
- `get_stats`          — `GET /api/v1/stats`

## 约束（继承阶段一）

- Python 3.11+；`mcp==2.0.0`；MCP 协议 `2026-07-28`；使用 `MCPServer`；无状态 Streamable HTTP。
- 不得使用或导入 `mcp.server.fastmcp.FastMCP`。
- 不得实现旧协议的 `initialize`、`Mcp-Session-Id`、会话存储/过期。
- 每个新工具一个文件，放在 `tools/`，调用 `rest_client` 新增对应方法。
- 输入/成功输出/错误输出均使用 Pydantic；错误输出沿用统一 `{error:{code,message,details}}`。
- 严格校验：`species`/`status`/`gender`/`chargeCategory` 等使用真实后端允许值（见 `/api/v1/meta`）；
  拒绝未知字段、`NaN`/`Infinity`、类型不正确输入。
- 后端调用必须有超时与有限重试；不得把 httpx/Pydantic/SDK/Python 堆栈原样暴露给客户端。
- 按 SDK 2.x 实际规定标记工具调用失败状态（`CallToolResult(is_error=True)`）。
- 日志含 `timestamp/tool_name/params/status/duration_ms`；`ownerPhone`/`ownerAddr`/`chipNo` 及其 snake_case 写法递归脱敏。
- 测试用 `httpx.MockTransport` 或 `respx`，禁止访问真实 Go 服务。

## 开始前

1. 阅读现有 `pet_hospital_mcp/src/pet_hospital_mcp/` 全部模块与 `tests/`。
2. 调用 `GET /api/v1/meta` 与 `GET /api/v1/endpoints` 确认每个接口的真实参数、字段与枚举。
3. 仅在 `tools/` 增加模块，在 `rest_client.py` 增加方法，在 `server.py` 注册工具。
4. 每个新工具至少补齐：正常调用、输入校验失败、上游 4xx/5xx、上游超时、上游非法响应 五类测试。
5. 运行 `pytest -q`，全部通过。

## 交付

1. 修改后的目录结构；
2. 实际修改/新增文件列表；
3. 测试命令与真实测试结果；
4. 如何启动与验证每个新工具（含无状态 HTTP 调用示例）；
5. 明确声明阶段一 `list_pets` 行为未变。
