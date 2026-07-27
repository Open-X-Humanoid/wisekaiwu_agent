# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import os
import argparse
from robot_voice.utils.voice_server import VoiceSocketServer
from robot_voice.processor.msg_processor import BaseMsgProcessor
import os
from robot_voice.listener.baidu_face import FaceStreamListener, BaiduFaceCallback
from robot_voice.utils.common import list_files
from robot_voice.tool.doubao import VOICEIDS_TO_TTSIDS
import logging
from dotenv import load_dotenv
from typing import Any, Dict
logger = logging.getLogger(__name__)


# 唤醒词
WAKE_WORD = "天工天工"
DEFAULT_VOICE_DIR = "configs/voice/default"
ADAPTIVE_VOICE_IDs = ["tiangong_v1", "tiangong_v2", "tiangong_v3", "tiangong_v4","tiangong_v5"]
TENCENT_VOICE_IDs = ["101001", "502001"]
DOUBAO_VOICES_IDS = list(VOICEIDS_TO_TTSIDS.keys())

XUNFEI_EVENT_SOURCES=["ros", "sockets"]

# 交互模式
class VOICE_MODES:
    # 无大模型，仅NLP
    ONLINE_ASR_XF_SKILL = "讯飞联网识别_讯飞技能"
    ONLINE_ASR_XF_LUOYU = "讯飞联网识别_讯飞落域"
    
    # 讯飞交互大模型
    # LLM = "联网_讯飞大模型"
    
    # 离线
    ONLINE_ASR_CUSTOM_INTENT = "讯飞联网识别_自研意图"
    OFFLINE_ASR_CUSTOM_INTENT = "讯飞离线识别_自研意图"

    # 时间监听器模式
    EVENT_LISTENER = "离散事件监听器"
    

def get_common_args_parser():
    # 创建ArgumentParser对象
    parser = argparse.ArgumentParser(description="Robot Voice输入参数")

    # 添加参数
    parser.add_argument("-t", "--tts", type=str, 
                        default='doubao', 
                        choices=['adaptive' ,'chattts', 'xftts', 'tencent', "doubao"], 
                        help="选择TTS服务源。")
    # 添加音色，1-3男声，4女生，5备用。当tts选用tencent时需要指定音色
    parser.add_argument("-v","--voice",type=str,
                        default="tiangong_v1",
                        choices=[*ADAPTIVE_VOICE_IDs, *TENCENT_VOICE_IDs, *DOUBAO_VOICES_IDS],
                        help="选择播报音色。")
    parser.add_argument("--sbus",
                        default=False,
                        action="store_true",  # 如果提供了该选项，值为 True；否则为 False
                        help="启用遥控手柄播报功能，默认关闭。")
    parser.add_argument("-m", "--music-dir", type=str, 
                        default=DEFAULT_VOICE_DIR,
                        help="语音播报功能的音频源目录。")
    parser.add_argument("-dc", "--disable-checker", 
                        default=False,
                        action="store_true",
                        help="不检查讯飞3588的摄像头、麦克风等状态")
    parser.add_argument("--disable-tts", 
                        default=False,
                        action="store_true",
                        help="关闭语音合成播报功能，减少依赖")
    # 语速、音量调整参数，目前仅豆包TTS2.0支持
    parser.add_argument("--speech-rate", type=int, default=0,help="豆包tts2.0语音合成语速调整参数，范围[-50, 100]，默认0")
    parser.add_argument("--volume", type=int, default=100,help="豆包tts2.0语音合成音量调整参数，范围[-50, 100]，默认0")

    parser.add_argument("-ec", "--env-config", type=str, default=".env", help="环境变量配置文件，默认 .env")
    
    parser.add_argument("--port", default=8765, type=int, help="port to use, default 8765. For interact agent, you need to use 8788")
    parser.add_argument("-da", "--disable-asr", 
                        default=False,
                        action="store_true",
                        help="关闭语音识别功能，即不监听讯飞3588的语音消息")
    
    # 人脸检测相关参数
    parser.add_argument("--enable-face", 
                        default=False,
                        action="store_true",
                        help="启用人脸检测服务，默认关闭")
    parser.add_argument("--face-ip", type=str, 
                        default="10.42.0.127",
                        help="讯飞3588设备IP地址，默认10.42.0.127")
    parser.add_argument("--face-port", type=int, 
                        default=9090,
                        help="视频流端口，默认9090")
    parser.add_argument("--watching-delay", type=int, 
                        default=None,
                        help="观察延时时间（秒），None表示禁用watching功能，大于0的整数表示启用并设置延时时间，默认为None（禁用）")
    parser.add_argument("--send-face", 
                        default=False,
                        action="store_true",
                        help="识别到人脸信息后立刻广播给客户端，默认先等待用户说话结束后再一起发送")
    # 语音事件流相关参数
    parser.add_argument("--xunfei-event-source", type=str, default="ros", choices=[*XUNFEI_EVENT_SOURCES], help="讯飞语音事件源")
    parser.add_argument("--enable-event", default=True, action="store_true", help="打开/关闭语音事件流")
    parser.add_argument("--enable-audio", default=False, help="打开/关闭音频流")
    parser.add_argument("--mic-server", type=str, default="localhost", help="麦克风服务端地址")
    parser.add_argument("--mic-port", type=int, default=8124, help="麦克风服务端运行端口,默认8124")

    return parser


