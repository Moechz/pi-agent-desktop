#!/bin/bash
# 解除冻结 + 立即重打补丁 + 清缓存（patch-off.sh 的逆操作）。
# 用法：bash patch-on.sh
# 环境变量（测试用）：PI_UI_HOME / PI_STANDALONE / PI_NO_CACHE
set -u
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
CACHE="$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop"

# 重打补丁前先备份用户数据（补丁 bug 可能写坏 models.json/会话等，先例 P11/P17）
bash "$RT/user-data-backup.sh" 2>/dev/null || echo "⚠️ 用户数据备份失败（继续，但建议手动跑一次）"

rm -f "$RT/FROZEN" && echo "✅ 看护已恢复自动模式"
if out=$(python3 "$RT/apply_patches.py" 2>&1); then
    echo "✅ $out"
    [ -z "${PI_NO_CACHE:-}" ] && rm -rf "$CACHE/Cache/Cache_Data" "$CACHE/Code Cache"/* 2>/dev/null
    echo "请完全退出 Pi Agent Desktop（Cmd+Q）后重新打开生效。"
else
    echo "❌ 重打失败：$out"
    echo "（应用结构可能变了，请打开 pi-agent-UI-change-memo 项目让助手重新适配）"
    exit 1
fi
