#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
## Build a GUI based on tkinter.
## Run at demonstration device instead of Orin

import asyncio
import re
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

import websockets


# GUI 类
class WebSocketGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WebSocket Server GUI")
        self.geometry("1200x800")

        # 设置字体和样式
        self.configure(bg="#f4f4f9")  # 背景颜色
        self.style = ttk.Style()
        self.style.configure("TButton", font=("Arial", 12), padding=6)
        self.style.configure("TLabel", font=("Arial", 12), background="#f4f4f9")

        # # 滚动文本框
        # self.output_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=70, height=20, font=("Arial", 10), bg="#f0f0f0", fg="#333")
        # self.output_text.pack(pady=10)

        # 使用框架 (Frame) 使布局更灵活
        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True)
        frame.pack_propagate(False)  # 确保框架不会缩小到子控件的大小

        # 文本框 1
        self.output_text_1 = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=10, height=80)
        self.output_text_1.pack(side="left", fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 文本框 2
        self.output_text_2 = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=10, height=80)
        self.output_text_2.pack(side="left", fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 为不同类型的消息设置标签样式
        self.output_text_1.tag_configure("plan", foreground="blue", font=("Arial", 10, "italic"))
        self.output_text_1.tag_configure(
            "current_step", foreground="green", font=("Arial", 10, "bold")
        )
        self.output_text_1.tag_configure(
            "user_instruction", foreground="red", font=("Helvetica", 12, "bold italic")
        )

        self.output_text_2.tag_configure("message", foreground="blue", font=("Arial", 10, "italic"))
        self.output_text_2.tag_configure("react_done", foreground="red", font=("Arial", 10, "bold"))
        self.output_text_2.tag_configure(
            "current_step", foreground="green", font=("Arial", 10, "bold")
        )

        # 创建并启动异步事件循环的线程
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.run_async_loop, daemon=True).start()

        # 启动 WebSocket 服务器任务
        self.loop.call_soon_threadsafe(lambda: self.loop.create_task(self.start_server()))

    def run_async_loop(self):
        """在单独的线程中运行 asyncio 事件循环。"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    # def display_message(self, message):
    #     self.output_text.insert(tk.END, message + "\n")
    #     self.output_text.see(tk.END)

    def display_message(self, message, box=1, tag=None):
        if box == 1:
            self.output_text_1.insert(tk.END, message + "\n", tag)
            self.output_text_1.see(tk.END)
        elif box == 2:
            self.output_text_2.insert(tk.END, message + "\n", tag)
            self.output_text_2.see(tk.END)

    async def start_server(self):
        """启动 WebSocket 服务器。"""
        server = await websockets.serve(self.websocket_handler, "0.0.0.0", 12345)
        # print("Server started on port 12345")
        await server.wait_closed()

    async def websocket_handler(self, websocket, path):
        """处理 WebSocket 连接。"""
        # print("Client connected")
        try:
            async for message in websocket:
                # print(f"Received message: {message}")
                # self.display_message(message)

                # 根据接收到的消息内容选择文本框
                if "Message" in message:
                    if "Human" not in message:
                        if "Ai Message" in message:
                            modified_message = message.replace(
                                "== Ai Message ==", " Brain Thought "
                            )
                            modified_message = re.sub(
                                r"^.*Call ID:.*\n?", "", modified_message, flags=re.MULTILINE
                            )
                            modified_message = re.sub(
                                r"\(chatcmpl-tool-[a-f0-9]{32}\)", "", modified_message
                            )
                        if "Tool Message" in message:
                            modified_message = message.replace("Tool Message", "Tool Result")
                        self.display_message(modified_message, box=2, tag=None)
                    # else:
                    #     self.display_message(message, box=1, tag = None)

                # elif "ReAct Execution Start" in message:
                #         self.display_message(message, box=2, tag = None)

                elif "<<< Step Done" in message:
                    self.display_message(message, box=2, tag="current_step")

                elif ">>> Current Step" in message:
                    self.display_message(message, box=2, tag="current_step")
                    # self.output_text_2.delete(1.0, tk.END)

                elif "user instruction" in message:
                    self.output_text_1.delete(1.0, tk.END)
                    self.output_text_2.delete(1.0, tk.END)

                    self.display_message(message, box=1, tag="user_instruction")

                elif "plan" in message:

                    # if "replan" not in message:
                    #     self.output_text_1.delete(1.0, tk.END)
                    #     self.output_text_2.delete(1.0, tk.END)

                    # 提取“plan:”标题和步骤
                    lines = message.splitlines()
                    if lines:
                        # 将第一行 "plan:" 用蓝色打印
                        self.display_message(lines[0], box=1, tag="plan")

                        first_step_done = False
                        # 使用绿色打印每个步骤
                        for line in lines[1:]:
                            if re.match(r"^\d+\.\s", line):  # 匹配步骤开头的 "1. "、"2. " 等
                                if not first_step_done:
                                    # 仅对第一个步骤使用绿色样式
                                    self.display_message(line, box=1, tag="current_step")
                                    first_step_done = True
                                else:
                                    # 其他步骤行使用默认样式
                                    self.display_message(line, box=1)

                            else:
                                self.display_message(line, box=1)  # 默认打印，不带样式标签

                await websocket.send("Message received")
        except websockets.ConnectionClosed:
            # print("Client disconnected")
            pass

    def on_closing(self):
        """在关闭窗口时执行清理工作。"""
        print("Closing server and GUI")
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()


# 启动 GUI 和服务器
def main():
    gui = WebSocketGUI()
    gui.protocol("WM_DELETE_WINDOW", gui.on_closing)
    gui.mainloop()


if __name__ == "__main__":
    main()
