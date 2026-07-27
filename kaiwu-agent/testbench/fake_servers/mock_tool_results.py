"""Mock tool return values and providers for different test scenarios."""

import json
import re
from collections import defaultdict
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Standard mock data
# ---------------------------------------------------------------------------

MEMORY_ITEM_APPLE = {
    "_id": "test_id_apple_001",
    "type": "object",
    "name": "苹果",
    "obj_x": 1.41,
    "obj_y": -4.33,
    "coordinate_x": 1.83,
    "coordinate_y": -3.77,
    "coordinate_z": 0.65,
    "coordinate_yaw": -2.22,
    "property": "红色苹果",
    "status": "放置在桌面上",
    "color": "红色",
    "desp": "一个红色苹果",
    "similarity_score": 0.88,
}

MEMORY_ITEM_BOTTLE = {
    "_id": "test_id_bottle_001",
    "type": "object",
    "name": "瓶子",
    "obj_x": 2.10,
    "obj_y": -3.85,
    "coordinate_x": 2.55,
    "coordinate_y": -3.20,
    "coordinate_z": 0.72,
    "coordinate_yaw": -1.95,
    "property": "绿色饮料瓶",
    "status": "放置在桌面上",
    "color": "绿色",
    "desp": "一个绿色饮料瓶",
    "similarity_score": 0.82,
}

MEMORY_ITEM_ORANGE = {
    "_id": "test_id_orange_001",
    "type": "object",
    "name": "橙子",
    "obj_x": 1.65,
    "obj_y": -4.10,
    "coordinate_x": 2.00,
    "coordinate_y": -3.55,
    "coordinate_z": 0.60,
    "coordinate_yaw": -2.10,
    "property": "新鲜橙子",
    "status": "放置在桌面上",
    "color": "橙色",
    "desp": "一个新鲜橙子",
    "similarity_score": 0.90,
}

MEMORY_ITEM_CUP = {
    "_id": "test_id_cup_001",
    "type": "object",
    "name": "杯子",
    "obj_x": 1.30,
    "obj_y": -4.50,
    "coordinate_x": 1.75,
    "coordinate_y": -3.90,
    "coordinate_z": 0.68,
    "coordinate_yaw": -2.30,
    "property": "白色杯子",
    "status": "放置在桌面上",
    "color": "白色",
    "desp": "一个白色杯子",
    "similarity_score": 0.86,
}

MEMORY_ITEM_TABLE_WHITE = {
    "_id": "test_id_table_white_001",
    "type": "furniture",
    "name": "桌子",
    "obj_x": 1.50,
    "obj_y": -5.00,
    "coordinate_x": 1.90,
    "coordinate_y": -4.40,
    "coordinate_z": 0.70,
    "coordinate_yaw": -2.15,
    "property": "白色桌子",
    "status": "固定家具",
    "color": "白色",
    "desp": "一张白色的桌子",
    "similarity_score": 0.92,
}

MEMORY_ITEM_TABLE_RED = {
    "_id": "test_id_table_red_001",
    "type": "furniture",
    "name": "桌子",
    "obj_x": 2.30,
    "obj_y": -5.20,
    "coordinate_x": 2.70,
    "coordinate_y": -4.60,
    "coordinate_z": 0.70,
    "coordinate_yaw": -2.00,
    "property": "红色桌子",
    "status": "固定家具",
    "color": "红色",
    "desp": "一张红色的桌子",
    "similarity_score": 0.91,
}

MEMORY_ITEM_WATER_BOTTLE = {
    "_id": "test_id_water_001",
    "type": "object",
    "name": "水瓶",
    "obj_x": 1.95,
    "obj_y": -4.05,
    "coordinate_x": 2.40,
    "coordinate_y": -3.45,
    "coordinate_z": 0.70,
    "coordinate_yaw": -2.05,
    "property": "透明水瓶",
    "status": "放置在桌面上",
    "color": "透明",
    "desp": "一个透明的水瓶",
    "similarity_score": 0.85,
}

