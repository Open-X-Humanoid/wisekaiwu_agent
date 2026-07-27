#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
"""Unified Robot Actions Mock MCP Server.

Exposes ~23 tools covering home_living (spatial memory + grasp / place / handover) and
box_carry (initialize / scan / pick_up_box / put_box_to_table) workflows. All tool calls
route through ``MockResultProvider`` so test drivers can fully control return values.

Two complementary state machines:
  1. **Scenario** — selects which mock provider returns canned data
     (happy_path_fetch / memory_miss / grasp_fail_retry / box_carrying / ...)
  2. **Robot state** — tracks ``held_items`` / ``placed_items`` per process, so STATE
     CHECK violations (e.g. grasp while both hands full) surface as tool failures even
     when the scenario itself is a happy path.

Both can be inspected and overridden via the HTTP control port:
    POST  http://localhost:<control-port>/scenario   {"scenario": "memory_miss"}
    GET   http://localhost:<control-port>/scenario   -> {"scenario": "memory_miss"}
    GET   http://localhost:<control-port>/state      -> {"held_items": [...], "placed_items": {...}}
    POST  http://localhost:<control-port>/state      {"held_items": ["book"]}   # inject preset state
    POST  http://localhost:<control-port>/state/reset

Environment knobs:
    PHYSICAL_MOCK=1   simulate real robot latency on physical action tools
    VERBOSE_MOCK=1    bloat spatial_memory_query_vec returns (drives L1 compression tests)

Test hygiene:
    Robot state persists across user instructions in the same scenario (by design,
    for state-check tests). When agent yaml has `instruction_processor_cfg.robot_state_url`
    pointing here, stale state leaks into the LLM prompt as `<robot_state>` and pick /
    handover SKILL.md STATE CHECK will refuse ("hands already full") even when the
    physical hands are empty. Reset between e2e runs:

        curl -s -X POST http://localhost:<control-port>/state/reset

Usage:
    python robot_actions_mcp.py [--port 8000] [--control-port 8001]
                                [--scenario happy_path_fetch]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).parent))

from mock_tool_results import (  # noqa: E402
    MockResultProvider,
    box_carrying_mock,
    box_fail_retry_mock,
    box_workflow_mock,
    box_workflow_pick_fail_mock,
    box_workflow_scan_fail_mock,
    compound_failure_mock,
    context_accumulation_mock,
    fetch_and_place_mock,
    fetch_two_items_mock,
    grasp_fail_retry_mock,
    handover_fail_retry_mock,
    happy_path_fetch_mock,
    memory_miss_mock,
    move_fail_retry_mock,
    multi_task_mock,
    multi_waypoint_search_mock,
    perception_fail_retry_mock,
    place_down_fail_retry_mock,
    place_to_red_table_mock,
    scene_fail_mock,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, Any] = {
    "happy_path_fetch": happy_path_fetch_mock,
    "fetch_and_place": fetch_and_place_mock,
    "memory_miss": memory_miss_mock,
    "scene_fail": scene_fail_mock,
    "multi_task": multi_task_mock,
    "box_carrying": box_carrying_mock,
    "place_to_red_table": place_to_red_table_mock,
    "fetch_two_items": fetch_two_items_mock,
    "multi_waypoint_search": multi_waypoint_search_mock,
    "grasp_fail_retry": grasp_fail_retry_mock,
    "move_fail_retry": move_fail_retry_mock,
    "handover_fail_retry": handover_fail_retry_mock,
    "place_down_fail_retry": place_down_fail_retry_mock,
    "perception_fail_retry": perception_fail_retry_mock,
    "compound_failure": compound_failure_mock,
    "box_fail_retry": box_fail_retry_mock,
    "box_workflow": box_workflow_mock,
    "box_workflow_scan_fail": box_workflow_scan_fail_mock,
    "box_workflow_pick_fail": box_workflow_pick_fail_mock,
    "context_accumulation_stress": context_accumulation_mock,
}

_provider: MockResultProvider = happy_path_fetch_mock()
_provider_lock = threading.Lock()
_scenario_name: str = "happy_path_fetch"


def _set_provider(scenario: str) -> None:
    global _provider, _scenario_name
    factory = SCENARIOS.get(scenario)
    if not factory:
        raise ValueError(
            f"Unknown scenario: {scenario}. Available: {list(SCENARIOS)}"
        )
    with _provider_lock:
        _provider = factory()
        _scenario_name = scenario
    _reset_state()  # 切 scenario = 切测试场景, 状态归零


# ---------------------------------------------------------------------------
# Robot state tracker (held_items / placed_items)
# ---------------------------------------------------------------------------
# Lightweight stateful layer on top of MockResultProvider, so STATE CHECK rules in
# SKILL.md become observable: trying to grasp a second item while both hands are
# occupied will return failure even under happy_path scenarios.

_HANDS_CAPACITY = 2  # 双手机器人

_robot_state: dict[str, Any] = {
    "held_items": [],          # list[str], 最多 _HANDS_CAPACITY 个
    "placed_items": defaultdict(list),  # location -> [item, ...]
}
_state_lock = threading.Lock()


def _reset_state() -> None:
    with _state_lock:
        _robot_state["held_items"] = []
        _robot_state["placed_items"] = defaultdict(list)


def _state_snapshot() -> dict[str, Any]:
    with _state_lock:
        return {
            "held_items": list(_robot_state["held_items"]),
            "placed_items": {k: list(v) for k, v in _robot_state["placed_items"].items()},
        }


def _inject_state(payload: dict) -> None:
    """Force a specific state (e.g. for STATE CHECK tests)."""
    with _state_lock:
        if "held_items" in payload:
            _robot_state["held_items"] = list(payload["held_items"])[:_HANDS_CAPACITY]
        if "placed_items" in payload:
            _robot_state["placed_items"] = defaultdict(list, payload["placed_items"])


def _is_success(result: Any) -> bool:
    if isinstance(result, str):
        # handover returns plain strings like "SUCCESS: ..." / "ERROR: ..."
        return result.lstrip().upper().startswith("SUCCESS")
    if isinstance(result, dict):
        return (
            result.get("state") == "succeed"
            or result.get("status") == "success"
            or result.get("success") is True
        )
    return False


_GRASP_TOOLS = {"grasp_start", "pick_up_box", "fetch_box"}


def _state_precheck(tool_name: str, _args: dict) -> Optional[dict]:
    """Return an override result if the call violates a state invariant; else None."""
    with _state_lock:
        held = _robot_state["held_items"]

        if tool_name in _GRASP_TOOLS and len(held) >= _HANDS_CAPACITY:
            return {
                "state": "failed",
                "status": "failed",
                "msg": f"双手已持物({held}), 请先调用 place_down / handover 释放后再抓取",
                "message": f"双手已持物({held}), 请先调用 place_down / handover 释放后再抓取",
            }

        if tool_name in {"handover", "place_down", "place", "put_box_to_table", "put_box"} and not held:
            return {
                "state": "failed",
                "status": "failed",
                "msg": f"手中无物品, 调用 {tool_name} 无意义",
                "message": f"手中无物品, 调用 {tool_name} 无意义",
            }

    return None


def _state_postupdate(tool_name: str, args: dict, result: Any) -> None:
    """Mutate _robot_state to reflect a successful tool call."""
    if not _is_success(result):
        return
    with _state_lock:
        held = _robot_state["held_items"]
        placed = _robot_state["placed_items"]

        if tool_name == "grasp_start":
            item = args.get("item", "unknown")
            held.append(item)
        elif tool_name == "pick_up_box":
            held.append("box")
        elif tool_name == "fetch_box":
            target = args.get("target", "unknown")
            held.append(f"box_from_{target}")
        elif tool_name in {"place_down", "place"}:
            # 简化: 一次放下手里全部
            target = args.get("object_name") or "ground"
            for item in held:
                placed[target].append(item)
            held.clear()
        elif tool_name in {"put_box_to_table", "put_box"}:
            target = args.get("target", "table")
            for item in held:
                placed[target].append(item)
            held.clear()
        elif tool_name == "handover":
            for item in held:
                placed["user"].append(item)
            held.clear()
        elif tool_name == "release_hand":
            held.clear()


# ---------------------------------------------------------------------------
# Physical latency + verbose memory bloat (carried over from David)
# ---------------------------------------------------------------------------

_PHYSICAL_LATENCIES = {
    "move_to": 5.0,
    "move": 5.0,
    "navigate_to": 5.0,
    "grasp_start": 3.0,
    "pick_up_box": 3.0,
    "place_down": 2.0,
    "put_box_to_table": 2.0,
    "handover": 4.0,
    "fetch_box": 5.0,
    "put_box": 3.0,
    "reach_out": 3.0,
    "release_hand": 1.0,
    "back_station": 5.0,
    "scene_recognition": 0.5,
    "scan_table_with_box": 1.0,
    "perception_custom": 0.5,
    "spatial_memory_query_vec": 0.1,
    "delete_spatial_memory_by_id": 0.1,
    "trigger_spatial_processing": 1.0,
    "get_robot_pose": 0.05,
    "parameter_store": 0.05,
    "place_start": 0.5,
    "adjust_body_height": 1.0,
    "initialize": 1.0,
}

_PHYSICAL_MOCK = os.environ.get("PHYSICAL_MOCK", "1") == "1"
_VERBOSE_MOCK = os.environ.get("VERBOSE_MOCK", "0") == "1"


def _inflate_memory_item(item: dict, idx: int = 0) -> dict:
    """Bloat a memory item with verbose history/metadata (verbose context tests)."""
    out = dict(item)
    out["history"] = "\n".join(
        f"day -{d}: scanned at ({out.get('obj_x', 0):.2f}, {out.get('obj_y', 0):.2f}), "
        f"confidence {0.85 + (d % 10) * 0.01:.3f}, lighting natural_daylight"
        for d in range(30)
    )
    out["semantic_tags"] = [
        "可抓取", "可移动", "桌面物品", "食物", "新鲜", "厨房区域",
        "需轻拿轻放", "易破损", "建议双手取用", "光线下颜色稳定",
    ]
    out["related_items"] = [
        f"邻近物品_{j}: 距离 {0.3 + j * 0.15:.2f}m, 关联 0.{75 + j}"
        for j in range(15)
    ]
    out["metadata"] = {
        "scan_count": 12 + idx,
        "confidence": 0.91 + (idx * 0.001),
        "verified_by": ["spatial_scanner_v2", "depth_sensor_3d", "color_classifier"],
        "environment_context": {"room_id": "kitchen_001", "zone": f"zone_{idx}"},
    }
    return out


# ---------------------------------------------------------------------------
# Central dispatch
# ---------------------------------------------------------------------------

def _call(tool_name: str, args: dict) -> Any:
    """Pipeline: state precheck -> physical latency -> provider -> state update -> bloat."""
    args = {k: v for k, v in args.items() if v is not None}
    # override = _state_precheck(tool_name, args) # 长期运行很容易死锁，先不考虑这种状态更新。机器人身体的状态应该是基于视觉或者传感器实时检测的得到。
    # if override is not None:
    #     return override

    if _PHYSICAL_MOCK:
        time.sleep(_PHYSICAL_LATENCIES.get(tool_name, 0.1) * 1.5)

    with _provider_lock:
        result_str = _provider.get(tool_name, args)

    if isinstance(result_str, str):
        try:
            result = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            result = result_str
    else:
        result = result_str

    # _state_postupdate(tool_name, args, result) # 长期运行很容易死锁，先不考虑这种状态更新。机器人状态应该是给予检测的。

    if _VERBOSE_MOCK and tool_name == "spatial_memory_query_vec" and isinstance(result, list):
        result = [_inflate_memory_item(item, idx=i) for i, item in enumerate(result)]

    return result


# ---------------------------------------------------------------------------
# Control HTTP server
# ---------------------------------------------------------------------------

class _ControlHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid json"})
            return

        if self.path == "/scenario":
            try:
                _set_provider(body["scenario"])
                self._respond(200, {"ok": True, "scenario": body["scenario"]})
            except (ValueError, KeyError) as exc:
                self._respond(400, {"error": str(exc)})
        elif self.path == "/state":
            _inject_state(body)
            self._respond(200, {"ok": True, "state": _state_snapshot()})
        elif self.path == "/state/reset":
            _reset_state()
            self._respond(200, {"ok": True, "state": _state_snapshot()})
        else:
            self._respond(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/scenario":
            self._respond(200, {"scenario": _scenario_name})
        elif self.path == "/state":
            self._respond(200, _state_snapshot())
        elif self.path == "/scenarios":
            self._respond(200, {"available": list(SCENARIOS)})
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, code: int, body: dict):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002, A003
        # Suppress default HTTP access logs (chatty); rely on logger for important events.
        return


def _start_control_server(port: int) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), _ControlHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Control server listening on port %d", port)
    return server


# ---------------------------------------------------------------------------
# FastMCP tools — 23 unified actions
# ---------------------------------------------------------------------------

mcp = FastMCP(name="TianGong Robot Actions Mock MCP Server")


# === 移动 (3) ===

@mcp.tool()
def move(dst_point: dict[str, float]) -> dict[str, str]:
    """Move robot to the specified destination.

    Args:
        dst_point: Destination point to move to, {x: float, y: float, yaw: float}.

    Returns:
        dict: {'state': 'succeed' or 'failed', 'msg': '...'}.
    """
    return _call("move", {"dst_point": dst_point})


@mcp.tool()
def move_to(
    obj_x: float,
    obj_y: float,
    coordinate_x: float,
    coordinate_y: float,
    coordinate_z: float,
    coordinate_yaw: float,
) -> dict[str, str]:
    """导航到目标点位 (配合 spatial_memory_query_vec 的返回字段使用).

    Args:
        obj_x: 目标物体 x 坐标
        obj_y: 目标物体 y 坐标
        coordinate_x: 机器人到达点 x 坐标
        coordinate_y: 机器人到达点 y 坐标
        coordinate_z: 机器人到达点 z 坐标
        coordinate_yaw: 机器人到达点朝向
    """
    return _call(
        "move_to",
        {
            "obj_x": obj_x,
            "obj_y": obj_y,
            "coordinate_x": coordinate_x,
            "coordinate_y": coordinate_y,
            "coordinate_z": coordinate_z,
            "coordinate_yaw": coordinate_yaw,
        },
    )


@mcp.tool()
def back_station() -> dict[str, str]:
    """返回充电桩。"""
    return _call("back_station", {})


# === 身体 (2) ===

@mcp.tool()
def adjust_body_height(expected_height: float) -> dict[str, str]:
    """Adjust the height of robot body vertically."""
    return _call("adjust_body_height", {"expected_height": expected_height})


@mcp.tool()
def get_robot_pose() -> dict[str, str]:
    """获取当前机器人的位置。"""
    return _call("get_robot_pose", {})


# === 通用抓取 (5) ===

@mcp.tool()
def grasp_start(item: str) -> dict[str, str]:
    """Pick up the specified item.

    Args:
        item: 待抓取物品名称，**必须用英文**（如 'bottle'、'apple'、'yellow bottle'），禁止传中文。
    """
    return _call("grasp_start", {"item": item})


@mcp.tool()
def reach_out(
    position: list[float],
    object_name: Optional[str] = None,
) -> dict[str, str]:
    """Deliver the grasped object to the given position without releasing it.

    Args:
        position: [x, y, z] 目标位置坐标。
        object_name: 物品名称（用于状态跟踪），**必须用英文**（如 'apple'、'bottle'），禁止传中文。
    """
    return _call("reach_out", {"position": position, "object_name": object_name})


@mcp.tool()
def release_hand() -> dict[str, str]:
    """Open the robot's finger fully."""
    return _call("release_hand", {})


