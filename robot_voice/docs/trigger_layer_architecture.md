# 触发层架构设计说明

## 概述

本文档说明重构后的触发层（Trigger Layer）架构设计，包括单模态和跨模态两种处理方式。

## 架构层次

```
物理层 (Physical Layer)
    ↓
感知层 (Perception Layer) - 连续数据流
    ↓
触发层 (Trigger Layer) - 离散状态流 + 事件触发
    ↓
思考层 (Thinking Layer) - 业务逻辑处理
```

## 单模态处理链路

### 组件

1. **BaseListener** - 单模态监听器基类
   - 职责：监听连续流，检测状态变化
   - 示例：`FaceStreamListener` (视觉模态)

2. **BaseCallback** - 单模态回调处理器基类
   - 职责：业务逻辑处理、状态缓存、事件发送
   - 示例：`BaiduFaceCallback` (人脸识别+缓存)

### 数据流

```
传感器 → BaseListener → BaseCallback → 思考层
         (监听+触发)    (处理+缓存+发送)
```

### 示例：人脸检测

```python
# 1. Listener 监听视频流，检测人脸ID变化
face_listener = FaceStreamListener(device_ip="10.42.0.127")

# 2. Callback 处理人脸识别、缓存状态
face_callback = BaiduFaceCallback(
    voice_server=server,
    enable_face_recognition=True
)

# 3. 连接 Listener 和 Callback
face_listener.on_state_change = face_callback.on_state_change
face_listener.on_state_disappeared = face_callback.on_state_disappeared

# 4. 启动监听
face_listener.start()
```

## 跨模态处理链路

### 组件

1. **MultiModalListener** - 跨模态监听器基类
   - 职责：订阅多个单模态状态、维护跨模态缓存、通知Callback
   - 示例：`WatchIntroListener` (视觉+听觉)

2. **MultiModalCallback** - 跨模态回调处理器基类
   - 职责：融合判断、事件构建、事件发送
   - 示例：`WatchIntroCallback` (watching检测)

### 关键设计决策：为什么需要 MultiModalCallback？

**原因分析：**

1. **保持架构一致性**
   - 单模态：Listener(监听) + Callback(处理+发送)
   - 跨模态：MultiModalListener(监听+缓存) + MultiModalCallback(融合+发送)

2. **职责分离**
   - MultiModalListener：订阅状态、维护缓存、时间同步
   - MultiModalCallback：融合判断、业务逻辑、事件发送

3. **便于测试和扩展**
   - 可以独立测试融合逻辑
   - 可以为同一Listener编写多个不同的Callback

### 数据流

```
单模态Callback状态 ──┐
                    ├─→ MultiModalListener → MultiModalCallback → 思考层
单模态Callback状态 ──┘   (监听+缓存)         (融合+判断+发送)
```

### 示例：Watching检测

```python
# 1. 创建跨模态系统
watch_listener, watch_callback = create_watch_intro_system(
    voice_server=server,
    watching_delay=5  # 5秒无语音触发
)

# 2. 连接 Listener 和 Callback
watch_listener.set_state_update_callback(watch_callback.on_multimodal_state_update)

# 3. 订阅单模态Callback的状态
def on_face_detected(face_index, face_image, face_info):
    # 人脸Callback检测到新人脸时，通知跨模态Listener
    face_data = {
        "face_index": face_index,
        "user_name": "...",  # 来自识别结果
        ...
    }
    watch_listener.on_face_detected(face_data)

def on_instruction_received(instruction_data):
    # 语音Callback收到指令时，通知跨模态Listener
    watch_listener.on_instruction_received(instruction_data)

face_callback.on_state_change = on_face_detected
voice_callback.on_instruction = on_instruction_received

# 4. 启动
watch_listener.start()
```

## 核心类说明

### BaseListener

```python
class BaseListener(ABC):
    """单模态监听器基类"""
    
    # 核心方法
    def start(self): ...           # 启动监听
    def stop(self): ...            # 停止监听
    def _connect(self): ...        # 连接数据源
    def _listen_loop(self): ...    # 监听循环
    
    # 事件通知
    def _notify_state_change(self, *args): ...
    def _notify_state_disappeared(self, *args): ...
```

### BaseCallback

