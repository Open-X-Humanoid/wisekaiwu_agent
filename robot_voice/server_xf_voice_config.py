# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
"""
讯飞语音服务器 - 配置驱动版

使用注册器模式 + Pydantic配置 + YAML配置文件，优雅启动所有服务。
参考 Kaiwu Agent 的架构设计。
"""
import argparse
import logging
import sys
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from robot_voice.utils.log import setup_logger
from robot_voice.utils.config_model import ServerConfig
from robot_voice.utils.registry import TTS_PLAYERS, ASR_LISTENERS, FACE_SERVICES
from robot_voice.utils.service_factory import create_tts_player, create_face_service
from robot_voice.utils.event_bridge import connect_face_to_watch_intro, connect_voice_to_watch_intro
from robot_voice.utils.voice_server import VoiceSocketServer
from robot_voice.utils.check_xf import check_xunfei_network_once, CheckXFNetwork
from robot_voice.listener.xf_voice.xf_voice_listener_re import create_xf_voice_system
from robot_voice.listener.xf_voice.aiui_python import AIUIClient
from robot_voice.listener.xf_voice import EventCallback
from robot_voice.listener.watch_intro.watch_intro_listener_re import WatchIntroListener
from robot_voice.listener.watch_intro.watch_intro_callback_re import WatchIntroCallback
from configs.server_cfg import init_sbus_monitor

logger = logging.getLogger(__name__)


class ServiceManager:
    """服务管理器 - 统一管理所有服务的生命周期"""
    
    def __init__(self):
        self.services: List[Any] = []
        self.service_names: List[str] = []
        
    def register(self, service: Any, name: str):
        """注册服务"""
        if service:
            self.services.append(service)
            self.service_names.append(name)
            logger.debug(f"服务已注册: {name}")
    
    def start_all(self):
        """启动所有服务"""
        logger.info("=" * 60)
        logger.info("正在启动各个服务...")
        logger.info("=" * 60)
        
        for service, name in zip(self.services, self.service_names):
            try:
                if hasattr(service, 'start'):
                    service.start()
                    logger.info(f"✓ {name} 已启动")
            except Exception as e:
                logger.error(f"✗ {name} 启动失败: {e}")
        
        logger.info("=" * 60)
        logger.info("所有服务启动完成")
        logger.info("=" * 60)
    
    def stop_all(self):
        """停止所有服务"""
        logger.info("=" * 60)
        logger.info("正在清理资源...")
        logger.info("=" * 60)
        
        # 反向停止服务
        for service, name in reversed(list(zip(self.services, self.service_names))):
            try:
                if hasattr(service, 'stop'):
                    service.stop()
                    logger.info(f"✓ {name} 已停止")
                elif hasattr(service, 'close'):
                    service.close()
                    logger.info(f"✓ {name} 已关闭")
                elif hasattr(service, 'cleanup'):
                    service.cleanup()
                    logger.info(f"✓ {name} 已清理")
            except Exception as e:
                logger.error(f"✗ {name} 停止失败: {e}")
        
        logger.info("=" * 60)
        logger.info("语音服务端正常退出")
        logger.info("=" * 60)


def build_services(config: ServerConfig) -> Dict[str, Any]:
    """根据配置构建所有服务
    
    Returns:
        包含所有服务实例的字典
    """
    services = {}
    
    # 1. 检查讯飞网络
    check_xunfei_network_once()
    services['checker'] = CheckXFNetwork(seconds=60.0)
    
    # 2. 创建TTS播放器
    if config.tts.enabled:
        services['tts_player'] = create_tts_player(config.tts.type, config.tts.voice_id)
    else:
        logger.info("TTS功能已禁用")
        services['tts_player'] = None
    
    # 3. 创建VoiceSocketServer
    services['voice_server'] = VoiceSocketServer(
        host=config.host,
        port=config.port,
        tts_player=services['tts_player']
    )
    logger.info(f"VoiceSocketServer创建完成，端口: {config.port}")
    
    # 4. 创建语音监听系统
    if config.asr.enabled:
        services['xf_listener'], services['xf_callback'] = create_xf_voice_system(
            mode=config.asr.mode,
            voice_server=services['voice_server'],
            wake_word=config.asr.wake_word,
            recv_msg_timeout=config.asr.recv_msg_timeout,
            check_xunfei=config.asr.check_xunfei,
            cache_timeout=config.asr.cache_timeout
        )
        logger.info(f"讯飞语音系统创建完成，模式: {config.asr.mode}")
    else:
        logger.warning("ASR已禁用")
        services['xf_listener'] = None
        services['xf_callback'] = None
    
    # 5. 创建WatchIntro系统
    if config.watch_intro.enabled and config.watch_intro.watching_delay:
        services['watch_intro_callback'] = WatchIntroCallback(
            voice_server=services['voice_server'],
            watching_delay=config.watch_intro.watching_delay
        )
        services['watch_intro_listener'] = WatchIntroListener(
            on_state_update=services['watch_intro_callback'].on_multimodal_state_update
        )
        logger.info(f"WatchIntro系统创建完成，延时: {config.watch_intro.watching_delay}s")
    else:
        services['watch_intro_listener'] = None
        services['watch_intro_callback'] = None
    
    # 6. 创建人脸服务
    if config.face.enabled:
        services['face_listener'], services['face_callback'] = create_face_service(
            voice_server=services['voice_server'],
            face_ip=config.face.face_ip,
            face_port=config.face.face_port
        )
        
        # 连接人脸事件到WatchIntro
        if services['watch_intro_listener'] and services['face_callback']:
            connect_face_to_watch_intro(services['face_callback'], services['watch_intro_listener'])
    else:
        services['face_listener'] = None
        services['face_callback'] = None
    
    # 7. 连接语音事件到WatchIntro
    if services.get('watch_intro_listener') and services.get('xf_callback'):
        connect_voice_to_watch_intro(services['xf_callback'], services['watch_intro_listener'])
    
    # 8. 创建AIUI客户端
    if services['xf_listener']:
        callback = EventCallback(services['xf_listener'])
        services['aiui_client'] = AIUIClient(config.aiui_ip, config.aiui_port, callback=callback)
        logger.info("AIUI客户端创建完成")
    else:
        services['aiui_client'] = None
    
    # 9. 创建手柄监控
    if config.sbus.enabled:
        services['sbus_monitor'] = init_sbus_monitor(
            services['xf_listener'],
            services['voice_server'],
            config.sbus.music_dir
        )
        logger.info("手柄监控服务创建完成")
    else:
        services['sbus_monitor'] = None
    
    return services


