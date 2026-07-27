## 自定义基于FastAPI的消息客户端

1. 创建一个继承自[BaseFastAPIMsgClient](../../algo_tools/messages/base.py)的类: `CustomerMsgClient`
2. 实现`get_msg_dict`方法，将消息转换为字典格式
3. 实现`send_message_once`方法，用于客户端通过回调接口发送消息
4. 实现`_register_routes`方法，用于处理客户端发送的消息， 添加路由

# 启动服务端
```
export PYTHONPATH=.:$PYTHONPATH && python3 examples/message/msg_server.py
```

# 启动客户端
```
export PYTHONPATH=.:$PYTHONPATH && python3 examples/message/msg_client.py
```
