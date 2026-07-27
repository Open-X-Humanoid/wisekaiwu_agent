import logging
from dotenv import load_dotenv
from robot_voice.utils.log import setup_logger
from robot_voice.livekit_agent.room_client import RoomClient
from configs.server_cfg import init_sbus_monitor, get_msg_listener, get_common_args_parser, VOICE_MODES, init_face_service
import sys
import asyncio
import json
from livekit import rtc, api
import os
import inspect

# 防止livekit和robot_voice的logger重复打印
lk_logger = logging.getLogger("livekit")
lk_logger.propagate = False
rv_logger = logging.getLogger("robot_voice")
rv_logger.propagate = False
# 关闭livekit 底层输出的websocket信息
logging.getLogger("websockets.server").setLevel(logging.INFO)
logging.getLogger("websockets.client").setLevel(logging.INFO)
logging.getLogger("livekit.agents").setLevel(logging.INFO)


def main(sbus_enable=False, music_dir=None, tts_version='adaptive',voice_id="tiangong_v1", port=8765, check_xunfei=True,
         enable_face=False, face_ip="10.42.0.127", face_port=9090, asr_mode=None):
    
    voice_publisher = None
    
    # 先创建语音服务器和消息监听器（现在一次性创建所有组件）
    msg_listener, voice_server, msg_processor = get_msg_listener(
        mode=VOICE_MODES.ONLINE_ASR_XF_SKILL,
        voice_publisher=voice_publisher,
        tts_version=tts_version,
        voice_id=voice_id,
        port=port,
        check_xunfei=check_xunfei
    )

    room_client = RoomClient()
    room_client.register_callback(voice_server.async_broadcast_voice)
    # 初始化人脸服务（如果启用）
    face_listener = None
    if enable_face:
        face_listener = init_face_service(
            msg_processor=msg_processor,
            face_ip=face_ip,
            face_port=face_port
        )
    
    # 订阅手柄控制信息，可播放固定音频，可开关语音交互
    sbus_monitor = init_sbus_monitor(msg_listener, voice_server, music_dir) \
        if sbus_enable else None

    
    logger.info("正在启动各个服务...")
    if sbus_monitor:
        sbus_monitor.start()
        logger.info("手柄监控服务已启动")
    
    if face_listener:
        face_listener.start()
        logger.info("人脸监听服务已启动")
    
    logger.info("语音消息监听器已启动")
    
    room_client.start()
    # 启动语音服务，这会让主程序常驻，直到遇到 ctrl-c
    logger.info("正在启动语音WebSocket服务器...")
    voice_server.start()


    # 清理资源
    logger.info("正在清理资源...")
    voice_server.stop()
    room_client.stop()

    if face_listener:
        face_listener.stop()
        logger.info("人脸监听服务已停止")
    
    if sbus_monitor:
        sbus_monitor.stop()
        logger.info("手柄监控服务已停止")
    
    logger.info("语音服务端正常退出")
    
    
if __name__ == "__main__":
    logger = setup_logger()
    logger.info("logger setup done.")
    # 创建ArgumentParser对象
    parser = get_common_args_parser()

    # 解析参数
    args, remaining_argv = parser.parse_known_args(sys.argv[1:])
    sys.argv = [sys.argv[0]] + remaining_argv

    load_dotenv(dotenv_path=args.env_config)
    main(sbus_enable=args.sbus, 
        music_dir=args.music_dir,
        tts_version=args.tts,
        voice_id=args.voice,
        port=args.port,
        check_xunfei=not args.disable_checker,
        enable_face=args.enable_face,
        face_ip=args.face_ip,
        face_port=args.face_port,
        asr_mode=args.asr_mode)