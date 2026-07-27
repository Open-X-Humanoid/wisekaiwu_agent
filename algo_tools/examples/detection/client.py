# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import json
import time
from algo_tools.websocket.task_client import TaskClient

def recv_callback(message: str):
    """收到服务端消息的回调函数。
    
    注意注意：
    - 不要在recv_callback做耗时高的操作（如超过1s），否则会阻塞websocket导致无法正常接收消息，最后导致websocket异常断开！
    - 如要做高耗时任务，就把message放到消息队列里，见 algo_tools.utils.msg_monitor.py
    
    Returns:
        wait_msg (bool): 是否继续等待服务端的消息
    """
    # print(f"收到检测服务端消息: {message}")
    
    msg_dict = json.loads(message)
    state = msg_dict["state"]
    data = msg_dict.get("data", None)
    if data is not None:
        print(f"收到检测坐标: {data}")
    
    wait_msg = True
    if state in ("running"):
        # 继续监听
        wait_msg = True
    elif state in ("finished"):
        wait_msg = False
    else:
        print(f'recv_message: 错误, unknown state: {state}')
        wait_msg = False
    
    return wait_msg


def main():
    task_client = TaskClient(
        recv_callback=recv_callback,
        url = 'ws://localhost:9192/task',
        connect_timeout = 3.0, 
        recv_timeout = 60.0
    )
    task_client.start()
    
    # 模拟发送指令
    for i in range(2):
        msg_dict = {"a": i, "b": 1+1}
        task_client.send_message(json.dumps(msg_dict))
        time.sleep(3)
    
    task_client.stop()


if __name__ == "__main__":
    main()
