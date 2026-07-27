---
name: fetch_to_user
description: 取物给用户的完整场景。当用户说"帮我拿 X"、"把 X 递给我"、"给我拿 X 过来"等（隐含递给用户）时使用。完整流程：找物品坐标 → 抓取 → 递交给用户。禁止用于"放到 X 上"（那是 move_item_to_location）。
---

# 取物给用户
完整流程：**找到物品位置 → 抓取到手 → 递交给用户**。一个技能内完成"找坐标 → 抓取 → 递交"三个阶段。

## 阶段一：找到物品位置并移动过去
目标是拿到物品的坐标。根据用户有没有指定取物地点，走不同的路线。如果用户有明确指定取xxx地方或者xxx上面拿物品，必须走情况A的逻辑；没有指定，只是说拿物品走情况B。

**情况 A：用户指定了去特定位置取物**（比如"去把桌子上的水果拿给我"）
因为用户明确指定了地点取物，先找到指定位置，然后移动过去，再扫描并确定物品的位置
1. 先调用 `spatial_memory_query_vec` 先查询用户指定位置，如茶水间/门口/桌子
2. 查询到用户指定位置的坐标后，调用 `move_to(obj_x, obj_y, coordinate_x, coordinate_y, coordinate_z, coordinate_yaw)` 移动到用户指定位置。若没有找到指定位置，返回任务失败
3. 到了用户指定位置后用 `trigger_spatial_processing(obj_name=英文物品名)` 扫描环境，再 `spatial_memory_query_vec` 查待抓取物品的坐标。没有则任务失败。

**情况 B：用户没指定地点**（比如"帮我拿瓶水"）
直接从记忆中查询物品的位置。
1. 先用 `spatial_memory_query_vec` 查历史记忆里有没有这个物品的坐标；
2. 查不到就用 `trigger_spatial_processing(obj_name=英文物品名)` 扫一下当前环境再查一次。
3. 还是找不到，就换地方找：`move(dst_point={"x":..., "y":..., "yaw":...})` 到候选位置后再扫描、再查，这样最多试 2 个候选点。全部试完仍没找到，报告"未找到 {name}"并结束。

一旦查到待抓取物品的坐标，调用 `move_to(obj_x, obj_y, coordinate_x, coordinate_y, coordinate_z, coordinate_yaw)` 导航到物品位置。到不了就重试 1 次，还不行就报告"无法到达物品位置"并结束。

## 阶段二：抓取物品
确认物品真的在眼前，再把它抓到手里。
1. 用 `scene_recognition(target=item英文名)` 确认物品在视野里。确认到了就去抓；如果没看到（`state: failed`），说明记忆里的位置已经过期，用 `delete_spatial_memory_by_id(id_list=[memory_id])` 清掉这条旧记忆，然后报告"物品不在记忆位置，需重新定位"并结束。
2. 用 `grasp_start(item=item英文名)` 抓取。抓到了就进入记忆清理；抓失败就重试 1 次，还不行报告"抓取失败"并结束。
3. 抓成功后，物品已经离开原位、旧记忆作废，用 `delete_spatial_memory_by_id(id_list=[memory_id])` 清掉这条记忆。

## 阶段三：递交给用户
把手中的物品交付给用户。
⚠️ 强制执行规则（违反 = 任务失败）
- 用户会移动，每次递交前**必须**重新感知用户位置，然后在移动和递给用户，**禁止**跳过任何步骤。
1. `perception_custom(xxx)` — 获取用户位置。失败重试 1 次，仍失败则报错结束。
2. `move_to(obj_x, obj_y, coordinate_x, coordinate_y, coordinate_z, coordinate_yaw)` — 用上一步返回的 `user_pose` 6 个字段原样填入参数，移动到用户旁。失败重试 1 次，仍失败则报错结束。
3. （可选）`reach_out(position=[x,y,z], object_name=...)` — 伸手预动作，让递交更自然。
4. `handover` — 递出物品。失败重试 1 次，仍失败则报错结束。完成后物品（递给了用户）。

**注意**：每次调用工具前都必须要说明当前正在执行的动作，比如：
- 调用 `move` 前说"这附近没找到，我去旁边再找找"
- 调用 `move_to` 前说"找到xxx了，我过去拿"
- 调用 `grasp_start` 前说"我来把xxx拿起来"
- 调用 `perception_custom` 前说"我看看你现在在哪儿"
- 例外：调用 `delete_spatial_memory_by_id` 无需执行机器人物理动作，调用前不需要说明