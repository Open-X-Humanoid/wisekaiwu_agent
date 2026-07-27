#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连接 MCP server 并打印其暴露的 tools。

从 configs/kaiwu.yaml 读取 mcp_cfg，复用 agent 运行时同款的
MultiServerMCPClient 连接，列出每个 server 的工具名/描述/参数。

用法:
    python scripts/print_mcp_tools.py                  # 默认读 configs/kaiwu.yaml
    python scripts/print_mcp_tools.py -c path/to.yaml  # 指定配置文件
    python scripts/print_mcp_tools.py --schema         # 同时打印参数 JSON Schema
    python scripts/print_mcp_tools.py --openai         # 打印发给 LLM 的 OpenAI tool 定义
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_mcp_adapters.client import MultiServerMCPClient

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "configs" / "kaiwu.yaml"


def load_mcp_cfg(config_path: Path) -> dict:
    if not config_path.exists():
        sys.exit(f"配置文件不存在: {config_path}")
    with config_path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    mcp_cfg = cfg.get("mcp_cfg")
    if not mcp_cfg:
        sys.exit(f"{config_path} 中没有找到 mcp_cfg（可能被注释掉了）")
    return mcp_cfg


def _input_schema(tool) -> dict:
    """取工具完整的 JSON Schema（含 required、defaults 等顶层信息）。"""
    schema = getattr(tool, "args_schema", None)
    if isinstance(schema, dict):
        return schema
    if schema is not None:
        for attr in ("model_json_schema", "schema"):
            fn = getattr(schema, attr, None)
            if callable(fn):
                try:
                    return fn()
                except Exception:
                    pass
    props = getattr(tool, "args", None)
    return {"properties": props} if isinstance(props, dict) else {}


def _describe_param(name: str, spec: dict, required: bool) -> list[str]:
    """把单个参数的定义/说明整理成多行文本。"""
    if not isinstance(spec, dict):
        spec = {}
    type_str = spec.get("type")
    if not type_str:
        if "anyOf" in spec:
            type_str = " | ".join(
                str(s.get("type", "?")) for s in spec["anyOf"] if isinstance(s, dict)
            )
        elif "enum" in spec:
            type_str = "enum"
        else:
            type_str = "?"
    flag = "必填" if required else "可选"
    lines = [f"      - {name} ({type_str}, {flag})"]

    pdesc = (spec.get("description") or spec.get("title") or "").strip()
    if pdesc:
        lines.append(f"          说明: {pdesc}")
    if "enum" in spec:
        lines.append(f"          可选值: {spec['enum']}")
    if "default" in spec:
        lines.append(f"          默认值: {spec['default']!r}")
    items = spec.get("items")
    if isinstance(items, dict) and items.get("type"):
        lines.append(f"          元素类型: {items['type']}")
    return lines


async def run(mcp_cfg: dict, show_schema: bool, show_openai: bool) -> None:
    print(f"共 {len(mcp_cfg)} 个 MCP server:")
    for name, server in mcp_cfg.items():
        url = server.get("url", server.get("command", "?"))
        print(f"  - {name}: {url} ({server.get('transport', '?')})")
    print()

    client = MultiServerMCPClient(mcp_cfg)
    tools = await client.get_tools()

    print(f"共 {len(tools)} 个 tools:\n")
    for i, tool in enumerate(tools, 1):
        print(f"[{i}] {tool.name}")
        desc = (tool.description or "").strip()
        if desc:
            print(f"    描述: {desc}")

        schema = _input_schema(tool)
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])

        if props:
            req_list = sorted(p for p in props if p in required)
            opt_list = sorted(p for p in props if p not in required)
            print(f"    参数: 共 {len(props)} 个"
                  f"（必填 {len(req_list)}, 可选 {len(opt_list)}）")
            print(f"    必填参数: {', '.join(req_list) if req_list else '无'}")
            print("    参数定义:")
            for pname, pspec in props.items():
                for line in _describe_param(pname, pspec, pname in required):
                    print(line)
        else:
            print("    参数: 无")

        if show_schema:
            print("    完整 schema: " + json.dumps(schema, ensure_ascii=False, indent=6))

        if show_openai:
            try:
                openai_tool = convert_to_openai_tool(tool)
                print("    OpenAI tool 定义 (发给 LLM 的 schema):")
                print(json.dumps(openai_tool, ensure_ascii=False, indent=6))
            except Exception as err:
                print(f"    OpenAI tool 定义转换失败: {err}")
        print()

    if show_openai:
        print("=" * 60)
        print("以下为 create_agent/bind_tools 实际传给 LLM 的完整 tools 列表:\n")
        all_openai = []
        for tool in tools:
            try:
                all_openai.append(convert_to_openai_tool(tool))
            except Exception as err:
                all_openai.append({"name": getattr(tool, "name", "?"), "_error": str(err)})
        print(json.dumps(all_openai, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="连接并打印 MCP tools")
    parser.add_argument(
        "-c", "--config", type=Path, default=DEFAULT_CONFIG,
        help=f"配置文件路径 (默认: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--schema", action="store_true", help="同时打印每个工具的参数 JSON Schema",
    )
    parser.add_argument(
        "--openai", action="store_true",
        help="打印 create_agent/bind_tools 实际发给 LLM 的 OpenAI tool 定义",
    )
    args = parser.parse_args()

    mcp_cfg = load_mcp_cfg(args.config)
    try:
        asyncio.run(run(mcp_cfg, args.schema, args.openai))
    except Exception as err:
        sys.exit(f"连接 MCP 失败，请确认 MCP server 已启动并检查 mcp_cfg: {err}")


if __name__ == "__main__":
    main()
