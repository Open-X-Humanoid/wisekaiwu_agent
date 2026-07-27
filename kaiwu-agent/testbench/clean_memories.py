#!/usr/bin/env python3
"""通用脏记忆清洗 / 迁移工具（离线，作用于本地原子记忆 JSON）。

针对历史脏数据做三类处理（与新版抽取规则对齐）：

1. **疑问句脏记忆**：value/content 里残留疑问词（如 `地点: 哪家公司上班`、
   `用户喜欢 吃什么`）——这些是旧版误把用户提问当事实写入的，删除。
2. **偏好 attribute 迁移**：旧形态 `偏好_乌龙茶` / `✗_偏好_可乐`（attribute 含 value）
   → 新形态 `偏好:饮品` / `✗_偏好:饮品`（attribute 只含受控子类），value 规范化。
3. **去重**：迁移后按 (entity, attribute, value) 三元组去重，保留"有效 > 高置信 > 更新"的一条。

安全：
- 默认 **dry-run**，只打印将要发生的改动，不写文件；
- `--apply` 才落盘，且写前自动备份 `*.bak-<时间戳>`；
- 作用范围可用 `--user` / `--dir` 限定。

用法：
    python testbench/clean_memories.py                 # dry-run，扫描 data/supermemory/
    python testbench/clean_memories.py --user EVA      # 只看 EVA
    python testbench/clean_memories.py --apply         # 真正清洗 + 备份
    python testbench/clean_memories.py --dir /path/to/supermemory --apply
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 允许从仓库根直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kaiwu.personalization.memory_schema import (  # noqa: E402
    normalize_value,
    build_preference_attribute,
    preference_subcategory,
    known_subcategories,
    looks_like_noise,
    is_preference_attribute,
    PREF_POS_PREFIX,
    PREF_NEG_PREFIX,
)

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data" / "supermemory"
_SUFFIX = "_atomic_memories.json"


def _is_question_dirty(mem: dict) -> bool:
    """value/content 是噪声(疑问/语气助词/指示代词残片) → 判为脏记忆。

    用 looks_like_noise（实体感知）：用户偏好/身份/物品位置只按疑问助词判，
    位置/事件/人物等噪声易发类目额外启用指示代词/裸"哪"等激进规则。
    """
    entity = str(mem.get("entity") or "")
    value = str(mem.get("value") or "")
    if value and looks_like_noise(value, entity):
        return True
    # content 兜底（去掉"地点: / 用户喜欢 "等前缀噪声影响，仅用通用规则）
    if looks_like_noise(str(mem.get("content") or ""), entity=None) and not value:
        return True
    return False


def _migrate_preference(mem: dict) -> bool:
    """把旧偏好形态迁移为 `偏好:子类` + 规范化 value。返回是否发生改动。"""
    attr = mem.get("attribute") or ""
    if not is_preference_attribute(attr):
        return False
    # 已是新形态（偏好 / 偏好:子类 / ✗_偏好 / ✗_偏好:子类）则只规范化 value
    is_neg = attr.startswith(PREF_NEG_PREFIX)
    # 取旧 attribute 的后缀（_X 或 :X）
    suffix = ""
    for pre in (PREF_NEG_PREFIX + "_", PREF_NEG_PREFIX + ":", PREF_POS_PREFIX + "_", PREF_POS_PREFIX + ":"):
        if attr.startswith(pre):
            suffix = attr[len(pre):]
            break

    old_value = (mem.get("value") or "").strip()
    # 旧形态 attribute 里可能藏着 value（偏好_乌龙茶），value 字段缺失时回退用后缀
    if not old_value:
        old_value = suffix
    norm = normalize_value(old_value) or old_value

    # 子类优先级：① 旧后缀本就是合法类目（偏好_食物）→ 保留；② 否则按 value 重分类
    if suffix in known_subcategories():
        base = PREF_NEG_PREFIX if is_neg else PREF_POS_PREFIX
        new_attr = f"{base}:{suffix}"
    else:
        new_attr = build_preference_attribute(norm, is_neg)
    changed = (new_attr != attr) or (norm != (mem.get("value") or ""))
    if changed:
        mem["attribute"] = new_attr
        mem["value"] = norm
        verb = "不喜欢" if is_neg else "喜欢"
        mem["content"] = f"用户{verb} {norm}"
    return changed


def _dedup_key(mem: dict) -> tuple:
    return (mem.get("entity") or "", mem.get("attribute") or "", mem.get("value") or "")


def _mem_id(mem: dict) -> str:
    return str(mem.get("memory_id") or mem.get("id") or mem.get("mem_id") or "")


def _better(a: dict, b: dict) -> dict:
    """从两条同键记忆里挑更优的：有效 > 高置信 > 更新时间。"""
    if bool(a.get("is_active", True)) != bool(b.get("is_active", True)):
        return a if a.get("is_active", True) else b
    ca, cb = float(a.get("confidence", 0)), float(b.get("confidence", 0))
    if ca != cb:
        return a if ca > cb else b
    return a if str(a.get("created_at", "")) >= str(b.get("created_at", "")) else b


def plan_cleanup(data: list, use_llm: bool = False) -> dict:
    """对一批记忆做清洗规划（纯函数，本地/云端共用）。

    返回 dict：
      final         清洗后保留的记忆列表（迁移已就地改写）
      removed_ids   被删除记忆的 memory_id 集合（疑问句脏数据 + 去重落败者）
      migrated_ids  发生字段迁移的 memory_id 集合（需回写云端）
      stats/_samples 统计与示例

    use_llm=True 时，对规则保留下来的记忆再做一轮 LLM 语义终审，剔除"语义无意义"
    的孤立片段（如 地点:卧室 / 地点:回龙观），这类规则判不了。
    """
    stats = {"total": len(data), "removed_question": 0, "migrated_pref": 0,
             "deduped": 0, "removed_llm": 0, "kept": 0}
    samples = {"removed": [], "migrated": []}
    removed_ids: set = set()
    migrated_ids: set = set()

    # LLM 语义终审：先判出"无意义"的下标（针对原始 data），其 memory_id 一并删
    llm_drop_ids: set = set()
    if use_llm:
        try:
            from kaiwu.personalization.memory_llm_gate import judge_memory_records
            for li in judge_memory_records(data):
                m = data[li]
                if isinstance(m, dict):
                    llm_drop_ids.add(_mem_id(m))
        except Exception:
            pass

    kept: list = []
    for mem in data:
        if not isinstance(mem, dict):
            continue
        if _is_question_dirty(mem):
            stats["removed_question"] += 1
            removed_ids.add(_mem_id(mem))
            if len(samples["removed"]) < 5:
                samples["removed"].append(mem.get("content") or mem.get("value"))
            continue
        if _mem_id(mem) in llm_drop_ids:
            stats["removed_llm"] += 1
            removed_ids.add(_mem_id(mem))
            if len(samples["removed"]) < 8:
                samples["removed"].append(f"[LLM] {mem.get('content') or mem.get('value')}")
            continue
        before = (mem.get("attribute"), mem.get("value"))
        if _migrate_preference(mem):
            stats["migrated_pref"] += 1
            migrated_ids.add(_mem_id(mem))
            if len(samples["migrated"]) < 5:
                samples["migrated"].append(f"{before[0]}={before[1]} → {mem['attribute']}={mem['value']}")
        kept.append(mem)

    # 去重（仅对活跃记忆做三元组合并；失效历史保留）
    merged: dict = {}
    passthrough: list = []
    for mem in kept:
        if not mem.get("is_active", True):
            passthrough.append(mem)
            continue
        k = _dedup_key(mem)
        if k in merged:
            stats["deduped"] += 1
            loser = _better(merged[k], mem)  # 实际保留的
            winner = merged[k] if loser is mem else mem
            # winner 是要丢弃的那条
            removed_ids.add(_mem_id(winner))
            merged[k] = loser
        else:
            merged[k] = mem
    final = list(merged.values()) + passthrough
    stats["kept"] = len(final)
    # 迁移集合里若有人被去重删掉，则从迁移集合移除（避免回写已删记忆）
    migrated_ids -= removed_ids
    return {"final": final, "removed_ids": {i for i in removed_ids if i},
            "migrated_ids": {i for i in migrated_ids if i},
            "stats": stats, "_samples": samples}


def clean_file(path: Path, apply: bool, use_llm: bool = False) -> dict:
    """清洗单个本地用户文件，返回统计 dict。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"file": path.name, "error": str(e)}
    if not isinstance(data, list):
        return {"file": path.name, "error": "not a list"}

    plan = plan_cleanup(data, use_llm=use_llm)
    st = {"file": path.name, **plan["stats"], "_samples": plan["_samples"]}

    if apply and (st["removed_question"] or st["migrated_pref"] or st["deduped"] or st["removed_llm"]):
        bak = path.with_suffix(f".json.bak-{datetime.now():%Y%m%d%H%M%S}")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.write_text(json.dumps(plan["final"], ensure_ascii=False, indent=2), encoding="utf-8")
        st["backup"] = bak.name
    return st


