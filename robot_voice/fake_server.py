# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
from robot_voice.utils.log import setup_logger
import json
import threading
import argparse
from dotenv import load_dotenv
from robot_voice.utils.voice_server import VoiceSocketServer
from robot_voice.utils.tictok import tic
from configs.server_cfg import get_msg_listener, VOICE_MODES, get_common_args_parser


def input_wrapper(voice_server):
    def input_from_terminal():
        while True:
            try:
                instruction = input('请输入指令: ')
                if not instruction.strip():  # 检查空输入
                    continue
                tic(timer_id="iat_end_2_tts_begin")
                message = {"instruction": instruction, "intent": None}
                msg_str = json.dumps(message)
                # broadcast_voice expects a string message
                voice_server.broadcast_voice(message=msg_str)
            except UnicodeDecodeError:
                logger.info("输入有误，请重新输入")
            except EOFError:
                logger.info("输入结束，退出程序")
                break
            except KeyboardInterrupt:
                logger.info("用户中断，退出程序")
                break
            except Exception as e:
                logger.error(f"处理输入时发生错误: {e}")
    return input_from_terminal
                

def main(args):
    voice_publisher = None
    if not args.disable_tts:
        tts_version = args.tts
        if args.tts in ('xftts'):
            import rospy
            # 新建一个我们自己的ros node，node名称是自定义的，不是去找现有节点，下面根据话题发布或监听即可
            # 如果选择不匿名，会把其它同名的node挤下线
            # Node's name cannot contain namespaces (i.e. '/')
            rospy.init_node('robot_voice', anonymous=True) 
            
            # 播放语音的topic
            # queue_size决定了发送频率，高出则会被丢弃
            
            from std_msgs.msg import String
            voice_publisher = rospy.Publisher('/xunfei/tts_play', String, queue_size=10)
    else:
        tts_version = None
    
    # 读取语音识别结果的topic，现在返回三个组件
    msg_listener, voice_server, msg_processor = get_msg_listener(
        mode=VOICE_MODES.ONLINE_ASR_XF_SKILL,
        voice_publisher=voice_publisher,
        tts_version=tts_version,
        voice_id=args.voice,
        port=args.port,
        speech_rate=args.speech_rate,
        volume=args.volume,
    )

    receiver_thread = threading.Thread(target=input_wrapper(voice_server))
    # 设置守护线程
    receiver_thread.daemon = True
    receiver_thread.start()
    
    # 启动语音消息监听器
    logger.info("正在启动语音消息监听器...")
    msg_listener.start()
    logger.info("语音消息监听器已启动")
    
    # 启动语音服务，这会让主程序常驻，直到遇到 ctrl-c
    logger.info("正在启动语音WebSocket服务器...")
    voice_server.start()
    
    # 清理资源
    logger.info("正在清理资源...")
    voice_server.stop()
    msg_listener.stop()
    logger.info("语音服务端正常退出")


if __name__ == '__main__':
    logger = setup_logger()
    logger.info("logger setup done.")

    parser = get_common_args_parser()
    args = parser.parse_args()

    load_dotenv(dotenv_path=args.env_config)
    main(args)