def get_msg_listener(mode, 
                     voice_publisher=None, 
                     tts_version="adaptive",
                     voice_id = "tiangong_v1", 
                     port=8765, 
                     speech_rate=None, 
                     volume=None,
                     check_xunfei=True, 
                     watching_delay=None,
                     send_face_immediately=False,
                     xunfei_event_source="ros",
                     enable_event=True,
                     enable_audio=False,
                     mic_server="localhost",
                     mic_port=8124):
    # TTS
    if tts_version == "adaptive":
        from robot_voice.tool import AdaptiveLBTTSPlayer
        url_ip = "cosyvoice.x-humanoid-cloud.com"
        url_port = 9962 
        url_port = 9962 
        adaptive_url = f"{url_ip}:{url_port}"
        tts_player = AdaptiveLBTTSPlayer(url = adaptive_url,voice_file=voice_id,voice_publisher=None,publish_dict=True,default_cmd="append")
    elif tts_version == "xftts":
        from robot_voice.tool import XFTTSPlayer
        tts_player = XFTTSPlayer(voice_publisher=voice_publisher)
    elif tts_version == "tencent":
        from robot_voice.tool import TencentTTSPlayer
        tts_player = TencentTTSPlayer(voice_id=voice_id)
    elif tts_version == "doubao":
        from robot_voice.tool import DoubaoTTSPlayer
        tts_player = DoubaoTTSPlayer(voice=voice_id, speech_rate=speech_rate, volume=volume)

    elif tts_version == None:
        # 不启动TTS服务
        tts_player = None
    else:
        raise NotADirectoryError(tts_version)

    logger.info(f"TTS版本：{tts_version}")
    
    # 起一个服务，对外广播语音消息，并接受tts合成和语音播报请求    
    voice_server = VoiceSocketServer(
        host="0.0.0.0", 
        port=port,
        tts_player=tts_player
    )
    
    # 创建消息处理器
    msg_processor = BaseMsgProcessor(voice_server, 
                                     watching_delay=watching_delay,
                                     send_face_immediately=send_face_immediately)
    
    commons = dict(   
        mode=mode,
        msg_processor=msg_processor,
        wake_word=WAKE_WORD,
        check_xunfei=check_xunfei,
        xunfei_event_source=xunfei_event_source,
        enable_event=enable_event,
        enable_audio=enable_audio,
        mic_server_uri=mic_server,
        mic_port=mic_port
    )

    if mode == VOICE_MODES.ONLINE_ASR_XF_SKILL:
        # 第一版：需要写句式的意图识别，无大模型，纯语义理解
        from robot_voice.listener.xf_voice import XFNLPListener
        listener = XFNLPListener(**commons)
    elif mode == VOICE_MODES.ONLINE_ASR_XF_LUOYU:
        # 第二版： 不需要写句式的意图识别，用落域技能实现，无大模型，纯语义理解
        # 详见 https://aiui-doc.xf-yun.com/project-1/doc-359/
        from robot_voice.listener.xf_voice import XFLUOYUListener
        listener = XFLUOYUListener(**commons)
    elif mode == VOICE_MODES.ONLINE_ASR_CUSTOM_INTENT:
        from robot_voice.listener.xf_voice import XFOnlineASRListener
        listener = XFOnlineASRListener(**commons)
    elif mode == VOICE_MODES.OFFLINE_ASR_CUSTOM_INTENT:
        from robot_voice.listener.xf_voice import XFOfflineASRListener
        listener = XFOfflineASRListener(**commons)
    elif mode == VOICE_MODES.EVENT_LISTENER:
        from robot_voice.listener.event_listener import XFEventListener
        listener = XFEventListener(**commons)
    elif mode == None:
        # 若mode为None，则不启动语音输入服务
        listener = None
    else:
        raise NotImplementedError(f"unsupported mode: {mode}")
    
    return listener, voice_server, msg_processor


