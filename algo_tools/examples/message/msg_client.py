# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import logging
import threading
from pydantic import BaseModel

from algo_tools.messages.base import BaseFastAPIMsgClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 定义完整的 Message 数据结构
class Message(BaseModel):
    command_id: str
    content: str


class CustomerMsgClient(BaseFastAPIMsgClient):
    def __init__(self,
                 host: str = "0.0.0.0",
                 port: int = 8164,
                 enable_input: bool = True,
                 enable_output: bool = True):
        super().__init__(host, port, enable_input, enable_output)

    def _register_routes(self):
        @self.app.post("/agent/instruction")
        async def recv_message(message: Message):
            """接收消息并处理"""
            logger.info(f"Received message: {message}")

            # 处理消息
            msg_dict = self.get_msg_dict(message)
            await self.process_message(msg_dict)

            return {"status": 0, "message": "成功", "command_id": message.command_id}
        
    def get_msg_dict(self, message: Message):
        """转成消息字典，内含`instruction`字段。"""
        return {"instruction": message.content, "raw_message": message}
    
    async def send_message_once(self, text: str, **kwargs):
        """
            通过回调接口发送任务进度
        """
        logger.info(f"receive msg: {text}")

if __name__ == "__main__":
    client = CustomerMsgClient()
    server_thread = threading.Thread(target=client.start, daemon=True)
    server_thread.start()
    
    # 测试客户端
    client.send_message("client test")  # 日志输出 "receive msg: client test"
    server_thread.join()
    