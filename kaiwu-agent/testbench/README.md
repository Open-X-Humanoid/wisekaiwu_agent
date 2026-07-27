# testbench

用于在没有真实硬件或云服务的情况下运行 kaiwu-agent 的开发测试台。

## 目录结构

```
testbench/
├── fake_servers/
│   ├── robot_actions_mcp.py    # 统一的 MCP 服务（24 个机器人工具，支持场景切换）
│   ├── mock_tool_results.py    # 20 个预置场景 + 夹具数据
│   ├── huisikaiwu_recv.py      # 模拟慧思开物云接收端 (FastAPI)
│   └── huisikaiwu_send.py      # 模拟慧思开物云发送端 (HTTP client)
└── monitors/                   # WebSocket 日志查看器 + GUI 监控
```

这些工具**不属于**生产运行时。它们提供一个模拟环境，使开发者可以在本地运行和调试
brain agent，而无需连接真实的机器人控制层或慧思开物云。

## 机器人操作模拟 MCP 服务

`robot_actions_mcp.py` 暴露 **24 个工具**，涵盖 home_living（空间记忆 +
抓取/放置/交接）和 box_carry（initialize/scan/pick_up_box/put_box_to_table）
两类工作流。所有工具调用都通过 `MockResultProvider` 路由，使测试可以完全控制返回值。


### 快速开始

```bash
# Default: happy_path_fetch scenario
PYTHONPATH=. python3 testbench/fake_servers/robot_actions_mcp.py
```

## 慧思开物云 Mock

- `huisikaiwu_recv.py`：接收 `/v1/api/chat/doResult` 回调的 FastAPI 服务
- `huisikaiwu_send.py`：向 agent 的 `huisikaiwu` 通道发送指令的 HTTP 客户端

在 `kaiwu.yaml -> gateway.channels.huisikaiwu` 启用时使用。

## 语音通道 Mock

进行语音通道测试时，将 `voice_socket.uri` 指向 `robot_voice` 仓库的
`fake_server.py`（命令行输入 → WS 广播）。语音 mock 位于同级的 `robot_voice`
仓库中，而非本 testbench。

如需一次性的 WS 推送（无交互式命令行），参见 e2e 测试期间创建的
`/tmp/kaiwu_test/mini_voice_server.py`。
