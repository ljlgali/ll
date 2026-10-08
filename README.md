# LLM课程MCP开发项目
课程MCP开发MVP最小原型项目，共3项开发任务。

## 目录结构
LLM/
├── PetHospitalMCP        # 任务 1：宠物医院 MCP 服务（第一次任务）
├── AnythingLLMMCP        # 任务 2：AnythingLLM MCP 服务（第二次任务）
└── AnythingLLMserver    # 任务 3：AnythingLLM 文件上传网页（第三次任务）

## 任务1：PetHospitalMCP（第一次开发任务）
开发宠物医院MCP Server MVP版本。
- 对接PetHospitalServer后端REST API
- 仅实现MCP工具：`list_pets`，对应接口`GET /api/v1/pets`，实现宠物列表查询（分页、过滤、排序）
- 通信方式：Streamable HTTP，兼容新旧MCP协议（2026-07-28前后版本）
- 开发完成后生成MCP配置文件

## 任务2：AnythingLLMMCP（第二次开发任务）
开发对接AnythingLLM的MCP Server MVP版本。
- 调用本机AnythingLLM的API，使用自定义apikey
- 仅实现单一功能：提取第一个工作区里面的文件信息
- 通信方式：Streamable HTTP，兼容新旧MCP协议
- 开发完成后更新MCP配置文件

## 任务3：AnythingLLMWebPage（第三次开发任务）
开发简单网页，给AnythingLLM第一个工作区上传文档并自动向量化嵌入。
- 使用REST API：`POST /v1/document/upload`
- 功能：文档上传 + 向量化处理
- 极简设计，不做冗余开发，节约token

## 开发环境
- Python 3.10
- MCP协议SDK
- PetHospitalServer（宠物医院后端服务，提供REST接口）
- AnythingLLM本地服务

## 项目说明
全部项目均为MVP最小原型版本，不做冗余、过度设计，减少token消耗。
使用Git进行版本管理，分任务提交代码。
