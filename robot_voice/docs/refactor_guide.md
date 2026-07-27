# 语音服务器重构 - 配置驱动架构

## 🎯 架构升级

参考 **Kaiwu Agent** 的优雅设计，将原有的命令式服务器重构为**配置驱动 + 注册器模式**。

## 📦 核心组件

### 1. **注册器系统** (`robot_voice/utils/registry.py`)

类似于 `kaiwu_agent` 的 `MODELS`、`AGENTS` 注册器：

```python
from robot_voice.utils.registry import TTS_PLAYERS, FACE_SERVICES

# 注册TTS构建函数
@TTS_PLAYERS.register("adaptive")
def build_adaptive_tts(voice_id: str = "tiangong_v1", **kwargs):
    from robot_voice.tool import AdaptiveLBTTSPlayer
    return AdaptiveLBTTSPlayer(...)

# 使用注册器构建组件
tts_player = TTS_PLAYERS.build("adaptive", voice_id="tiangong_v2")
```

**优势：**
- ✅ 声明式注册，易于扩展
- ✅ 统一的构建接口
- ✅ 支持配置驱动：`TTS_PLAYERS.build_from_cfg({"type": "adaptive", "voice_id": "v2"})`

### 2. **配置模型** (`robot_voice/utils/config_model.py`)

使用 **Pydantic** 定义配置结构，支持验证和类型检查：

```python
class ServerConfig(BaseModel):
    version: str = "0.0.1"
    port: int = 8765
    tts: TTSConfig
    asr: ASRConfig
    face: FaceConfig
    ...
```

**优势：**
- ✅ 类型安全，自动验证
- ✅ 清晰的配置结构
- ✅ 支持版本校验

### 3. **服务管理器** (`server_xf_voice_config.py`)

统一管理所有服务的生命周期：

```python
manager = ServiceManager()
manager.register(face_listener, "人脸监听服务")
manager.register(xf_listener, "讯飞语音监听服务")

manager.start_all()  # 批量启动
manager.stop_all()   # 批量停止
```

**优势：**
- ✅ 统一的启动/停止逻辑
- ✅ 自动错误处理
- ✅ 优雅的日志输出

### 4. **事件桥接器** (`robot_voice/utils/event_bridge.py`)

优雅的事件连接方式：

```python
# 连接人脸事件到WatchIntro
connect_face_to_watch_intro(face_callback, watch_intro_listener)

# 连接语音事件到WatchIntro
connect_voice_to_watch_intro(xf_callback, watch_intro_listener)
```

**优势：**
- ✅ 装饰器模式，非侵入式
- ✅ 自动错误隔离
- ✅ 可追踪连接关系

## 📝 使用方式

### 方式1：YAML配置文件（推荐）

1. 创建配置文件 `my_config.yaml`：

```yaml
version: "0.0.1"
port: 8765

tts:
  enabled: true
  type: "adaptive"
  voice_id: "tiangong_v1"

asr:
  enabled: true
  mode: "OnlineASR"
  wake_word: "天工天工"

face:
  enabled: true
  face_ip: "10.42.0.127"
  face_port: 9090

watch_intro:
  enabled: true
  watching_delay: 30
```

2. 启动服务器：

```bash
python server_xf_voice_config.py -c my_config.yaml
```

### 方式2：命令行参数（兼容旧方式）

```bash
python server_xf_voice_config.py \
    --port 8765 \
    --tts adaptive \
    --voice tiangong_v1 \
    --enable-face \
    --watching-delay 30
```

### 方式3：原始版本（保持兼容）

```bash
python server_xf_voice_re.py \
    --port 8765 \
    -t adaptive \
    -v tiangong_v1 \
    --enable-face
```

## 📊 代码对比

### 原版 vs 新版

| 指标 | 原版 (`server_xf_voice_re.py`) | 新版 (`server_xf_voice_config.py`) |
|------|-------------------------------|-----------------------------------|
| 代码行数 | 227 行 | 主文件 220 行 + 模块化代码 |
| TTS初始化 | 44 行 if-elif | 注册器 + 5行调用 |
| 服务启动 | 30+ 行重复代码 | ServiceManager 统一管理 |
| 配置方式 | 仅命令行参数 | YAML + 命令行 + Pydantic |
| 可扩展性 | 修改主文件 | 注册新组件即可 |
| 类型安全 | 无 | Pydantic 验证 |

## 🚀 扩展新服务

### 添加新的TTS类型

```python
# 在 service_factory.py 中添加
@TTS_PLAYERS.register("new_tts")
def build_new_tts(param1, param2, **kwargs):
    from some_module import NewTTSPlayer
    return NewTTSPlayer(param1=param1, param2=param2)
```

### 添加新的人脸服务

```python
@FACE_SERVICES.register("opencv")
def build_opencv_face(voice_server, **kwargs):
    from robot_voice.listener.opencv_face import OpenCVFace
    return OpenCVFace(voice_server=voice_server)
```

## 🎨 架构优势总结

1. **配置驱动**：一个YAML文件控制所有服务
2. **注册器模式**：声明式组件注册，易于扩展
3. **类型安全**：Pydantic自动验证配置
4. **统一管理**：ServiceManager管理服务生命周期
5. **优雅连接**：EventBridge实现跨模态事件桥接
6. **向后兼容**：保留命令行参数，平滑迁移

## 📚 参考

本重构参考了 **Kaiwu Agent** 的以下设计模式：
- 注册器模式 (`MODELS`, `AGENTS`, `MSG_CLIENTS`)
- 配置驱动 (`AppConfig`, `parse_args_and_cfg`)
- 占位符替换 (`resolve_placeholders`)
- 统一的构建接口 (`build_from_cfg`)

## 🔧 迁移指南

从旧版本迁移到新版本：

1. **直接替换**：`server_xf_voice_config.py` 完全兼容旧参数
2. **创建配置文件**：复制 `config_example.yaml` 并修改
3. **逐步迁移**：先用命令行参数，再切换到YAML
4. **保留原版**：`server_xf_voice_re.py` 保持不变，可随时回退
