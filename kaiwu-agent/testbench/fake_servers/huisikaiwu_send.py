#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import json
import uuid

import requests

# FastAPI 服务端地址
url = "http://127.0.0.1:8164/agent/instruction"

# 固定的示例数据
user_uuid = "123e4567-e89b-12d3-a456-426614174000"  # 用户 ID 示例
role_info = {
    "roleName": "Assistant",
    "roleUuid": str(uuid.uuid4()),
    "description": "A helpful virtual assistant",
    "modelType": "text-model",
    "skills": ["manipulation", "ask_user", "voice_play"],
}


def generate_payload(command: str) -> dict:
    """
    生成 POST 请求的 payload 数据
    """
    return {
        "userUuid": user_uuid,
        "role": role_info,
        "task": {
            "commandUuid": str(uuid.uuid4()),  # 自动生成唯一指令 ID
            "command": command,  # 用户输入的指令
            "mediaType": "text",  # 固定类型为 text
            "mediaData": "",  # 空数据，后续可扩展为图片/音频数据
            "taskUuid": str(uuid.uuid4()),  # 自动生成任务 ID
        },
    }


def send_request(payload: dict):
    """
    发送 POST 请求到服务器
    """
    try:
        headers = {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        print(response.json())  # 如果返回 JSON 数据
        return response
    except Exception as e:
        print(f"请求发送失败: {e}")
        return None


def run():
    """
    主程序，负责接受用户指令并处理
    """
    print("欢迎使用云端模拟器！")
    print("请输入用户指令，程序将自动构建并发送消息。输入 'exit' 退出程序。\n")

    while True:
        command = input("请输入用户指令 (command): ").strip()
        if command.lower() == "exit":
            print("程序已退出。")
            break

        # 生成数据
        payload = generate_payload(command)

        # 打印即将发送的 JSON 数据
        print("\n即将发送的数据:")
        print(json.dumps(payload, indent=4, ensure_ascii=False))

        # 发送请求并处理响应
        response = send_request(payload)
        if response:
            print("\n服务器响应:")
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.json()}\n")

        print("-" * 50)


if __name__ == "__main__":
    run()
