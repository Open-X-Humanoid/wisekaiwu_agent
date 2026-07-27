#
# Copyright (c) 2023~2025 Beijing Innovation Center of Humanoid Robotics. All rights reserved.
#
import fnmatch
import os


def print_directory_contents(path, level=0, prefix="", exclude_patterns=None):
    # 获取目录下的所有文件和子目录
    try:
        items = os.listdir(path)
    except PermissionError:
        print(f"{prefix}权限不足，无法访问该目录: {path}")
        return
    except FileNotFoundError:
        print(f"{prefix}找不到目录: {path}")
        return

    # 遍历目录中的每个项
    for idx, item in enumerate(items):
        # 如果给定的排除模式匹配当前项，则跳过
        if any(fnmatch.fnmatch(item, pattern) for pattern in exclude_patterns):
            continue

        item_path = os.path.join(path, item)
        is_last = idx == len(items) - 1  # 判断是否为最后一个文件/文件夹

        # 根据是否是最后一个元素，决定使用的连接符号
        if is_last:
            connector = "└──"
            new_prefix = prefix + "    "
        else:
            connector = "├──"
            new_prefix = prefix + "│   "

        if os.path.isdir(item_path):
            print(f"{prefix}{connector} {item}/")
            # 递归调用，进入子目录
            print_directory_contents(item_path, level + 1, new_prefix, exclude_patterns)
        else:
            print(f"{prefix}{connector} {item}")


# 调用函数列出当前目录的内容
dir = "kaiwu_agent"
print(dir)
print_directory_contents(dir, exclude_patterns=["*__init__.py", "__pycache__"])