@mcp.tool()
def place(
    position: Optional[list[float]] = None,
    object_name: Optional[str] = None,
    drop: bool = True,
) -> dict[str, str]:
    """Place the grasped object on a 3D coordinate.

    Args:
        position: [x, y, z] target position.
        object_name: 物品名称（用于状态跟踪），**必须用英文**（如 'apple'、'bottle'），禁止传中文。
        drop: 是否松手 (本 mock 视为 True).
    """
    return _call("place", {"position": position, "object_name": object_name, "drop": drop})


@mcp.tool()
def place_start(position: str) -> dict[str, str]:
    """Place object at a quadrant position.

    Args:
        position: 'top_right' / 'bottom_right' / 'top_left' / 'bottom_left'.
    """
    return _call("place_start", {"position": position})


@mcp.tool()
def place_down() -> dict[str, str]:
    """将手中物品放置在目标点位 (依赖之前已 move 到目标位置)。"""
    return _call("place_down", {})


# === 递交 (1) ===

@mcp.tool()
def handover(
    hand: str = "auto",
    force_threshold: float = 5.0,
    timeout: float = 30.0,
    delay_after_release: float = 0.5,
    vel: float = 0.3,
    acc: float = 0.3,
) -> Any:
    """Full handover pipeline: detect hand → move to handover pose → wait for force-release → return arm.

    Args:
        hand: 'auto' / 'left' / 'right'.
        force_threshold: 触发释放的力阈值 (N).
        timeout: 等待释放最大秒数.
    """
    return _call(
        "handover",
        {
            "hand": hand,
            "force_threshold": force_threshold,
            "timeout": timeout,
            "delay_after_release": delay_after_release,
            "vel": vel,
            "acc": acc,
        },
    )


