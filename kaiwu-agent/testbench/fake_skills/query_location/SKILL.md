---
name: query_location
description: 仅查询物品等位置的场景。当用户只是问"X 在哪"、"X 在哪里"、"帮我找下 X"等纯查询，不要求取物/移动时使用。完整流程：找坐标 → 口头回答。⚠️ 只负责找到并口头汇报坐标/位置，禁止执行抓取、导航、放置等任何后续物理动作。
---

# 查询位置
完整流程：**定位目标 → 口头回答**。仅查询并汇报，不执行任何后续物理动作。

## 阶段一：定位目标（找坐标）
找到目标物品或位置（如"苹果"、"白色桌子"、"客厅"）的坐标。
1. `spatial_memory_query_vec(obj_cn_name=物品名)` — 查询物品的坐标位置。查询结果非空则进入阶段二，否则调用trigger_spatial_processing。
2. `trigger_spatial_processing(obj_name=英文物品名)` — 触发环境扫描后再查一次 `spatial_memory_query_vec`。找到则进入阶段二，否则开始 waypoint 探索。
3. 多 waypoint 探索（最多 2 个）：`move(dst_point={"x":..., "y":..., "yaw":...})` 移动到候选位置 → `trigger_spatial_processing` → `spatial_memory_query_vec`，找到则进入阶段二，否则换下个候选。
4. 全部探索仍未找到 → 口头回答"未找到 {name}"，结束。

## 阶段二：口头回答
- 用自然语言把找到的位置/坐标告诉用户（例如"苹果在客厅的茶几上"）。
- ⛔ **禁止**继续调用任何抓取、导航到物品、放置、递交等动作。任务到此结束。

**注意**：每次调用工具前都必须要说明当前正在执行的动作，比如：
- 调用spatial_memory_query_vec前说"我先查一下苹果在哪"
- 调用trigger_spatial_processing前说"没找到，我扫一下周围环境"
- 调用move前说"换个位置再找找"
