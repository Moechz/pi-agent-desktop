#!/bin/bash
# ============================================================================
# Pi Agent Desktop —— 硬重启（退出 → 清 Chromium 缓存 → 重开）
#
# 用途：部署 UI 补丁后强制刷新。根因：Next.js 对 /_next/static/* 发
#   `Cache-Control: immutable`（一年），我们改 chunk 内容不改文件名，
#   Chromium 命中旧缓存永不回源 —— 常规重启看不到修改。
#   清缓存必须在应用【完全退出】后做：运行中清了会被旧进程的内存索引写回。
#   （P19 已给 server.js 注入 no-cache，此后新条目不会再有此问题；
#    本脚本用于一次性清掉存量 immutable 条目 + 以后保险。）
#
# 用法：bash ~/.pi-ui-patches/hard-restart.sh
# ============================================================================
CACHE="$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop"
LOG() { echo "$(date '+%F %T') $*"; }

LOG "请求退出 Pi Agent Desktop…"
osascript -e 'quit app "Pi Agent Desktop"' 2>/dev/null || true
for i in $(seq 1 60); do
  pgrep -f "Pi Agent Desktop.app/Contents/MacOS" >/dev/null || break
  sleep 0.25
done
if pgrep -f "Pi Agent Desktop.app/Contents/MacOS" >/dev/null; then
  LOG "⚠️ 15 秒仍未退出，强制 kill…"
  pkill -f "Pi Agent Desktop.app/Contents/MacOS" || true
  sleep 2
fi
sleep 1
LOG "清理 Chromium 缓存…"
rm -rf "$CACHE/Cache/Cache_Data" 2>/dev/null || true
rm -rf "$CACHE/Code Cache"/* 2>/dev/null || true
sleep 0.5
LOG "重新启动 Pi Agent Desktop…"
open -a "Pi Agent Desktop"
LOG "✅ 完成（首次加载会稍慢，属正常）"