MEMORY_ITEM_SNACK = {
    "_id": "test_id_snack_001",
    "type": "object",
    "name": "零食",
    "obj_x": 1.55,
    "obj_y": -4.25,
    "coordinate_x": 1.95,
    "coordinate_y": -3.70,
    "coordinate_z": 0.62,
    "coordinate_yaw": -2.18,
    "property": "袋装零食",
    "status": "放置在桌面上",
    "color": "红色",
    "desp": "一袋零食",
    "similarity_score": 0.80,
}

MEMORY_ITEM_REMOTE = {
    "_id": "test_id_remote_001",
    "type": "object",
    "name": "遥控器",
    "obj_x": 2.20,
    "obj_y": -4.70,
    "coordinate_x": 2.60,
    "coordinate_y": -4.10,
    "coordinate_z": 0.55,
    "coordinate_yaw": -2.00,
    "property": "电视遥控器",
    "status": "放置在沙发上",
    "color": "黑色",
    "desp": "一个黑色的电视遥控器",
    "similarity_score": 0.83,
}

# ---------------------------------------------------------------------------
# Extra fruit items for context_accumulation_stress scenario
# ---------------------------------------------------------------------------
def _make_fruit_item(idx: int, cn_name: str, en_name: str, color_cn: str, color_en: str) -> dict:
    """生成水果 item（坐标分散在场景里，避免互相冲突）。"""
    return {
        "_id": f"test_id_{en_name}_{idx:03d}",
        "type": "object",
        "name": cn_name,
        "obj_x": 1.0 + (idx % 5) * 0.5,
        "obj_y": -3.0 - (idx // 5) * 0.8,
        "coordinate_x": 1.5 + (idx % 5) * 0.5,
        "coordinate_y": -2.5 - (idx // 5) * 0.8,
        "coordinate_z": 0.6,
        "coordinate_yaw": -2.1,
        "property": f"新鲜的{color_cn}{cn_name}",
        "status": "放置在桌面上",
        "color": color_cn,
        "desp": f"一个新鲜的{color_cn}{cn_name}，看起来很好吃",
        "similarity_score": 0.90,
    }

MEMORY_ITEM_BANANA = _make_fruit_item(0, "香蕉", "banana", "黄色", "yellow")
MEMORY_ITEM_GRAPE = _make_fruit_item(1, "葡萄", "grape", "紫色", "purple")
MEMORY_ITEM_PEACH = _make_fruit_item(2, "桃子", "peach", "粉色", "pink")
MEMORY_ITEM_PEAR = _make_fruit_item(3, "梨", "pear", "黄绿色", "yellow-green")
MEMORY_ITEM_CHERRY = _make_fruit_item(4, "樱桃", "cherry", "深红色", "dark red")
MEMORY_ITEM_MANGO = _make_fruit_item(5, "芒果", "mango", "橙黄色", "orange-yellow")
MEMORY_ITEM_PINEAPPLE = _make_fruit_item(6, "菠萝", "pineapple", "金黄色", "golden")
MEMORY_ITEM_WATERMELON = _make_fruit_item(7, "西瓜", "watermelon", "深绿色", "dark green")
MEMORY_ITEM_LEMON = _make_fruit_item(8, "柠檬", "lemon", "黄色", "yellow")
MEMORY_ITEM_COCONUT = _make_fruit_item(9, "椰子", "coconut", "棕色", "brown")
MEMORY_ITEM_DRAGONFRUIT = _make_fruit_item(10, "火龙果", "dragonfruit", "玫红色", "rose")
MEMORY_ITEM_STRAWBERRY = _make_fruit_item(11, "草莓", "strawberry", "鲜红色", "bright red")
MEMORY_ITEM_BLUEBERRY = _make_fruit_item(12, "蓝莓", "blueberry", "深蓝色", "deep blue")


# ---------------------------------------------------------------------------
# 扫描登记表：trigger_spatial_processing(obj_name=英文) -> 对应 memory item。
# 用于 scan -> query 联动：扫描英文物名后，能按物品的中文 name 被 query 命中。
# 多词名 (例 'yellow bottle') 走子串匹配回落到这里的某个 key。
# ---------------------------------------------------------------------------
_SCAN_ITEM_REGISTRY: dict[str, dict] = {
    "apple": MEMORY_ITEM_APPLE,
    "orange": MEMORY_ITEM_ORANGE,
    "cup": MEMORY_ITEM_CUP,
    "table": MEMORY_ITEM_TABLE_WHITE,
    "water bottle": MEMORY_ITEM_WATER_BOTTLE,
    "water": MEMORY_ITEM_WATER_BOTTLE,
    "bottle": MEMORY_ITEM_BOTTLE,
    "drink": MEMORY_ITEM_BOTTLE,
    "snack": MEMORY_ITEM_SNACK,
    "remote": MEMORY_ITEM_REMOTE,
    "banana": MEMORY_ITEM_BANANA,
    "grape": MEMORY_ITEM_GRAPE,
    "peach": MEMORY_ITEM_PEACH,
    "pear": MEMORY_ITEM_PEAR,
    "cherry": MEMORY_ITEM_CHERRY,
    "mango": MEMORY_ITEM_MANGO,
    "pineapple": MEMORY_ITEM_PINEAPPLE,
    "watermelon": MEMORY_ITEM_WATERMELON,
    "lemon": MEMORY_ITEM_LEMON,
    "coconut": MEMORY_ITEM_COCONUT,
    "dragonfruit": MEMORY_ITEM_DRAGONFRUIT,
    "strawberry": MEMORY_ITEM_STRAWBERRY,
    "blueberry": MEMORY_ITEM_BLUEBERRY,
}


def _synthesize_scan_item(obj_name: str) -> dict:
    """为未登记的物名合成一个可信的 memory item，保证“扫到啥就能查到啥”。"""
    return {
        "_id": f"scanned_{abs(hash(obj_name)) % 100000:05d}",
        "type": "object",
        "name": obj_name,
        "obj_x": 1.50,
        "obj_y": -4.20,
        "coordinate_x": 1.90,
        "coordinate_y": -3.65,
        "coordinate_z": 0.65,
        "coordinate_yaw": -2.15,
        "property": f"扫描检测到的{obj_name}",
        "status": "放置在桌面上",
        "color": "",
        "desp": f"空间感知扫描检测到的 {obj_name}",
        "similarity_score": 0.80,
    }


def _resolve_scan_item(obj_name: str) -> dict:
    """英文物名 -> memory item：先精确命中登记表，再子串回落，最后合成。"""
    key = obj_name.lower().strip()
    if key in _SCAN_ITEM_REGISTRY:
        return _SCAN_ITEM_REGISTRY[key]
    for registered, item in _SCAN_ITEM_REGISTRY.items():
        if registered in key:
            return item
    return _synthesize_scan_item(obj_name)


MOVE_SUCCESS = {"state": "succeed", "msg": "已经移动到目的地"}
MOVE_FAILED = {"state": "failed", "msg": "导航失败，路径被阻挡"}
GRASP_OUT_OF_RANGE = {"status": "failed", "message": "超出操作范围"}
GRASP_FAILED = {"status": "failed", "message": "抓取失败，未能稳定抓取物品"}
PERCEPTION_CUSTOM_SUCCESS = {
    "state": "succeed",
    "msg": "找到用户位置",
    "user_pose": {
        "obj_x": 5.0,
        "obj_y": 3.0,
        "coordinate_x": 4.8,
        "coordinate_y": 2.9,
        "coordinate_z": 0.65,
        "coordinate_yaw": 0.0,
    },
}
PERCEPTION_CUSTOM_FAILED = {"state": "failed", "msg": "未检测到用户位置"}
HANDOVER_SUCCESS = "SUCCESS: auto hand – force-release detected, arm returned home."
HANDOVER_FAILED = "ERROR: force-release timeout – no pull detected within 30 s."
PLACE_DOWN_SUCCESS = {"state": "succeed", "msg": ""}
PLACE_DOWN_FAILED = {"state": "failed", "msg": "放置失败，目标位置不可达"}
FETCH_BOX_SUCCESS = {"state": "succeed", "msg": "已从 table 搬起箱子"}
FETCH_BOX_FAILED = {"state": "failed", "msg": "未能搬起箱子，位置偏移"}
PUT_BOX_SUCCESS = {"state": "succeed", "msg": "已将箱子放到 stack"}
PUT_BOX_FAILED = {"state": "failed", "msg": "放置箱子失败"}


# ---------------------------------------------------------------------------
# MockResultProvider
# ---------------------------------------------------------------------------

class MockResultProvider:
    """Provides mock results for tool calls with support for sequencing and conditions."""

    def __init__(self):
        self._defaults: dict[str, Any] = {}
        self._sequences: dict[str, list] = {}
        self._conditional: dict[str, Callable] = {}
        self._call_counts: dict[str, int] = defaultdict(int)
        # 动态空间记忆：trigger_spatial_processing 扫描成功后写入，
        # spatial_memory_query_vec 命中不到静态 items_map 时作为兜底来源查询。
        # key 同时按中文名 (item['name']) 和英文 obj_name 索引，兼容中/英查询。
        self.scanned_memory: dict[str, list] = {}
        # 最近一次扫描到的物品。未登记物体 (走 _synthesize_scan_item) 只有英文名，
        # 跨语言查询 (扫 obj_name=英文，再用 name=中文 query) 按 key 匹配命中不到，
        # 此时回落到"刚扫到的那个物品"，兑现"扫到啥就能查到啥"。
        self._last_scanned: list = []

    def set_default(self, tool_name: str, result: Any) -> "MockResultProvider":
        self._defaults[tool_name] = result
        return self

    def set_sequence(self, tool_name: str, results: list) -> "MockResultProvider":
        """Return results[i] on the (i+1)-th call; reuse last element after exhaustion.
        Clears any existing conditional for this tool so the sequence takes effect."""
        self._sequences[tool_name] = results
        self._conditional.pop(tool_name, None)
        return self

    def set_conditional(self, tool_name: str, fn: Callable[[dict], Any]) -> "MockResultProvider":
        """Set a function (args_dict) -> result for dynamic responses.
        Clears any existing sequence for this tool so the conditional takes effect."""
        self._conditional[tool_name] = fn
        self._sequences.pop(tool_name, None)
        return self

    def get(self, tool_name: str, arguments: dict | None = None) -> str:
        self._call_counts[tool_name] += 1
        count = self._call_counts[tool_name]

        if tool_name in self._sequences:
            seq = self._sequences[tool_name]
            idx = min(count - 1, len(seq) - 1)
            result = seq[idx]
        elif tool_name in self._conditional:
            result = self._conditional[tool_name](arguments or {})
        elif tool_name in self._defaults:
            result = self._defaults[tool_name]
        else:
            result = {"state": "succeed", "msg": ""}

        if callable(result):
            result = result(arguments or {})

        args = arguments or {}
        # 扫描成功 -> 把检测到的物品登记进动态空间记忆，让后续 query 能查到。
        if tool_name == "trigger_spatial_processing":
            self._record_scan(args, result)
        # query 命中不到本场景静态 items_map（返回空）时，回落到“刚扫描到”的记忆。
        # 仅对 conditional 型 query 生效；sequence 型场景 (memory_miss /
        # multi_waypoint_search) 保留其“扫描后仍查不到”的脚本化语义。
        elif (
            tool_name == "spatial_memory_query_vec"
            and tool_name in self._conditional
            and self._is_empty_result(result)
        ):
            fallback = self._query_scanned_memory(args)
            if fallback:
                result = fallback

        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)

    # ------------------------- scan <-> query 联动 ------------------------ #
    @staticmethod
    def _is_empty_result(result: Any) -> bool:
        if isinstance(result, list):
            return len(result) == 0
        if isinstance(result, str):
            return result.strip() in ("", "[]")
        return False

    @staticmethod
    def _scan_succeeded(result: Any) -> bool:
        data = result
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return bool(data.strip())
        if isinstance(data, dict):
            return data.get("state") == "succeed" or data.get("status") == "success"
        return False

    def _record_scan(self, args: dict, result: Any) -> None:
        obj_name = str(args.get("obj_name") or "").strip()
        if not obj_name or not self._scan_succeeded(result):
            return
        item = _resolve_scan_item(obj_name)
        cn_name = item.get("name") or obj_name
        # 双索引：中文名（query 常用）+ 英文 obj_name（兼容英文 query）。
        self.scanned_memory[cn_name] = [item]
        self.scanned_memory[obj_name.lower()] = [item]
        self._last_scanned = [item]

    def _query_scanned_memory(self, args: dict) -> list:
        combined = (
            f"{args.get('name', '')} {args.get('query', '')} {args.get('color', '')}"
        ).lower()
        tokens = set(re.findall(r"[a-z0-9]+", combined))
        for key, items in self.scanned_memory.items():
            if not key:
                continue
            k = key.lower()
            if k.isascii():
                # 英文 key 走整词匹配，避免 'apple' ⊂ 'pineapple' 这类子串误命中。
                if all(tok in tokens for tok in k.split()):
                    return items
            elif k in combined:
                # 中文 (CJK) key 用子串匹配，与静态 items_map 行为一致。
                return items
        # 按 key 匹配不到，但本轮刚扫描过物品：回落到最近一次扫描结果。
        # 解决"扫英文 obj_name → 用中文 name query"这类跨语言/未登记物体查不到的问题。
        return list(self._last_scanned)


# ---------------------------------------------------------------------------
# Memory query handler builder
# ---------------------------------------------------------------------------

def _memory_query_handler(items_map: dict[str, list]) -> Callable:
    """Build a handler that matches the 'name' / 'query' argument against keys in items_map.

    No-match fallback: return `[]` (empty list). This makes the mock honest — LLM should
    then trigger spatial_memory_processing or report not-found, instead of being fed an
    arbitrary fixture and getting confused (which used to send long sessions into a loop
    querying "工作台" / "workbench" while mock kept returning the water bottle).
    """

    def handler(args: dict) -> list:
        name = args.get("name", "")
        query = args.get("query", "")
        color = args.get("color", "")
        combined = f"{name} {query} {color}"
        for key, items in items_map.items():
            if key in combined:
                return items
        return []  # honest "not found"

    return handler


# ---------------------------------------------------------------------------
# Pre-configured mock providers for common scenarios
# ---------------------------------------------------------------------------

def _apply_common_defaults(p: MockResultProvider) -> None:
    """Register default success results for all common tools."""
    # 移动
    p.set_default("move_to", MOVE_SUCCESS)
    p.set_default("move", MOVE_SUCCESS)
    p.set_default("back_station", {"state": "succeed", "msg": "已回到充电桩"})
    # 身体
    p.set_default("adjust_body_height", {"state": "succeed", "msg": ""})
    p.set_default(
        "get_robot_pose",
        {"state": "succeed", "msg": '{"x": 0.0, "y": 0.0, "yaw": 0.0}'},
    )
    # 感知
    p.set_conditional(
        "scene_recognition",
        lambda a: {"state": "succeed", "msg": f"当前位置有{a.get('target', '物品')}"},
    )
    p.set_default("perception_custom", PERCEPTION_CUSTOM_SUCCESS)
    # 抓取通用
    p.set_conditional(
        "grasp_start",
        lambda a: {"status": "success", "message": f"执行任务: {a.get('item', 'item')}"},
    )
    p.set_default("reach_out", {"state": "succeed", "msg": ""})
    p.set_default("release_hand", {"state": "succeed", "msg": ""})
    p.set_default("place", {"state": "succeed", "msg": ""})
    p.set_default("place_start", {"state": "succeed", "msg": ""})
    p.set_default("place_down", PLACE_DOWN_SUCCESS)
    # 递交
    p.set_default("handover", HANDOVER_SUCCESS)
    # 空间记忆
    p.set_conditional(
        "delete_spatial_memory_by_id",
        lambda a: {
            "state": "succeed",
            "msg": f"已删除 {len(a.get('id_list', []))} 条过期记忆，请继续执行下一步操作",
            "deleted_count": len(a.get("id_list", [])),
        },
    )
    p.set_conditional(
        "trigger_spatial_processing",
        lambda a: {"state": "succeed", "msg": f"已完成空间感知处理，检测到 {a.get('obj_name', '')} 相关物品"},
    )
    # Box 一步式
    p.set_default("fetch_box", FETCH_BOX_SUCCESS)
    p.set_default("put_box", PUT_BOX_SUCCESS)
    # Box 工艺 (initialize / scan / pick_up_box / put_box_to_table)
    p.set_default("initialize", {"state": "succeed", "msg": "已初始化机器人位姿"})
    p.set_default(
        "scan_table_with_box",
        {"state": "succeed", "msg": "桌子的坐标是：(0.5, 0.5, 0.5)，箱子位于桌面"},
    )
    p.set_default("pick_up_box", {"state": "succeed", "msg": "已抓起箱子"})
    p.set_default("put_box_to_table", {"state": "succeed", "msg": "已将箱子放到桌子上"})
    # 系统
    p.set_conditional(
        "parameter_store",
        lambda a: {"state": "succeed", "msg": f"action={a.get('action', '')} ok"},
    )


def happy_path_fetch_mock() -> MockResultProvider:
    """All tools succeed; memory always finds the item."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            # 顺序敏感: 长 key 在前 (`key in combined` 子串匹配, 防止短 key 误命中)。
            {
                "水瓶": [MEMORY_ITEM_WATER_BOTTLE],
                "饮料瓶": [MEMORY_ITEM_BOTTLE],
                "苹果": [MEMORY_ITEM_APPLE],
                "瓶子": [MEMORY_ITEM_BOTTLE],
                "橙子": [MEMORY_ITEM_ORANGE],
                "杯子": [MEMORY_ITEM_CUP],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
                "水": [MEMORY_ITEM_WATER_BOTTLE],
            }
        ),
    )
    return p


def fetch_and_place_mock() -> MockResultProvider:
    """Same as happy path but with table entries for placement targets."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "瓶子": [MEMORY_ITEM_BOTTLE],
                "橙子": [MEMORY_ITEM_ORANGE],
                "饮料": [MEMORY_ITEM_BOTTLE],
                "白色": [MEMORY_ITEM_TABLE_WHITE],
                "红色": [MEMORY_ITEM_TABLE_RED],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    return p


def memory_miss_mock() -> MockResultProvider:
    """First spatial_memory_query_vec returns empty; subsequent calls find the item."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_sequence(
        "spatial_memory_query_vec",
        [
            [],
            [MEMORY_ITEM_ORANGE],
            [MEMORY_ITEM_ORANGE],
            [MEMORY_ITEM_ORANGE],
        ],
    )
    return p


def scene_fail_mock() -> MockResultProvider:
    """scene_recognition fails on first call, succeeds on second."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "杯子": [MEMORY_ITEM_CUP],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    p.set_sequence(
        "scene_recognition",
        [
            {"state": "failed", "msg": "当前位置没有找到杯子"},
            {"state": "succeed", "msg": "当前位置有杯子"},
        ],
    )
    return p


