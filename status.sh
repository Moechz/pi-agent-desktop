#!/bin/bash
# Pi Agent Desktop UI 定制 —— 体检报告（一眼看清当前状态 / 备份是否可信）
# 用法：bash status.sh
# 环境变量（测试用）：PI_STANDALONE / PI_UI_HOME / PI_APP_VERSION
set -u

APP="${PI_STANDALONE:-/Applications/Pi Agent Desktop.app/Contents/Resources/standalone}"
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
BK="$RT/backup"
CACHE="$(ls -d "$HOME/Library/Application Support/"@*pi-agent-desktop 2>/dev/null | head -1)"

app_version() {
    [ -n "${PI_APP_VERSION:-}" ] && { echo "$PI_APP_VERSION"; return; }
    /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" \
        "$(dirname "$(dirname "$APP")")/Info.plist" 2>/dev/null
}
sha() { shasum -a 256 "$1" 2>/dev/null | cut -d' ' -f1; }

VER="$(app_version)"
BKVER="$(sed -n 's/^app_version=//p' "$BK/MANIFEST.txt" 2>/dev/null | head -1)"
echo "═══ Pi Agent Desktop UI 定制体检 ═══"

# 1. 应用与版本
if [ -d "$APP" ]; then
    echo "应用       : ✅ 已安装（v${VER:-?}）"
else
    echo "应用       : ❌ 未找到 $APP"; exit 1
fi

# 2. 补丁是否在位
if grep -qs "__piSM" "$APP"/.next/static/chunks/*.js 2>/dev/null; then
    echo "UI 补丁    : ✅ 在位"
else
    echo "UI 补丁    : ✗ 不在位（原版态，或被应用更新覆盖）"
fi

# 3. 版本 vs 备份
if [ -n "$BKVER" ]; then
    if [ "$BKVER" = "$VER" ]; then
        echo "备份版本   : ✅ 匹配（v$BKVER）"
    else
        echo "备份版本   : ⚠️ 不匹配！备份是 v$BKVER，应用是 v$VER —— 回滚前先重新采集"
    fi
else
    echo "备份版本   : ⚠️ 无 MANIFEST（先跑 backup-app.sh）"
fi

# 4. 真原版（gold）是否已固化
if [ -d "$BK/pristine-$VER" ]; then
    echo "真原版     : ✅ backup/pristine-$VER（$(find "$BK/pristine-$VER" -type f | wc -l | tr -d ' ') 个文件）"
else
    echo "真原版     : ✗ 未固化 —— bash $RT/backup-app.sh --from-dmg <官方DMG>"
fi
INS="$(sed -n 's/^installer=//p' "$BK/MANIFEST.txt" 2>/dev/null | head -1)"
[ -z "$INS" ] || [ ! -f "$INS" ] && for c in "$BK/installer/"*.dmg \
        "$HOME/Documents/projects/pi-agent-UI-change-memo/backup/installer/"*.dmg; do
    [ -f "$c" ] && { INS="$c"; break; }
done
if [ -n "$INS" ]; then
    exp="$(sed -n 's/^installer_sha256=//p' "$BK/MANIFEST.txt" 2>/dev/null | head -1)"
    if [ -n "$exp" ] && [ "$(sha "$INS")" = "$exp" ]; then
        echo "官方DMG    : ✅ 已归档且校验通过（$(basename "$INS")）"
    else
        echo "官方DMG    : ⚠️ 已归档（$(basename "$INS")）但 sha256 校验不通过/无记录"
    fi
else
    echo "官方DMG    : ✗ 未归档（终极还原靠它）"
fi

# 5. .orig 可信度（是否与真原版一致）
if [ -d "$BK/pristine-$VER" ]; then
    ok=0; bad=0
    for f in "$BK"/*.orig; do
        [ -f "$f" ] || continue
        base="$(basename "$f" .orig)"
        p="$(find "$BK/pristine-$VER" -type f -name "$base" 2>/dev/null | head -1)"
        if [ -n "$p" ]; then
            [ "$(sha "$f")" = "$(sha "$p")" ] && ok=$((ok+1)) || bad=$((bad+1))
        fi
    done
    echo ".orig 可信 : ${ok} 个一致${bad:+，$bad 个不一致⚠️}"
fi

# 6. 看护状态
if [ -f "$RT/FROZEN" ]; then
    echo "看护       : ❄️ 已冻结（不会自动重打；恢复用 patch-on.sh）"
elif launchctl list 2>/dev/null | grep -q com.user.pi-ui-patch; then
    echo "看护       : 🟢 运行中（每小时检查，缺补丁自动重打）"
else
    echo "看护       : ⚠️ 未加载（launchctl load ~/Library/LaunchAgents/com.user.pi-ui-patch.plist）"
fi

# 7. 最近快照
n=$(ls -1 "$RT/snapshots/"*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" -gt 0 ]; then
    echo "快照       : $n 份，最近：$(basename "$(ls -1t "$RT/snapshots/"*.tar.gz | head -1)")"
else
    echo "快照       : ✗ 无（改补丁前跑 backup-app.sh --snapshot）"
fi

# 8. 语法快检（白屏首要原因）
NODE=""
for c in node "$HOME/.pi/agent/bin/node" /opt/homebrew/bin/node; do
    command -v "$c" >/dev/null 2>&1 && { NODE="$c"; break; }
done
if [ -n "$NODE" ]; then
    badjs=0
    for j in "$APP"/.next/static/chunks/*.js; do
        $NODE --check "$j" 2>/dev/null || { echo "语法       : ❌ $(basename "$j") 损坏！"; badjs=1; }
    done
    [ $badjs -eq 0 ] && echo "语法       : ✅ 全部 chunk 通过 node --check"
fi

# 9. 用户数据备份（会话/记忆/模型配置；补丁 bug 写坏数据时的兜底）
n=$(ls -1 "$RT/userdata/"userdata-*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" -gt 0 ]; then
    newest="$(ls -1t "$RT/userdata/"userdata-*.tar.gz | head -1)"
    age=$(( ($(date +%s) - $(stat -f %m "$newest")) / 3600 ))
    echo "用户数据   : $n 份，最新 $age 小时前（看护每日自动 + patch-on 前自动）"
else
    echo "用户数据   : ✗ 无备份 —— bash $RT/user-data-backup.sh"
fi

echo
echo "速查：回滚 bash $RT/revert.sh ｜ 恢复定制 bash $RT/patch-on.sh ｜ 体检 bash $RT/status.sh ｜ 数据恢复 bash $RT/user-data-backup.sh --restore <文件>"