# === 空间记忆 (3) ===

@mcp.tool()
def spatial_memory_query_vec(
    obj_cn_name: str,
    color: Optional[str] = None,
    top_k: int = 10,
) -> list[dict]:
    """查找物品或目的地的位置坐标.

    Args:
        obj_cn_name: 要查找的物品或目的地名称，**用中文**（如 苹果、杯子、桌子、工作台、客厅）。
        color: 可选的颜色过滤，仅当用户明确指定了颜色时填写，按该颜色精确筛选（如 '红色'）。
        top_k: 返回结果数量上限。
    """
    return _call(
        "spatial_memory_query_vec",
        {"name": obj_cn_name, "color": color, "top_k": top_k},
    )


@mcp.tool()
def delete_spatial_memory_by_id(id_list: list[str]) -> dict:
    """根据 _id 列表从记忆中删除条目 (抓取成功后调用清理过期记忆)."""
    return _call("delete_spatial_memory_by_id", {"id_list": id_list})


@mcp.tool()
def trigger_spatial_processing(obj_name: str) -> dict[str, str]:
    """触发空间感知扫描, 更新空间记忆数据库。

    Args:
        obj_name: 物品名称，**必须用英文**（如 'apple'、'bottle'、'orange'），禁止传中文。
    """
    return _call("trigger_spatial_processing", {"obj_name": obj_name})