def multi_task_mock() -> MockResultProvider:
    """Supports the complex 3-sub-task scenario."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "瓶子": [MEMORY_ITEM_BOTTLE],
                "橙子": [MEMORY_ITEM_ORANGE],
                "饮料": [MEMORY_ITEM_BOTTLE],
                "白色": [MEMORY_ITEM_TABLE_WHITE],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    return p


def box_carrying_mock() -> MockResultProvider:
    """Only fetch_box / put_box are needed."""
    p = MockResultProvider()
    p.set_default("fetch_box", FETCH_BOX_SUCCESS)
    p.set_default("put_box", PUT_BOX_SUCCESS)
    return p


def context_accumulation_mock() -> MockResultProvider:
    """Long-horizon multi-fruit task to trigger L1 context compression.

    15 个水果按顺序拿+递交，每个完整 cycle 涉及：
    search (query_vec) → pick (move/scene/grasp/delete) → place (perception/move/handover)
    预期 wall ~3-5 min, n_tools ~135, prompt 累积 ~80-120k tokens
    （配合 VERBOSE_MOCK=1 时 query_vec 返回所有 15 物品，触发 L1）。
    """
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "橙子": [MEMORY_ITEM_ORANGE],
                "苹果": [MEMORY_ITEM_APPLE],
                "香蕉": [MEMORY_ITEM_BANANA],
                "葡萄": [MEMORY_ITEM_GRAPE],
                "桃子": [MEMORY_ITEM_PEACH],
                "梨": [MEMORY_ITEM_PEAR],
                "樱桃": [MEMORY_ITEM_CHERRY],
                "芒果": [MEMORY_ITEM_MANGO],
                "菠萝": [MEMORY_ITEM_PINEAPPLE],
                "西瓜": [MEMORY_ITEM_WATERMELON],
                "柠檬": [MEMORY_ITEM_LEMON],
                "椰子": [MEMORY_ITEM_COCONUT],
                "火龙果": [MEMORY_ITEM_DRAGONFRUIT],
                "草莓": [MEMORY_ITEM_STRAWBERRY],
                "蓝莓": [MEMORY_ITEM_BLUEBERRY],
            }
        ),
    )
    return p


# ---------------------------------------------------------------------------
# Extended coverage scenarios
# ---------------------------------------------------------------------------

def place_to_red_table_mock() -> MockResultProvider:
    """Place item to a red table instead of white."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "杯子": [MEMORY_ITEM_CUP],
                "红色": [MEMORY_ITEM_TABLE_RED],
                "桌子": [MEMORY_ITEM_TABLE_RED],
            }
        ),
    )
    return p


