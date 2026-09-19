#!/bin/bash
# Pi Agent Desktop UI 补丁看护：登录时 + 每小时检查补丁是否在位，
# 应用更新后被抹掉则自动重打；重打失败发系统通知提醒人工适配。
# 新增：FROZEN 哨兵（patch-off.sh 置位）→ 完全不动手（回滚后不会被自动打回）；
#       补丁在位时顺带 node --check 快检 chunk 语法，损坏则发通知（白屏预警）。
# 注意：必须放在 ~/.pi-ui-patches（home 根）运行——~/Documents 受 TCC 保护，
# launchd 无权读取；本文件的归档副本在 ~/Documents/projects/pi-agent-UI-change-memo/
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_STANDALONE="/Applications/Pi Agent Desktop.app/Contents/Resources/standalone"
CACHE="$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop"

# 人工冻结（patch-off.sh）→ 什么都不做
if [ -f "$DIR/FROZEN" ]; then
  echo "$(date '+%F %T') 看护已冻结（FROZEN 存在），跳过"
  exit 0
fi

# 应用未安装或正在更新中 → 跳过
[ -d "$APP_STANDALONE/.next/static/chunks" ] || exit 0

# 用户数据备份（每天最多一次，--auto 自带 20h 节流；数据被补丁 bug 写坏时兜底）
bash "$DIR/user-data-backup.sh" --auto 2>/dev/null &

# 补丁标记还在 → 快检语法后返回
if grep -qs "__piSM" "$APP_STANDALONE"/.next/static/chunks/*.js 2>/dev/null; then
  NODE=""
  for c in node "$HOME/.pi/agent/bin/node" /opt/homebrew/bin/node /usr/local/bin/node; do
    command -v "$c" >/dev/null 2>&1 && { NODE="$c"; break; }
  done
  if [ -n "$NODE" ]; then
    for j in "$APP_STANDALONE"/.next/static/chunks/*.js; do
      if ! "$NODE" --check "$j" 2>/dev/null; then
        echo "$(date '+%F %T') ⚠️ chunk 语法损坏：$(basename "$j")"
        osascript -e "display notification \"$(basename "$j") 语法损坏（可能白屏），运行 bash ~/.pi-ui-patches/revert.sh 回滚\" with title \"pi-agent-UI-change-memo\"" 2>/dev/null
        exit 1
      fi
    done
  fi
  echo "$(date '+%F %T') 补丁在位，跳过"
  exit 0
fi

# 重打补丁（在磁盘上操作，安全；正在运行的应用下次启动生效）
if out=$(python3 "$DIR/apply_patches.py" 2>&1); then
  echo "$(date '+%F %T') 重打成功: $out"
  rm -rf "$CACHE/Cache/Cache_Data" 2>/dev/null
  rm -rf "$CACHE/Code Cache" 2>/dev/null
  osascript -e 'display notification "UI 补丁已自动重新应用，重启 Pi Agent Desktop 后生效" with title "pi-agent-UI-change-memo"' 2>/dev/null
else
  echo "$(date '+%F %T') 重打失败: $out"
  osascript -e "display notification \"补丁重打失败（应用结构变化），请打开 pi-agent-UI-change-memo 请助手重新适配\" with title \"pi-agent-UI-change-memo\"" 2>/dev/null
fi
