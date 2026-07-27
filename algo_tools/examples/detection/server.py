# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import json
import time
from algo_tools.websocket.task_server import TaskSocketServer


class DetectionAgent:
    def __init__(self, task_server: TaskSocketServer):
        # 设置收到指令后的回调函数
        task_server.register_task_callback(self.recv_task)
        self.task_server = task_server
    
    def recv_task(self, message):
        """收到客户端指令后的回调函数。"""
        message, websocket = message["message"], message["websocket"]
        msg_dict = json.loads(message)
        print(f"recv: {msg_dict}")
        self.send_result(msg_dict, websocket)
    
    def send_result(self, msg_dict, websocket):
        """给客户端发结果。"""
        # 模拟每0.1s回复一次检测坐标
        for i in range(30):
            time.sleep(0.1)
            msg_dict = {"state": "running", "data": {"x1": i, "y1": i+1, "x2": i+2, "y2": i+3}}
            self.task_server.send_msg(websocket, json.dumps(msg_dict))
        
        # 告诉服务端，结束了别等了
        msg_dict = {"state": "finished"}
        self.task_server.send_msg(websocket, json.dumps(msg_dict))
            
        # 当前函数执退出后，websocket会释放，连接会断开
    
    def start(self):
        # 会卡住主进程，不让主进程退出
        # asyncio.run(server.start_server())
        self.task_server.start()
        
    def stop(self):
        self.task_server.stop()
        
    
def main():
    task_server = TaskSocketServer(host="localhost", 
                                   port="9192",
                                   task_path="/task")
    control_agent = DetectionAgent(task_server)
    # 启动服务，监听，接受task指令，执行task，给出回复，监听 ...
    control_agent.start()


if __name__ == "__main__":
    main()