def fetch_two_items_mock() -> MockResultProvider:
    """Supports fetching two items sequentially and handing both to the user."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "橙子": [MEMORY_ITEM_ORANGE],
                "瓶子": [MEMORY_ITEM_BOTTLE],
                "水": [MEMORY_ITEM_WATER_BOTTLE],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    return p


def multi_waypoint_search_mock() -> MockResultProvider:
    """Item not found in memory; needs to search multiple waypoints before finding it."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_sequence(
        "spatial_memory_query_vec",
        [
            [],  # initial query: not in memory
            [],  # after waypoint 1 spatial processing: still not found
            [MEMORY_ITEM_REMOTE],  # after waypoint 2: found
            [MEMORY_ITEM_REMOTE],
            [MEMORY_ITEM_REMOTE],
        ],
    )
    return p


# ---------------------------------------------------------------------------
# Failure-recovery scenarios (~10% failure rate patterns)
# ---------------------------------------------------------------------------

def grasp_fail_retry_mock() -> MockResultProvider:
    """grasp_start fails on the first attempt (out of range), succeeds on retry."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    p.set_sequence("grasp_start", [GRASP_OUT_OF_RANGE, {"status": "success", "message": "执行任务: apple"}])
    return p


def move_fail_retry_mock() -> MockResultProvider:
    """move_to fails on the first attempt, succeeds on subsequent calls."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    p.set_sequence("move_to", [MOVE_FAILED, MOVE_SUCCESS, MOVE_SUCCESS, MOVE_SUCCESS])
    return p