def main(config: ServerConfig):
    """主函数 - 配置驱动"""
    
    # 构建所有服务
    services = build_services(config)
    
    # 创建服务管理器
    manager = ServiceManager()
    
    # 注册需要启动的服务（按启动顺序）
    manager.register(services.get('sbus_monitor'), "手柄监控服务")
    manager.register(services.get('face_listener'), "人脸监听服务")
    manager.register(services.get('watch_intro_listener'), "WatchIntro监听服务")
    manager.register(services.get('aiui_client'), "AIUI客户端")
    manager.register(services.get('checker'), "讯飞网络检查服务")
    manager.register(services.get('xf_listener'), "讯飞语音监听服务")
    
    # 启动所有服务
    manager.start_all()
    
    # 启动语音服务器（阻塞主线程）
    logger.info("语音服务器开始运行，按 Ctrl-C 退出")
    try:
        services['voice_server'].start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，准备退出...")
    
    # 清理资源
    manager.stop_all()
    
    # 额外清理VoiceServer和Callback
    if services['voice_server']:
        services['voice_server'].stop()
        logger.info("✓ VoiceSocketServer已停止")
    
    if services.get('watch_intro_callback'):
        services['watch_intro_callback'].cleanup()
        logger.info("✓ WatchIntro回调处理器已清理")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Robot Voice Server - 配置驱动版")
    parser.add_argument("-c", "--config", type=str, help="YAML配置文件路径（可选）")
    parser.add_argument("-ec", "--env-config", type=str, default=".env", help="环境变量配置文件")
    
    # 保留兼容旧参数
    parser.add_argument("--port", type=int, default=8765, help="服务器端口")
    parser.add_argument("--disable-tts", action="store_true", help="禁用TTS")
    parser.add_argument("--disable-asr", action="store_true", help="禁用ASR")
    parser.add_argument("--enable-face", action="store_true", help="启用人脸服务")
    parser.add_argument("--watching-delay", type=int, help="WatchIntro延时（秒）")
    parser.add_argument("--sbus", action="store_true", help="启用手柄控制")
    parser.add_argument("-t", "--tts", type=str, default="adaptive", help="TTS类型")
    parser.add_argument("-v", "--voice", type=str, default="tiangong_v1", help="音色ID")
    
    return parser.parse_args()


if __name__ == '__main__':
    # 设置日志
    logger = setup_logger()
    logger.info("logger setup done.")
    
    # 解析参数
    args = parse_args()
    
    # 加载环境变量
    load_dotenv(dotenv_path=args.env_config)
    
    # 构建配置（优先使用YAML，否则从命令行参数构建）
    if args.config:
        # TODO: 从YAML文件加载配置
        logger.info(f"从配置文件加载: {args.config}")
        import yaml
        with open(args.config, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        config = ServerConfig.model_validate(config_dict)
    else:
        # 从命令行参数构建配置
        config = ServerConfig(
            port=args.port,
            tts={'type': args.tts, 'voice_id': args.voice, 'enabled': not args.disable_tts},
            asr={'enabled': not args.disable_asr},
            face={'enabled': args.enable_face},
            watch_intro={'enabled': bool(args.watching_delay), 'watching_delay': args.watching_delay},
            sbus={'enabled': args.sbus}
        )
    
    # 验证配置版本
    config.validate_version()
    
    # 打印配置摘要
    logger.info("=" * 60)
    logger.info("服务配置:")
    logger.info(f"  端口: {config.port}")
    logger.info(f"  TTS: {config.tts.type} ({'启用' if config.tts.enabled else '禁用'})")
    logger.info(f"  ASR: {config.asr.mode} ({'启用' if config.asr.enabled else '禁用'})")
    logger.info(f"  人脸: {'启用' if config.face.enabled else '禁用'}")
    logger.info(f"  WatchIntro: {'启用' if config.watch_intro.enabled else '禁用'}")
    logger.info(f"  手柄: {'启用' if config.sbus.enabled else '禁用'}")
    logger.info("=" * 60)
    
    # 运行主程序
    try:
        main(config)
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