```python
class BaseCallback(ABC):
    """单模态回调处理器基类"""
    
    # 核心方法
    def on_state_change(self, *args): ...       # 处理状态变化
    def on_state_disappeared(self, *args): ...  # 处理状态消失
    
    # 状态管理
    def cache_state(self, state_id, data): ...       # 缓存状态
    def get_latest_state(self): ...                   # 获取最新状态
    def clear_state_cache(self, state_id=None): ...  # 清除缓存
    
    # 事件发送
    def _send_event(self, event_data): ...       # 发送事件
    def _deliver_event(self, event_data): ...    # 实际传递（子类重写）
```

### MultiModalListener

```python
class MultiModalListener(ABC):
    """跨模态监听器基类"""
    
    # 核心方法
    def start(self): ...                        # 启动
    def stop(self): ...                         # 停止
    def set_state_update_callback(self, callback): ...  # 设置回调
    
    # 跨模态状态管理
    def update_modality_state(self, modality, state_id, data): ...  # 更新状态
    def get_modality_state(self, modality, state_id=None): ...      # 获取状态
    def has_modality_state(self, modality): ...                      # 检查状态
    def clear_modality_state(self, modality, state_id=None): ...    # 清除状态
    def get_all_modality_states(self): ...                           # 获取所有状态
```

### MultiModalCallback

```python
class MultiModalCallback(BaseCallback):
    """跨模态回调处理器基类"""
    
    # 核心方法
    def on_multimodal_state_update(self, modality_states): ...  # 状态更新回调
    def _check_fusion_condition(self, modality_states): ...     # 检查融合条件
    def _build_multimodal_event(self, modality_states): ...     # 构建事件
    
    # 状态管理
    def get_modality_state(self, modality_type): ...  # 获取某模态状态
```

## 实现示例

### 实现的类

#### 单模态
- `FaceStreamListener` (继承 BaseListener) - 讯飞3588人脸流监听
- `BaiduFaceCallback` (继承 BaseCallback) - 百度人脸识别+缓存

#### 跨模态
- `WatchIntroListener` (继承 MultiModalListener) - 注视监听（视觉+听觉）
- `WatchIntroCallback` (继承 MultiModalCallback) - 注视检测和事件发送

### 文件结构

```
robot_voice/listener/
├── __init__.py
├── base.py                    # 基类定义
├── callback_base.py           # 回调基类定义
├── baidu_face/
│   ├── __init__.py
│   ├── face_listener.py       # 旧版（保留兼容）
│   ├── face_listener_re.py    # 重构版
│   ├── face_callback.py       # 旧版（保留兼容）
│   └── face_callback_re.py    # 重构版
└── watch_intro/
    ├── __init__.py
    ├── watch_intro_handler.py      # 旧版（保留兼容）
    ├── watch_intro_handler_re.py   # 重构版v1（单类设计）
    └── watch_intro_handler_re2.py  # 重构版v2（Listener+Callback分离）
```

## 迁移指南

### 从旧架构迁移

**旧代码（使用 msg_processor）：**
```python
msg_processor = BaseMsgProcessor(voice_server)
msg_processor.send_face(face_msg)
msg_processor.send_instruct(instruction_msg)
```

**新代码（使用 Callback）：**
```python
face_callback = BaiduFaceCallback(voice_server)
face_callback.on_face_change(face_index, face_image, face_info)
face_callback.send_instruction_with_face(instruction_data)
```

## 设计优势

1. **职责清晰**
   - Listener 只负责监听和触发
   - Callback 负责业务处理
   - MultiModalListener 负责跨模态融合

2. **易于扩展**
   - 新增模态：继承 BaseListener 和 BaseCallback
   - 新增跨模态场景：继承 MultiModalListener

3. **便于测试**
   - 各层解耦，可独立测试
   - Mock 容易

4. **代码复用**
   - 基类提供通用功能
   - 子类专注特定模态/场景

## 总结

- **单模态** = BaseListener + BaseCallback（两层）
  - Listener: 监听 + 触发
  - Callback: 处理 + 缓存 + 发送

- **跨模态** = MultiModalListener + MultiModalCallback（两层）
  - MultiModalListener: 订阅 + 缓存 + 通知
  - MultiModalCallback: 融合 + 判断 + 发送

- **架构一致性** = 所有场景都遵循 Listener/Callback 分离原则

这样的设计保持了架构的一致性和清晰性，便于理解、测试和扩展。
