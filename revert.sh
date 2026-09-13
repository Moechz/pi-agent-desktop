#!/bin/bash
# 回滚 Pi Agent Desktop 的全部 UI 补丁（1 会话只留结果v2 / 2 输入框边框 / 3 侧边栏平铺+状态点）
set -e
APP="/Applications/Pi Agent Desktop.app/Contents/Resources/standalone"
cp "$HOME/.pi-ui-patches/backup/0wz_4dmun1la1.js.orig"  "$APP/.next/static/chunks/0wz_4dmun1la1.js"
cp "$HOME/.pi-ui-patches/backup/MessageView.tsx.orig"   "$APP/components/MessageView.tsx"
cp "$HOME/.pi-ui-patches/backup/MessageList.tsx.orig"    "$APP/components/MessageList.tsx"
cp "$HOME/.pi-ui-patches/backup/ChatInput.tsx.orig"     "$APP/components/ChatInput.tsx"
cp "$HOME/.pi-ui-patches/backup/SessionSidebar.tsx.orig" "$APP/components/SessionSidebar.tsx"
cp "$HOME/.pi-ui-patches/backup/SessionTree.tsx.orig"   "$APP/components/session-sidebar/SessionTree.tsx"
cp "$HOME/.pi-ui-patches/backup/helpers.ts.orig"        "$APP/components/session-sidebar/helpers.ts"
rm -rf "$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop/Cache/Cache_Data" 2>/dev/null || true
rm -rf "$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop/Code Cache"/* 2>/dev/null || true
echo "✅ 已回滚全部补丁。请完全退出 Pi Agent Desktop（Cmd+Q）后重新打开。"
