---
name: go_to_location
description: 机器人移动到某处的完整场景。当用户说"去 X"、"到 X 去"、"移动到 X"等纯粹的位置过渡（如跨房间），且不涉及取物/放物时使用。完整流程：找目标坐标 → 导航。如果是"去某物品位置抓取/放置"，请用 fetch_to_user 或 move_item_to_location（它们内部已含移动）。
---

# 移动到某处
完整流程：**定位目标 → 导航过去**。一个技能内完成"找目标坐标 → 导航"两个阶段。专用于：
- 跨房间过渡（如"去厨房"、"到客厅"）
- 多任务间显式切换位置
- 用户明确说"去某地方"

**不用于**：取物（用 fetch_to_user）、放物（用 move_item_to_location）——这些场景内部已包含移动。

## 阶段一：定位目标（找目标坐标）
找到目的地（如"厨房"、"白色桌子"、"客厅"）的坐标。
1. `spatial_memory_query_vec(obj_cn_name=位置名)` — 查询物品的坐标位置。查询结果非空则进入阶段二，否则调用trigger_spatial_processing。
2. `trigger_spatial_processing(obj_name=英文位置名)` — 触发环境扫描后再查一次 `spatial_memory_query_vec`。找到则进入阶段二，否则开始 waypoint 探索。
3. 多 waypoint 探索（最多 2 个）：`move(dst_point={"x":..., "y":..., "yaw":...})` 移动到候选位置 → `trigger_spatial_processing` → `spatial_memory_query_vec`，找到则进入阶段二，否则换下个候选。
4. 全部探索仍未找到 → 报告"未找到 {name}"，结束。

## 阶段二：导航
把机器人移动到已定位的坐标。
1. `move_to(obj_x, obj_y, coordinate_x, coordinate_y, coordinate_z, coordinate_yaw)` 移动到目标坐标。
   - `obj_x/obj_y` = 目标物体/位置坐标（spatial_memory_query_vec 返回的 obj_x/obj_y）
   - `coordinate_x/coordinate_y/coordinate_z/coordinate_yaw` = 机器人到达的姿态坐标（同上 coordinate_*）
2. 返回 succeed → 完成 ✓
3. 返回 failed → 重试 1 次
4. 第二次仍失败 → 报告"无法移动到目标位置"，结束。

**注意**：每次调用工具前都必须要说明当前正在执行的动作，比如：
- 调用spatial_memory_query_vec前说"我先查一下厨房在哪"
- 调用trigger_spatial_processing前说"没找到，我扫一下周围环境"
- 调用move_to前说"找到了，我这就过去"
