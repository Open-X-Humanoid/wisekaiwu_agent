#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import asyncio

import websockets

# 存储连接的客户端
clients = set()


async def handle_logging(websocket, path):
    clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received message from client: {message}")
            # 发送消息给所有连接的客户端
            await asyncio.wait([asyncio.create_task(client.send(message)) for client in clients])
    except websockets.ConnectionClosed:
        print("Client disconnected")
    finally:
        clients.remove(websocket)


async def start_server():
    # 在指定的地址和端口启动 WebSocket 服务器
    server = await websockets.serve(handle_logging, "0.0.0.0", 8686)
    print("WebSocket server started on ws://0.0.0.0:8686")
    await server.wait_closed()


# 启动服务器
def main():
    asyncio.run(start_server())


if __name__ == "__main__":
    main()