def init_face_service(msg_processor, face_ip="10.42.0.127", face_port=9090):
    """
    初始化人脸服务
    
    Args:
        msg_processor: 消息处理器实例
        face_ip: 讯飞3588设备IP地址
        face_port: 视频流端口
        
    Returns:
        face_listener: 人脸监听器实例，如果初始化失败则返回None
    """        
    try:        
        # 创建百度人脸回调处理器（API配置从环境变量自动获取）
        face_callback = BaiduFaceCallback(
            msg_processor=msg_processor,
            confidence_threshold=50.0  # 进一步降低阈值，提高识别成功率
        )
        
        # 创建人脸监听器
        face_listener = FaceStreamListener(
            device_ip=face_ip,
            video_port=face_port,
            on_face_change=face_callback.on_face_change,
            on_face_disappeared=face_callback.on_face_disappeared
        )
        
        logger.info(f"人脸服务已初始化: {face_ip}:{face_port}")
        return face_listener
        
    except Exception as e:
        logger.error(f"初始化人脸服务失败: {e}")
        return None


def init_sbus_monitor(msg_listener, voice_server, music_dir, node=None):
    from robot_voice.listener.sbus_controler import MusicPlayer, SbusMonitor
    assert os.path.exists(music_dir), music_dir
    file_list = list_files(music_dir, patterns=['*.mp3', '*.wav'], sort=True)
    if len(DEFAULT_VOICE_DIR) == 0:
        logger.info(f"未找到任何音频，无法启动遥控播报功能，跳过")
        return None
    
    logger.info(f"找到 {len(file_list)} 个音频，将按顺序播放:\n{file_list}")
    music_player = MusicPlayer(file_list=file_list,
                               msg_listener=msg_listener,
                               voice_server=voice_server)
    
    sbus_monitor = SbusMonitor(
        key_next_callback=music_player.on_key_next_change, 
        key_start_callback=music_player.on_key_start_change
    )
    
    # 订阅遥控消息
    # TODO, queue_size = 1，当前一个消息正在处理，其它消息丢弃，可能有丢消息的风险
    try:
        from sensor_msgs.msg import Joy
        if node is None:
            import rospy
            rospy.Subscriber('/sbus_data', Joy, sbus_monitor.on_subus_msg, queue_size=1) 
        else:
            sub = node.create_subscription(Joy, '/sbus_data', sbus_monitor.on_subus_msg, 1)
        
        logger.info("已启动遥控播报功能，用法：" \
            "\n1. `F键上拨和下拨`分别是上一首和下一首，初始音频序号是0，自动循环" \
            "\n2. `G键向左`开始播放音频，`G键自左回正`立刻静音" \
            "\n3. 当音频序号为0，`G键向左`开启语音交互，`G键自左回正`关闭语音交互")
    except Exception as err:
        logger.info(f"无法启动遥控播报功能，跳过: {err}")
        return None
    
    return sbus_monitor