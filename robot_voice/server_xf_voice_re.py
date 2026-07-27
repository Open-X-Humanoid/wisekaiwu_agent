# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
"""
讯飞语音服务器 - 重构版

使用新架构的XFVoiceListener和XFVoiceCallback，不依赖msg_processor。
支持与人脸识别、手柄控制等的集成。
"""
from dotenv import load_dotenv
from robot_voice.utils.check_xf import check_xunfei_network_once, CheckXFNetwork
from robot_voice.listener.xf_voice.xf_voice_listener_re import create_xf_voice_system
from robot_voice.listener.xf_voice.aiui_python import AIUIClient
from robot_voice.listener.xf_voice import EventCallback
from robot_voice.listener.watch_intro.watch_intro_listener_re import WatchIntroListener
from robot_voice.listener.watch_intro.watch_intro_callback_re import WatchIntroCallback
from robot_voice.utils.log import setup_logger
from robot_voice.utils.voice_server import VoiceSocketServer
from robot_voice.utils.service_factory import create_tts_player, create_face_service
from robot_voice.utils.event_bridge import connect_face_to_watch_intro, connect_voice_to_watch_intro
from configs.server_cfg import (
    get_common_args_parser, 
    VOICE_MODES,
    init_sbus_monitor
)
import logging

logger = logging.getLogger(__name__)


def main(args):
    """主函数"""
    
    # 1. 检查讯飞网络连接
    check_xunfei_network_once()
    checker = CheckXFNetwork(seconds=60.0)
    
    # 2. 初始化TTS播放器（如果启用）
    tts_player = None
    if not args.disable_tts:
        tts_player = create_tts_player(args.tts, args.voice)
    else:
        logger.info("TTS功能已禁用")
    
    # 3. 创建VoiceSocketServer（带TTS）
    voice_server = VoiceSocketServer(
        host="0.0.0.0",
        port=args.port,
        tts_player=tts_player
    )
    logger.info(f"VoiceSocketServer创建完成，端口: {args.port}")
    
    # 4. 确定语音交互模式
    if args.disable_asr:
        logger.warning("ASR已禁用，不会启动语音监听")
        xf_listener = None
        xf_callback = None
    else:
        # 根据配置选择模式
        mode_map = {
            VOICE_MODES.NLP: "NLP",
            VOICE_MODES.NLP_WITH_LUOYU: "LUOYU",
            VOICE_MODES.ONLINE_ASR_XF_SKILL: "OnlineASR",
            VOICE_MODES.OFFLINE_ASR: "OfflineASR"
        }
        voice_mode = mode_map.get(
            VOICE_MODES.ONLINE_ASR_XF_SKILL,  # 默认使用在线ASR
            "OnlineASR"
        )
        
        # 5. 创建语音监听系统（新架构）
        xf_listener, xf_callback = create_xf_voice_system(
            mode=voice_mode,
            voice_server=voice_server,
            wake_word=getattr(args, 'wake_word', "天工天工"),
            recv_msg_timeout=90,
            check_xunfei=not args.disable_checker,
            cache_timeout=60
        )
        logger.info(f"讯飞语音系统创建完成，模式: {voice_mode}")
    
    # 6. 初始化WatchIntro系统（跨模态：视觉+听觉）
    watch_intro_listener = None
    watch_intro_callback = None
    watching_delay = getattr(args, 'watching_delay', None)
    
    if watching_delay:
        watch_intro_callback = WatchIntroCallback(
            voice_server=voice_server,
            watching_delay=watching_delay
        )
        watch_intro_listener = WatchIntroListener(
            on_state_update=watch_intro_callback.on_multimodal_state_update
        )
        logger.info(f"WatchIntro系统创建完成，延时: {watching_delay}s")
    else:
        logger.info("WatchIntro功能未启用（watching_delay未设置）")
    
    # 7. 初始化人脸服务（如果启用）- 使用新架构
    face_listener = None
    face_callback = None
    if args.enable_face:
        face_listener, face_callback = create_face_service(
            voice_server=voice_server,
            face_ip=args.face_ip,
            face_port=args.face_port
        )
        
        # 如果启用了WatchIntro，连接人脸事件
        if watch_intro_listener and face_callback:
            connect_face_to_watch_intro(face_callback, watch_intro_listener)
    
    # 8. 将语音事件连接到WatchIntro系统
    if watch_intro_listener and xf_callback:
        connect_voice_to_watch_intro(xf_callback, watch_intro_listener)
    
    # 9. 创建AIUI客户端
    aiui_client = None
    if xf_listener:
        callback = EventCallback(xf_listener)
        aiui_client = AIUIClient("10.42.0.127", 19199, callback=callback)
        logger.info("AIUI客户端创建完成")
    
    # 10. 订阅手柄控制信息
    sbus_monitor = None
    if args.sbus:
        sbus_monitor = init_sbus_monitor(
            xf_listener, 
            voice_server, 
            args.music_dir
        )
        logger.info("手柄监控服务创建完成")
    
    # 11. 启动所有服务
    logger.info("=" * 60)
    logger.info("正在启动各个服务...")
    logger.info("=" * 60)
    
    if sbus_monitor:
        sbus_monitor.start()
        logger.info("✓ 手柄监控服务已启动")
    
    if face_listener:
        face_listener.start()
        logger.info("✓ 人脸监听服务已启动")
    
    if watch_intro_listener:
        watch_intro_listener.start()
        logger.info("✓ WatchIntro监听服务已启动")
    
    if aiui_client:
        aiui_client.start()
        logger.info("✓ AIUI客户端已启动")
    
    checker.start()
    logger.info("✓ 讯飞网络检查服务已启动")
    
    if xf_listener:
        xf_listener.start()
        logger.info("✓ 讯飞语音监听服务已启动")
    
    logger.info("=" * 60)
    logger.info("所有服务启动完成，语音服务器开始运行")
    logger.info("=" * 60)
    
    # 启动语音服务器（阻塞主线程，直到Ctrl-C）
    try:
        voice_server.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，准备退出...")
    
    # 12. 清理资源
    logger.info("=" * 60)
    logger.info("正在清理资源...")
    logger.info("=" * 60)
    
    voice_server.stop()
    logger.info("✓ VoiceSocketServer已停止")
    
    if xf_listener:
        xf_listener.stop()
        logger.info("✓ 讯飞语音监听服务已停止")
    
    checker.stop()
    logger.info("✓ 讯飞网络检查服务已停止")
    
    if aiui_client:
        aiui_client.close()
        logger.info("✓ AIUI客户端已关闭")
    
    if watch_intro_listener:
        watch_intro_listener.stop()
        logger.info("✓ WatchIntro监听服务已停止")
    
    if watch_intro_callback:
        watch_intro_callback.cleanup()
        logger.info("✓ WatchIntro回调处理器已清理")
    
    if face_listener:
        face_listener.stop()
        logger.info("✓ 人脸监听服务已停止")
    
    if sbus_monitor:
        sbus_monitor.stop()
        logger.info("✓ 手柄监控服务已停止")
    
    logger.info("=" * 60)
    logger.info("语音服务端正常退出")
    logger.info("=" * 60)


if __name__ == '__main__':
    # 设置日志
    logger = setup_logger()
    logger.info("logger setup done.")
    
    # 解析命令行参数
    parser = get_common_args_parser()
    args = parser.parse_args()
    
    # 加载环境变量
    load_dotenv(dotenv_path=args.env_config)
    
    # 运行主程序
    main(args)