def handover_fail_retry_mock() -> MockResultProvider:
    """handover fails on first attempt, succeeds on retry."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "水": [MEMORY_ITEM_WATER_BOTTLE],
            }
        ),
    )
    p.set_sequence("handover", [HANDOVER_FAILED, HANDOVER_SUCCESS])
    return p


def place_down_fail_retry_mock() -> MockResultProvider:
    """place_down fails on first attempt, succeeds on retry."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
                "白色": [MEMORY_ITEM_TABLE_WHITE],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    p.set_sequence("place_down", [PLACE_DOWN_FAILED, PLACE_DOWN_SUCCESS])
    return p


def perception_fail_retry_mock() -> MockResultProvider:
    """perception_custom fails on first attempt, succeeds on retry."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "苹果": [MEMORY_ITEM_APPLE],
            }
        ),
    )
    p.set_sequence("perception_custom", [PERCEPTION_CUSTOM_FAILED, PERCEPTION_CUSTOM_SUCCESS])
    return p


def compound_failure_mock() -> MockResultProvider:
    """Multiple tools fail at different points — scene recognition fails then grasp fails."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "杯子": [MEMORY_ITEM_CUP],
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
            }
        ),
    )
    p.set_sequence(
        "scene_recognition",
        [
            {"state": "failed", "msg": "当前位置没有找到杯子"},
            {"state": "succeed", "msg": "当前位置有杯子"},
        ],
    )
    p.set_sequence(
        "grasp_start",
        [GRASP_OUT_OF_RANGE, {"status": "success", "message": "执行任务: cup"}],
    )
    return p


