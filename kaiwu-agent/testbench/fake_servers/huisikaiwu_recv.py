#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel


class MessagesPayload(BaseModel):
    content: str = ""
    mentionedAgentUuids: list[str] = []
    messageUuid: str = ""
    steps: list[Any] = []
    taskStatus: Optional[str] = None


class DoResultRequest(BaseModel):
    agentName: str = ""
    agentUuid: str = ""
    chatUuid: str = ""
    commandUuid: str = ""
    messages: MessagesPayload = MessagesPayload()
    responseTimestamp: str = ""
    status: str = ""
    userUuid: str = ""


app = FastAPI()


@app.post("/v1/api/chat/doResult")
async def update_step_status(request: DoResultRequest):
    """
    接收机器人反馈并打印出来
    """
    print("=" * 50)
    print("收到机器人反馈:")
    print(f"  agentName: {request.agentName}")
    print(f"  status: {request.status}")
    print(f"  commandUuid: {request.commandUuid}")
    print(f"  taskStatus: {request.messages.taskStatus}")
    print(f"  回复内容: {request.messages.content}")
    print(f"  steps: {request.messages.steps}")
    print("=" * 50)

    return {"status": 0, "message": "成功"}


def run():
    print("虚拟云平台启动中...")
    uvicorn.run(app, host="0.0.0.0", port=8002)


if __name__ == "__main__":
    run()
