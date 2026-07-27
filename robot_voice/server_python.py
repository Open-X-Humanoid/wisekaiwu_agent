# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
from dotenv import load_dotenv
from robot_voice.utils.check_xf import check_xunfei_network_once, CheckXFNetwork
from robot_voice.listener.xf_voice import EventCallback
from configs.server_cfg import init_sbus_monitor, get_msg_listener, get_common_args_parser, VOICE_MODES, init_face_service
from robot_voice.utils.log import setup_logger
from robot_voice.listener.xf_voice.aiui_python import AIUIClient


def main(args):

    # 检查 orin到3588,orin到讯飞云(外网)的联通情况,没5s ping一次
    check_xunfei_network_once()
    # if not check_xunfei_network_once():
    #     return
    
    # 设置定时检查
    # TODO: 会导致当前程序无法被ctrl-c退出
    checker = CheckXFNetwork(seconds=60.0)
    
    voice_publisher = None
    
    # 读取语音识别结果的topic
    msg_listener, voice_server, msg_processor = get_msg_listener(
        mode=None if args.disable_asr else VOICE_MODES.ONLINE_ASR_XF_SKILL,
        voice_publisher=voice_publisher,
        tts_version=args.tts if not args.disable_tts else None,
        voice_id=args.voice,
        port=args.port,
        check_xunfei=not args.disable_checker,
        watching_delay=args.watching_delay,
        send_face_immediately=args.send_face
    )

    # 初始化人脸服务（如果启用）
    face_listener = None
    if args.enable_face:
        face_listener = init_face_service(
            msg_processor=msg_processor,
            face_ip=args.face_ip,
            face_port=args.face_port,
        )
    
    # 创建语音消息回调
    callback = EventCallback(msg_listener)

    # without ros
    aiui_client = AIUIClient("10.42.0.127", 19199, callback=callback)
  
    # 语音开关
    # voice_enable_cb = voice_enable_wrapper(msg_listener=msg_listener, voice_server=voice_server)
    # rospy.Subscriber('/voice_enable', String, voice_enable_cb)
    
    # 订阅手柄控制信息，可播放固定音频，可开关语音交互
    sbus_monitor = init_sbus_monitor(msg_listener, voice_server, args.music_dir) \
        if args.sbus else None
    
    # 启动所有服务
    logger.info("正在启动各个服务...")
    
    if sbus_monitor:
        sbus_monitor.start()
        logger.info("手柄监控服务已启动")
    
    if face_listener:
        face_listener.start()
        logger.info("人脸监听服务已启动")
    
    aiui_client.start()
    checker.start()
    if msg_listener:
        msg_listener.start()
    # 启动语音服务，这会让主程序常驻，直到遇到 ctrl-c
    voice_server.start()
    

    # 清理资源
    logger.info("正在清理资源...")
    voice_server.stop()
    if msg_listener:
        msg_listener.stop()
    checker.stop()
    aiui_client.close()
    
    if face_listener:
        face_listener.stop()
        logger.info("人脸监听服务已停止")
    
    if sbus_monitor:
        sbus_monitor.stop()
        logger.info("手柄监控服务已停止")
    
    logger.info("语音服务端正常退出")
    

if __name__ == '__main__':
    logger = setup_logger()
    logger.info("logger setup done.")
    # 创建ArgumentParser对象
    parser = get_common_args_parser()
    
    # 解析参数
    args = parser.parse_args()
    
    load_dotenv(dotenv_path=args.env_config)
    main(args)
