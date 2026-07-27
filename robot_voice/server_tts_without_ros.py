# -*- coding: utf-8 -*-
#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import argparse
from configs.server_cfg import get_msg_listener, get_common_args_parser
from robot_voice.utils.log import setup_logger
from dotenv import load_dotenv

def main(args):
    # 读取语音识别结果的topic
    msg_listener, voice_server, _ = get_msg_listener(
        mode=None,
        voice_publisher=None,
        tts_version=args.tts,
        voice_id=args.voice,
        speech_rate=args.speech_rate,
        volume=args.volume,
    )
    
    # 启动语音服务，这会让主程序常驻，直到遇到 ctrl-c
    voice_server.start()
    
    # 清理
    voice_server.stop()
    msg_listener.stop()
    logger.info("语音服务端正常退出")
    

if __name__ == '__main__':
    logger = setup_logger()
    logger.info("logger setup done.")
    # 解析参数
    parser = get_common_args_parser()
    args = parser.parse_args()
    load_dotenv(dotenv_path=args.env_config)
    main(args)