def _build_cloud_sync():
    """从 kaiwu.yaml + .env 构建并启用 CloudSyncManager；失败返回 None。"""
    import yaml
    from kaiwu.personalization.storage.baidu_cloud import create_baidu_cloud_storage
    from kaiwu.personalization.cloud_sync import CloudSyncManager

    root = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv
        load_dotenv(root / ".env")
    except Exception:
        pass
    raw = yaml.safe_load(open(root / "configs" / "kaiwu.yaml", encoding="utf-8"))
    pers = (raw or {}).get("personalization") or {}
    storage = create_baidu_cloud_storage(config=pers)
    if not storage.initialize():
        return None
    cs = CloudSyncManager()
    if not cs.configure(storage):
        return None
    return cs


def clean_cloud(user_id: str, cloud_sync, apply: bool, use_llm: bool = False) -> dict:
    """清洗某用户的云端原子记忆（拉取→规划→删除脏/去重落败→回写迁移）。"""
    ok, cloud_list = cloud_sync.pull_full_atomic_memories(user_id)
    if not ok:
        return {"file": f"[cloud] {user_id}", "error": "云端拉取失败/不可用"}
    plan = plan_cleanup(list(cloud_list), use_llm=use_llm)
    st = {"file": f"[cloud] {user_id}", **plan["stats"], "_samples": plan["_samples"]}
    if apply:
        by_id = {_mem_id(m): m for m in plan["final"]}
        for mid in plan["removed_ids"]:
            try:
                cloud_sync.delete_atomic_memory(user_id, mid)
            except Exception as e:
                st.setdefault("errors", []).append(f"del {mid}: {e}")
        for mid in plan["migrated_ids"]:
            mem = by_id.get(mid)
            if mem:
                try:
                    cloud_sync.push_atomic_memory(user_id, mem)
                except Exception as e:
                    st.setdefault("errors", []).append(f"push {mid}: {e}")
        st["applied"] = True
    return st


