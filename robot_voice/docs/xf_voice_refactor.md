# 讯飞语音模块重构说明

## 概述

讯飞语音(xf_voice)模块已重构为新的Listener/Callback架构，不再依赖`msg_processor`，提供更清晰的职责分离。

## 新增文件

### 核心文件

1. **`robot_voice/listener/xf_voice/xf_voice_callback_re.py`**
   - `XFVoiceCallback`: 基础语音回调类
   - `XFNLPCallback`: NLP模式回调
   - `XFLUOYUCallback`: LUOYU模式回调（落域技能）
   - `XFOnlineASRCallback`: 在线ASR回调
   - `XFOfflineASRCallback`: 离线ASR回调

2. **`robot_voice/listener/xf_voice/xf_voice_listener_re.py`**
   - `XFVoiceListener`: 基础语音监听器
   - `XFNLPListener`: NLP模式监听器
   - `XFLUOYUListener`: LUOYU模式监听器
   - `XFOnlineASRListener`: 在线ASR监听器
   - `XFOfflineASRListener`: 离线ASR监听器
   - `create_xf_voice_system()`: 便捷创建函数

3. **`server_xf_voice_re.py`**
   - 新的服务器脚本，使用重构后的架构
   - 支持人脸识别集成（使用新架构的face_listener_re）
   - 不依赖msg_processor

4. **`examples/xf_voice_usage.py`**
   - 5种使用示例
   - 包含完整的`XFVoiceTriggerManager`管理器类

## 架构说明

### Listener职责
- 监听AIUI事件流
- 处理设备状态、唤醒、VAD、识别结果等事件
- 解析不同模式的结果（iat、nlp、skill等）
- 调用callback的相应方法

### Callback职责
- 缓存语音状态（继承自BaseCallback）
- 处理业务逻辑（唤醒、指令）
- 通过voice_server广播事件

## 使用方式

### 方式1：便捷函数（推荐）

```python
from robot_voice.listener.xf_voice.xf_voice_listener_re import create_xf_voice_system
from robot_voice.utils.voice_server import VoiceSocketServer

voice_server = VoiceSocketServer(port=8765)

listener, callback = create_xf_voice_system(
    mode="OnlineASR",  # 或 "NLP", "LUOYU", "OfflineASR"
    voice_server=voice_server,
    wake_word="天工天工"
)

listener.start()
# ... 使用
listener.stop()
```

### 方式2：手动创建

```python
from robot_voice.listener.xf_voice.xf_voice_listener_re import XFOnlineASRListener
from robot_voice.listener.xf_voice.xf_voice_callback_re import XFOnlineASRCallback

callback = XFOnlineASRCallback(voice_server=voice_server)
listener = XFOnlineASRListener(callback=callback)
```

### 方式3：使用TriggerLayerManager

```python
from examples.xf_voice_usage import XFVoiceTriggerManager

manager = XFVoiceTriggerManager(
    mode="LUOYU",
    enable_face=True,
    enable_watching=True
)

manager.initialize()
manager.start()  # 阻塞
manager.stop()
```

## 支持的模式

| 模式 | 说明 | Listener类 | Callback类 |
|------|------|-----------|-----------|
| NLP | 需要写句式的意图识别 | XFNLPListener | XFNLPCallback |
| LUOYU | 落域技能，自动意图识别 | XFLUOYUListener | XFLUOYUCallback |
| OnlineASR | 仅在线语音识别 | XFOnlineASRListener | XFOnlineASRCallback |
| OfflineASR | 仅离线语音识别 | XFOfflineASRListener | XFOfflineASRCallback |

## 与其他模块集成

### 与人脸识别集成

```python
# 在XFVoiceTriggerManager中启用
manager = XFVoiceTriggerManager(
    mode="OnlineASR",
    enable_face=True,
    face_ip="10.42.0.127",
    face_port=9090
)
```

### 与Watching跨模态集成

```python
manager = XFVoiceTriggerManager(
    mode="OnlineASR",
    enable_face=True,
    enable_watching=True,
    watching_delay=3  # 3秒无语音发送watching事件
)
```

## 运行新服务器

```bash
# 使用新架构的服务器
python server_xf_voice_re.py --port 8765 --enable-face --watching-delay 3
```

## 迁移指南

### 从旧架构迁移

**旧代码：**
```python
from robot_voice.listener.xf_voice import XFOnlineASRListener
from robot_voice.processor.msg_processor import BaseMsgProcessor

msg_processor = BaseMsgProcessor(voice_server)
listener = XFOnlineASRListener(mode="OnlineASR", msg_processor=msg_processor)
```

**新代码：**
```python
from robot_voice.listener.xf_voice.xf_voice_listener_re import create_xf_voice_system

listener, callback = create_xf_voice_system(
    mode="OnlineASR",
    voice_server=voice_server
)
```

## 事件流程

```
讯飞3588 
  ↓ (TCP)
AIUIClient
  ↓ (OnEvent)
XFVoiceListener
  ↓ (_process_result)
XFVoiceCallback
  ↓ (on_voice_instruction)
VoiceSocketServer
  ↓ (WebSocket)
客户端
```

## 注意事项

1. **不依赖msg_processor**: 新架构完全独立，不需要`msg_processor`
2. **状态缓存**: Callback继承自`BaseCallback`，自动提供状态缓存功能
3. **模态类型**: 语音属于`ModalityType.AUDITORY`
4. **向后兼容**: 旧的listener/callback仍然可用，不影响现有代码

## 完整示例

参见 `examples/xf_voice_usage.py` 中的5个完整示例。
