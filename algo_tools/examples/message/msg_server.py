# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import logging
import threading
import time

import requests
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


# 定义完整的 Message 数据结构
class Message(BaseModel):
    command_id: str
    content: str


@app.post("/agent/instruction/")
async def recv_message(message: Message):
    """接收消息并处理"""
    logger.info(f"Received message: {message}")

    return {"status": 0, "message": "成功", "command_id": message.command_id}


if __name__ == "__main__":
    server_thread = threading.Thread(
        target=uvicorn.run, 
        args=(app,), 
        kwargs={"host": "0.0.0.0", "port": 8000},
        daemon=True
    )
    server_thread.start()
    
    time.sleep(0.02)  # 等待服务端启动
    
    # 测试服务端， 日志输出： Received message: command_id='1' content='server test'
    response = requests.post(
        url="http://localhost:8000/agent/instruction/",
        json={
            "command_id": "1",
            "content": "server test"
        }
    )
    