# === 感知 (2) ===

@mcp.tool()
def scene_recognition(target: str) -> dict[str, str]:
    """判断当前视野是否包含指定物品。

    Args:
        target: 待识别物品名称，**必须用英文**（如 'apple'、'bottle'、'table'），禁止传中文。
    """
    return _call("scene_recognition", {"target": target})


@mcp.tool()
def perception_custom() -> dict[str, Any]:
    """检测用户当前位置 (handover 前置).

    Returns:
        成功: {"state": "succeed", "msg": "...",
               "user_pose": {"obj_x": float, "obj_y": float,
                             "coordinate_x": float, "coordinate_y": float,
                             "coordinate_z": float, "coordinate_yaw": float}}
        失败: {"state": "failed", "msg": "未检测到用户位置"}

        user_pose 的 6 个字段可直接 splat 给 move_to(obj_x=..., obj_y=..., ...)。
    """
    return _call("perception_custom", {})


# === Box 一步式 (2) — 简化场景 ===

@mcp.tool()
def fetch_box(target: str) -> dict[str, str]:
    """搬起指定位置的箱子 (high-level, 内含 scan + pick).

    Args:
        target: 取箱子的位置，**必须用英文**（如 'table'），禁止传中文。
    """
    return _call("fetch_box", {"target": target})