def box_fail_retry_mock() -> MockResultProvider:
    """fetch_box fails on first attempt, succeeds on retry."""
    p = MockResultProvider()
    p.set_sequence("fetch_box", [FETCH_BOX_FAILED, FETCH_BOX_SUCCESS])
    p.set_default("put_box", PUT_BOX_SUCCESS)
    return p


# ---------------------------------------------------------------------------
# Box 工艺 scenarios (initialize / scan_table_with_box / pick_up_box / put_box_to_table)
# 区别于 box_carrying_mock (high-level fetch_box / put_box).
# ---------------------------------------------------------------------------

def box_workflow_mock() -> MockResultProvider:
    """完整 box 工厂工艺 happy path: initialize -> scan -> pick_up_box -> put_box_to_table."""
    p = MockResultProvider()
    _apply_common_defaults(p)  # box 工艺 4 工具的 default 已在 common 里
    # 让 spatial_memory_query_vec 能找到桌子 (box_carry SKILL 可能先查桌子坐标)
    p.set_conditional(
        "spatial_memory_query_vec",
        _memory_query_handler(
            {
                "桌子": [MEMORY_ITEM_TABLE_WHITE],
                "工作台": [MEMORY_ITEM_TABLE_WHITE],
                "货架": [MEMORY_ITEM_TABLE_RED],
            }
        ),
    )
    return p


def box_workflow_scan_fail_mock() -> MockResultProvider:
    """scan_table_with_box 第一次失败重试成功 (验证 box_carry SKILL 重试规则)."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_sequence(
        "scan_table_with_box",
        [
            {"state": "failed", "msg": "视觉算法识别失败, 桌面可能被遮挡"},
            {"state": "succeed", "msg": "桌子的坐标是：(0.5, 0.5, 0.5), 箱子位于桌面"},
        ],
    )
    return p


def box_workflow_pick_fail_mock() -> MockResultProvider:
    """pick_up_box 第一次失败重试成功 (抓取重试)."""
    p = MockResultProvider()
    _apply_common_defaults(p)
    p.set_sequence(
        "pick_up_box",
        [
            {"state": "failed", "msg": "夹爪未能稳固抓取箱子"},
            {"state": "succeed", "msg": "已抓起箱子"},
        ],
    )
    return p
