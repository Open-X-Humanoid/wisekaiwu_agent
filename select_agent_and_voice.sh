#!/bin/bash
# select_agent_and_voice.sh
# 检查系统架构并选择合适的 kaiwu_agent.so 和 robot_voice.so 版本，仅适用于 Ubuntu

ARCH=$(uname -m)

echo "Detected architecture: $ARCH"

# 检查并选择 kaiwu.so
if [[ "$ARCH" == "x86_64" ]]; then
    echo "Selecting kaiwu_x86_64.so..."
    mv kaiwu-agent/kaiwu_x86_64.so kaiwu-agent/kaiwu.so
    echo "Selecting robot_voice_x86_64.so..."
    mv robot_voice/robot_voice_x86_64.so robot_voice/robot_voice.so
elif [[ "$ARCH" == "aarch64" ]]; then
    echo "Selecting kaiwu_arm64.so..."
    mv kaiwu-agent/kaiwu_arm64.so kaiwu-agent/kaiwu.so
    echo "Selecting robot_voice_arm64.so..."
    mv robot_voice/robot_voice_arm64.so robot_voice/robot_voice.so
else
    echo "Error: Unsupported architecture: $ARCH"
    exit 1
fi

echo "kaiwu.so and robot_voice.so are ready for use."