@mcp.tool()
def put_box(target: str) -> dict[str, str]:
    """将箱子放到指定位置 (high-level, 内含 move + place).

    Args:
        target: 放置位置，**必须用英文**（如 'stack'、'table'），禁止传中文。
    """
    return _call("put_box", {"target": target})


# === Box 工艺 (4) — 工厂精细工艺 ===

@mcp.tool()
def initialize(init_pose: dict[str, float]) -> dict[str, Any]:
    """初始化机器人位姿和状态 (box 工艺第一步)."""
    return _call("initialize", {"init_pose": init_pose})


@mcp.tool()
def scan_table_with_box() -> dict[str, str]:
    """扫描桌面物品, 返回桌子和箱子坐标 (box 视觉算法)."""
    return _call("scan_table_with_box", {})


@mcp.tool()
def pick_up_box() -> dict[str, Any]:
    """抓起视野中的箱子 (依赖之前 scan_table_with_box 已扫描)."""
    return _call("pick_up_box", {})


@mcp.tool()
def put_box_to_table() -> dict[str, Any]:
    """放下手中的箱子到桌子上 (依赖之前已 move 到目标桌子)."""
    return _call("put_box_to_table", {})


# === 系统 (1) ===

@mcp.tool()
def parameter_store(
    action: str,
    key: Optional[str] = None,
    value: Optional[Any] = None,
    value_type: Optional[str] = None,
    params: Optional[dict] = None,
    param_types: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """读写运行参数 (set / get / list / batch_set)."""
    return _call(
        "parameter_store",
        {
            "action": action,
            "key": key,
            "value": value,
            "value_type": value_type,
            "params": params,
            "param_types": param_types,
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Robot Actions Mock MCP Server")
    parser.add_argument("--port", type=int, default=8000, help="FastMCP listen port")
    parser.add_argument("--control-port", type=int, default=8001, help="HTTP control port")
    parser.add_argument("--scenario", default="happy_path_fetch",
                        help=f"Initial scenario, one of: {list(SCENARIOS)}")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    _set_provider(args.scenario)
    _start_control_server(args.control_port)
    logger.info(
        "Robot actions MCP starting (port=%d, control=%d, scenario=%s, physical=%s, verbose=%s)",
        args.port, args.control_port, args.scenario, _PHYSICAL_MOCK, _VERBOSE_MOCK,
    )

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=args.port,
        log_level="INFO",
    )