def main():
    ap = argparse.ArgumentParser(description="通用脏记忆清洗/迁移工具（离线）")
    ap.add_argument("--dir", default=str(_DEFAULT_DIR), help="原子记忆目录（默认 data/supermemory）")
    ap.add_argument("--user", default=None, help="只处理某个 user_id")
    ap.add_argument("--apply", action="store_true", help="真正写盘/写云（默认 dry-run，仅打印）")
    ap.add_argument("--cloud", action="store_true",
                    help="清理云端原子记忆（RDS+BOS，需云连通）；默认只清本地文件")
    ap.add_argument("--llm", action="store_true",
                    help="额外用 LLM 语义终审剔除'无意义'记忆（如 地点:卧室）；需 model.yaml 可达")
    args = ap.parse_args()

    base = Path(args.dir)
    if not base.exists():
        print(f"目录不存在: {base}")
        sys.exit(1)

    # 用户列表：--user 指定，否则取本地文件名推断
    if args.user:
        user_ids = [args.user]
    else:
        user_ids = sorted(p.name[: -len(_SUFFIX)] for p in base.glob(f"*{_SUFFIX}"))

    mode = "APPLY（写盘/写云+备份）" if args.apply else "DRY-RUN（仅预览，不改动）"
    target = "云端 RDS+BOS" if args.cloud else f"本地目录 {base}"
    print("=" * 64)
    print(f" 脏记忆清洗  模式={mode}  目标={target}")
    print("=" * 64)

    cloud_sync = None
    if args.cloud:
        cloud_sync = _build_cloud_sync()
        if cloud_sync is None:
            print(" [错误] 云端不可用（RDS/BOS 未连通或未配置）。请在能连云的机器上运行，"
                  "或检查 .env 的千帆/RDS/BOS 配置。")
            sys.exit(1)

    totals = {"total": 0, "removed_question": 0, "migrated_pref": 0, "deduped": 0,
              "removed_llm": 0, "kept": 0}
    for uid in user_ids:
        if args.cloud:
            st = clean_cloud(uid, cloud_sync, args.apply, use_llm=args.llm)
        else:
            path = base / f"{uid}{_SUFFIX}"
            if not path.exists():
                print(f"  [跳过] 文件不存在: {path.name}")
                continue
            st = clean_file(path, args.apply, use_llm=args.llm)
        if st.get("error"):
            print(f"  [错误] {st['file']}: {st['error']}")
            continue
        for k in totals:
            totals[k] += st.get(k, 0)
        flag = f"  备份={st['backup']}" if st.get("backup") else ""
        flag += "  [已写云]" if st.get("applied") else ""
        print(f"\n■ {st['file']}: 共{st['total']} → 保留{st['kept']}"
              f"（删疑问句{st['removed_question']} / LLM删{st.get('removed_llm', 0)}"
              f" / 迁移偏好{st['migrated_pref']} / 去重{st['deduped']}）{flag}")
        for s in (st.get("_samples", {}).get("removed") or []):
            print(f"    - 删: {s}")
        for s in (st.get("_samples", {}).get("migrated") or []):
            print(f"    ~ 迁: {s}")
        for e in (st.get("errors") or []):
            print(f"    ! 云操作错误: {e}")

    print("\n" + "-" * 64)
    print(f" 合计: 共{totals['total']} → 保留{totals['kept']}  "
          f"删疑问句{totals['removed_question']} / LLM删{totals['removed_llm']} / "
          f"迁移偏好{totals['migrated_pref']} / 去重{totals['deduped']}")
    if not args.apply:
        print(" （这是 DRY-RUN，未改动任何数据；确认无误后加 --apply 落盘/写云）")


if __name__ == "__main__":
    main()
