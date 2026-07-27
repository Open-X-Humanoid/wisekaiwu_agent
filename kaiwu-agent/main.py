#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
"""KaiwuOS CLI entry point — wires Gateway MessageBus with Agent layer."""

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

import yaml

from kaiwu.config.loader import (
    build_agent,
    build_channels,
    build_context,
    get_config_path,
    load_config,
    load_env_vars,
    load_model_config,
)
from kaiwu.config.robot_identity import resolve_robot_sn, select_robot_profile
from kaiwu.gateway.bus.channel_sender import init_channel_sender
from kaiwu.gateway.bus.events import InboundMessage
from kaiwu.gateway.bus.queue import MessageBus
from kaiwu.gateway.channels.manager import ChannelManager
from kaiwu.utils.logger import logger


def autoload_plugins():
    """扫描 main.py 同目录及子目录下的 .py 模块并 import，触发其中的
    @TOOLS / @CHANNELS.register_module() 等装饰器完成注册。

    这样新增自定义工具 / 通道时，只要把文件放到项目目录下（且用注册装饰器
    修饰），启动时即被自动加载，无需在本文件手写 import。
    """
    import importlib

    base = Path(__file__).resolve().parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))

    # 不该被扫描导入的目录：虚拟环境 / 框架源码包 / 配置 / 资源 / 缓存等
    skip_dirs = {
        ".venv", "venv", "env", ".git", "__pycache__", "kaiwu",
        "configs", "skills", "testbench", "docs", "output", "tests",
        "scripts", "examples", ".idea", ".vscode", "node_modules",
    }

    for py in sorted(base.rglob("*.py")):
        parts = py.relative_to(base).parts
        # 跳过被排除目录 / 隐藏目录下的文件
        if any(p in skip_dirs or p.startswith(".") for p in parts[:-1]):
            continue
        # 跳过入口文件自身与 dunder 文件（如 __init__.py）
        if py.name == "main.py" or py.name.startswith("__"):
            continue
        module_name = ".".join(parts)[:-3]  # 相对路径转点分模块名，去掉 .py 后缀
        try:
            importlib.import_module(module_name)
            logger.debug("Autoloaded plugin module: %s", module_name)
        except Exception:
            logger.exception("Failed to autoload plugin module: %s", module_name)


async def inbound_bridge(bus: MessageBus, agent):
    """MessageBus inbound → agent.preprocess_message (carry full metadata for outbound round-trip)."""
    logger.info("Inbound bridge started")
    while agent._running:
        try:
            # 等待第一条消息
            msg: InboundMessage = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
            messages = [msg]

            # 等 1 秒，期间如果收到新消息就重置计时，直到 1 秒内没有新输入
            while True:
                try:
                    extra = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
                    messages.append(extra)
                except asyncio.TimeoutError:
                    break

            # 合并所有消息内容
            combined_content = " ".join(m.content for m in messages)
            logger.info(f"Inbound message from {msg.channel}: {combined_content[:100]}...")
            meta = messages[-1].metadata or {}
            await agent.preprocess_message({
                "instruction": combined_content,
                "channel": msg.channel,
                "intent": meta.get("intent"),
                "user_name": meta.get("user_name"),
                "agent_id": msg.chat_id,
                "sid": meta.get("sid"),
                "metadata": meta,
            })
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in inbound bridge")
    logger.info("Inbound bridge stopped")


