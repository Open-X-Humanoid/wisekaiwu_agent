# algo_tools
- 算法公共组件，包括消息通讯客户端（msg_client），负责监听语音指令，接收消息指令，架起了robot voice 和 慧思开物APP与kaiwu agent之间的通信通道。
- 提供两种类型的客户端
    - [VoiceSocketClient](../algo_tools/messages/voice_socket.py) : 基于WebSocket的语音消息客户端
    - [ComposeMsgClient](../algo_tools/messages/compose.py)： 组合使用， 可传入多种不同类型的客户端
- 同时提供两种不同类型的客户端基类
    - [BaseSocketClient](../algo_tools/messages/base.py)： 基础消息客户端， 用于自定义消息通讯客户端
    - [BaseFastAPIMsgClient](../algo_tools/messages/base.py)： 基于FastAPI的消息客户端， 用于自定义基于FastAPI的消息通讯客户端
- 注： 当前客户端需要配合agent使用


## 自定义消息通讯客户端
- 详情请参考 [自定义FastAPI消息通讯客户端](../examples/message/README.md)
