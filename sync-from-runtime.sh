#!/bin/bash
# 把运行时（~/.pi-ui-patches，权威副本）同步进本归档项目并提交 git
# 用法：适配新版本或改补丁后，在任意位置执行：
#   bash ~/Documents/projects/pi-agent-UI-change-memo/sync-from-runtime.sh
set -e
P="$(cd "$(dirname "$0")" && pwd)"
cp ~/.pi-ui-patches/apply_patches.py "$P/"
cp ~/.pi-ui-patches/watch_and_apply.sh "$P/"
cp ~/.pi-ui-patches/revert.sh "$P/"
cp ~/.pi-ui-patches/README.md "$P/RUNTIME_README.md" 2>/dev/null || true
cp ~/Library/LaunchAgents/com.user.pi-ui-patch.plist "$P/"
cd "$P"
git add -A
git commit -m "sync: runtime patches $(date '+%F %T')" || echo "无变更，跳过提交"
echo "✅ 已同步并归档"