async def run(args: argparse.Namespace):
    """env/model → yaml load (1 次) → SN identity → context → cfg → channels/agent."""
    autoload_plugins()  # 自动发现并注册项目目录下的自定义工具 / 通道
    load_env_vars(args.env_config)
    model_cfg = load_model_config(args.model_config, args.model_server, args.model)

    cfg_path = Path(args.config) if args.config else get_config_path()
    raw_yaml = yaml.safe_load(open(cfg_path, encoding="utf-8")) if cfg_path.exists() else {}
    robot_ctx = select_robot_profile(raw_yaml.get("robot_identity"), resolve_robot_sn())

    context = build_context(model_cfg, robot_ctx)
    cfg = load_config(raw_data=raw_yaml, context=context)

    # ---- 初始化 skill 配置 ----
    if cfg.skills:
        from kaiwu.skills.skill_loader import configure_skills
        configure_skills(enabled=cfg.skills.enabled, disabled_skills=cfg.skills.disabled_skills)

    # ---- 记忆开关：yaml(personalization.memory) → 环境变量桥接 ----
    # 底层 memory_llm_gate 等模块读 os.getenv("MEMORY_LLM_*")；这里把 kaiwu.yaml 里的
    # 显式配置写进环境变量（仅在 yaml 显式给值时覆盖 .env，未配置则沿用 .env / 默认）。
    if cfg.personalization and cfg.personalization.memory:
        import os
        _mem = cfg.personalization.memory
        if _mem.llm_extract is not None:
            os.environ["MEMORY_LLM_EXTRACT"] = "1" if _mem.llm_extract else "0"
        if _mem.llm_gate is not None:
            os.environ["MEMORY_LLM_GATE"] = "1" if _mem.llm_gate else "0"
        logger.info("记忆开关(来自 kaiwu.yaml/.env): MEMORY_LLM_EXTRACT=%s MEMORY_LLM_GATE=%s",
                    os.getenv("MEMORY_LLM_EXTRACT", "(未设)"), os.getenv("MEMORY_LLM_GATE", "(未设)"))

    # ---- 初始化个性化存储（kaiwu.yaml personalization.storage.enabled=true 时激活） ----
    if cfg.personalization and cfg.personalization.storage.enabled:
        try:
            from kaiwu.personalization.storage.baidu_cloud import (
                create_baidu_cloud_storage,
                set_global_storage,
            )
            pers_dict = cfg.personalization.model_dump()
            storage = create_baidu_cloud_storage(config=pers_dict)
            if storage.initialize():
                set_global_storage(storage)
                # 输出各后端状态，方便排查云端同步问题
                rds_ok = storage.rds_memory_store is not None and storage.rds_memory_store.is_available()
                dbv_ok = storage.dbvector_store is not None and storage.dbvector_store.is_available()
                bos_ok = storage.bos_storage is not None and storage.bos_storage.is_available()
                logger.info("Personalization storage initialized — RDS=%s DBVector=%s BOS=%s",
                            "OK" if rds_ok else "FAIL", "OK" if dbv_ok else "FAIL", "OK" if bos_ok else "FAIL")
            else:
                logger.warning("Personalization storage init failed, continuing without it")
        except Exception:
            logger.exception("Personalization storage init failed, continuing without it")

    bus = MessageBus()
    init_channel_sender(bus)

    channels = build_channels(cfg.gateway, bus=bus)
    manager = ChannelManager(config=cfg.gateway, bus=bus)
    for ch in channels.values():
        manager.register_channel(ch)
    await manager.start_all()

    agent = build_agent(cfg.agent, bus=bus, context=context, skill_dir=args.skill_dir)
    bridge_task = None
    if agent is not None:
        agent.start()
        bridge_task = asyncio.create_task(inbound_bridge(bus, agent))
    else:
        logger.error("No agent configured — inbound messages will not be processed")

    # -- Wait for shutdown signal --
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    _force_exit = False

    def signal_handler():
        nonlocal _force_exit
        if _force_exit:
            logger.warning("Force exit")
            os._exit(1)
        _force_exit = True
        logger.info("Received shutdown signal (press again to force exit)")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            signal.signal(sig, lambda *_: signal_handler())

    await stop_event.wait()

    # -- Graceful shutdown --
    logger.info("Shutting down...")
    if bridge_task:
        bridge_task.cancel()
        try:
            await bridge_task
        except asyncio.CancelledError:
            pass
    if agent is not None:
        agent.stop()
    await manager.stop_all()
    logger.info("Shutdown complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KaiwuOS Agent Runtime")
    parser.add_argument("-c", "--config", type=str, default=None,
                        help="Agent config file (default: auto-detect configs/kaiwu.yaml)")
    parser.add_argument("-mc", "--model-config", type=str, default="configs/model.yaml",
                        help="Model server config file")
    parser.add_argument("-ms", "--model-server", type=str, default="pelican-thinking",
                        help="Model server name from model.yaml")
    parser.add_argument("-m", "--model", type=str, default=None,
                        help="Override model name")
    parser.add_argument("-ec", "--env-config", type=str, default=".env",
                        help="Environment variables file")
    parser.add_argument("--skill-dir", type=str, default=None,
                        help="Additional skill directory (appended after built-in and project skills)")
    return parser.parse_args()


def main():
    """Entry point for `kaiwu` CLI."""
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Fatal error in main loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
