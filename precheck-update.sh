#!/bin/bash
# ============================================================================
# Pi Agent Desktop UI 补丁 —— 上游更新预检（不动真 App，一条命令看清兼容性）
#
# 场景：上游官方发布了新版本，你想知道：
#   更新后我的 17 组定制还能不能自动打上？哪些锚点要人工适配？
#
# 原理：挂载新官方 DMG → 提取补丁面到 /tmp 沙盒 → 用当前 apply_patches.py
#       试打 → 逐组报告命中/失配 + 语法验收。全程不碰 /Applications 里的 App。
#
# 用法：
#   bash precheck-update.sh <新官方DMG路径>            # 只预检
#   bash precheck-update.sh <新官方DMG路径> --adopt    # 预检通过后顺便采集该版备份
#                                                      # （pristine/MANIFEST/归档DMG，
#                                                      #  让 revert.sh 对新版本也有兜底）
# 下载新 DMG：官方 GitHub Releases（owner/repo 用 cat "/Applications/Pi Agent Desktop.app/Contents/Resources/app-update.yml" 查得）
#   （本机直连 443 不通：浏览器下载，或 curl -x http://127.0.0.1:7890 -L -o）
#
# 结果：退出码 0 = 全部命中，放心更新（看护会自动重打）
#       退出码 1 = 有失配，按 PATCHES.md §6 适配后再更新
# ============================================================================
set -u

DMG="${1:-}"
ADOPT=0
[ "${2:-}" = "--adopt" ] && ADOPT=1
[ -f "$DMG" ] || { sed -n '2,22p' "$0" >&2; echo "❌ 用法：bash precheck-update.sh <DMG路径> [--adopt]" >&2; exit 2; }

RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
PROJ="$(cd "$(dirname "$0")" && pwd)"
SB="/tmp/pi-precheck"
NODE="$HOME/.pi/agent/bin/node"
[ -x "$NODE" ] || NODE="$(command -v node || true)"

echo "═══ 上游更新预检 ═══"
echo "DMG: $DMG ($(du -h "$DMG" | cut -f1))"

# 1) 挂载并提取补丁面到沙盒
MP="$(mktemp -d /tmp/pidmg.XXXXXX)"
hdiutil attach -nobrowse -readonly -mountpoint "$MP" "$DMG" >/dev/null 2>&1 || { echo "❌ DMG 挂载失败"; exit 2; }
APP="$(ls -d "$MP"/*.app 2>/dev/null | head -1)"
SRC="$APP/Contents/Resources/standalone"
[ -d "$SRC" ] || { hdiutil detach "$MP" >/dev/null 2>&1; echo "❌ DMG 里没有 standalone（不是官方桌面版？）"; exit 2; }
NEWVER="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Contents/Info.plist" 2>/dev/null)"
OLDVER="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "/Applications/Pi Agent Desktop.app/Contents/Info.plist" 2>/dev/null)"
echo "当前版本: v${OLDVER:-?}  →  新版本: v${NEWVER:-?}"

rm -rf "$SB"; mkdir -p "$SB/.next/static"
cp -R "$SRC/.next/static/chunks" "$SB/.next/static/chunks"
[ -d "$SRC/components" ] && cp -R "$SRC/components" "$SB/components"
hdiutil detach "$MP" >/dev/null 2>&1

# 2) 沙盒试打当前补丁器
echo; echo "▶ 用当前补丁器试打（沙盒 $SB）："
OUT="$(PI_STANDALONE="$SB" python3 "$RT/apply_patches.py" 2>&1)"; RC=$?
echo "$OUT" | grep -E "^✅|^ℹ️|❌|未找到|大小" | sed 's/^/  /'

# 3) 语法验收（防"命中了但产物是坏的"）
SYN=1
if [ -n "$NODE" ]; then
    for j in "$SB/.next/static/chunks/"*.js; do
        "$NODE" --check "$j" 2>/dev/null || { echo "❌ 语法坏：$(basename "$j")（锚点命中但产物损坏，须适配）"; SYN=0; }
    done
    [ $SYN -eq 1 ] && echo "  ✅ 产物语法全部通过"
fi

# 4) 结论
echo; echo "═══ 结论 ═══"
if [ $RC -eq 0 ] && [ $SYN -eq 1 ]; then
    echo "✅ 全部补丁命中 v${NEWVER:-?} —— 放心更新！"
    echo "   更新后看护最迟 1 小时自动重打（或手动 bash $RT/patch-on.sh）"
    if [ $ADOPT -eq 1 ]; then
        echo; echo "▶ --adopt：采集 v$NEWVER 备份（pristine/MANIFEST/归档DMG）…"
        bash "$RT/backup-app.sh" --from-dmg "$DMG" || echo "⚠️ 采集失败，手动跑 backup-app.sh --from-dmg"
    else
        echo "   建议：更新前先跑一次带 --adopt 的预检，给 revert.sh 备好新版本兜底"
    fi
else
    echo "❌ 有失配（见上方 [Px] 行）—— 按 $PROJ/PATCHES.md §6 适配后再更新"
    echo "   快速路径：把本输出 + PATCHES.md 交给 AI 助手；沙盒已留在 $SB 可直接复现"
    exit 1
fi
rm -rf "$SB"
