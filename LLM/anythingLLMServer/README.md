# anythingLLMServer —— 文档上传网页（任务 3）

单页网页，把本地文件上传到本机 AnythingLLM 的**第一个工作区**并自动触发向量化嵌入。

## 文件

| 文件 | 作用 |
|---|---|
| `upload.html` | 唯一页面：API Key 输入、服务地址输入、选文件、上传并嵌入 |

纯静态单文件（HTML + 内联 CSS/JS），不依赖任何前端框架与构建工具。

## 使用

1. 启动本机 AnythingLLM（默认 `http://localhost:3001`），并在 AnythingLLM 里创建好工作区
2. 从 AnythingLLM 设置页拿到 API Key
3. 双击 `upload.html`，或用任意静态服务器打开（`python -m http.server 8080` 后访问 `http://127.0.0.1:8080/upload.html`）
4. 填写 API Key → 点击「上传并嵌入」

## 实现要点

- **接口调用链**：`GET /api/v1/workspaces` 取第一个工作区 slug → `POST /api/v1/document/upload` 带 `file` 与 `addToWorkspaces`，服务端据此完成入库与嵌入
- **密钥不进源码**：API Key 与地址只存在浏览器 `localStorage`（首次手填），页面源码与仓库中不含任何明文 Key
- **错误可见**：获取工作区失败、无工作区、上传失败、网络异常分别给出不同提示，并显示上游响应片段

## 限制

- 只针对「第一个工作区」，不做多工作区选择（课程任务要求极简 MVP）
- 未做文件类型白名单，能否被 AnythingLLM 解析取决于其自身支持的格式
