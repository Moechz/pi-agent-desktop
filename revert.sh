#!/bin/bash
# ============================================================================
# Pi Agent Desktop UI 定制 —— 一键回滚到干净原版（硬化版）
#
# 相比旧版多了 5 道保险：
#   1) 版本守卫：应用升级后 .orig 已过时，硬还原会把旧产物塞进新版 → 白屏；
#      版本不符时拒绝执行（除非 --force），并提示正确做法。
#   2) 回滚前自动快照：万一回滚后你想回到定制版。
#   3) 逐文件 fail-soft：某个文件不存在不再中断整个回滚（旧版 set -e 会半途死）。
#   4) 还原后 sha256 + node --check 双重校验。
#   5) 自动冻结看护（FROZEN 哨兵）：否则 1 小时内 launchd 会把补丁又打回来！
#
# 用法：
#   bash revert.sh              # 回滚（版本不符则拒绝）
#   bash revert.sh --force      # 版本不符也强行还原
#   bash revert.sh --keep-patched   # 只冻结看护，不回滚
#
# 环境变量（测试用）：PI_STANDALONE / PI_UI_HOME / PI_APP_VERSION / PI_NO_CACHE
# ============================================================================
set -u

APP="${PI_STANDALONE:-/Applications/Pi Agent Desktop.app/Contents/Resources/standalone}"
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
BK="$RT/backup"
SNAP="$RT/snapshots"
FROZEN="$RT/FROZEN"
CACHE="$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop"

FORCE=0; KEEP_PATCHED=0
for a in "$@"; do
    case "$a" in
        --force) FORCE=1 ;;
        --keep-patched) KEEP_PATCHED=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "未知参数：$a" >&2; exit 2 ;;
    esac
done

die() { echo "❌ $*" >&2; exit 1; }
app_version() {
    [ -n "${PI_APP_VERSION:-}" ] && { echo "$PI_APP_VERSION"; return; }
    local plist; plist="$(dirname "$(dirname "$APP")")/Info.plist"
    [ -f "$plist" ] && /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$plist" 2>/dev/null
}
sha() { shasum -a 256 "$1" 2>/dev/null | cut -d' ' -f1; }

[ -d "$APP" ] || die "找不到应用目录：$APP"
[ -d "$BK" ]  || die "找不到备份目录：$BK（先跑 bash backup-app.sh --from-dmg <官方DMG>）"

VER="$(app_version)"
BKVER="$(sed -n 's/^app_version=//p' "$BK/MANIFEST.txt" 2>/dev/null | head -1)"

echo "═══ UI 定制回滚 ═══"
echo "当前应用版本: ${VER:-未知}    备份采集版本: ${BKVER:-未知}"

# --- 1. 版本守卫 -------------------------------------------------------------
if [ -n "$BKVER" ] && [ -n "$VER" ] && [ "$BKVER" != "$VER" ] && [ $FORCE -ne 1 ]; then
    cat <<EOF >&2

❌ 已拒绝回滚：备份采集于 v$BKVER，当前应用是 v$VER。
   .orig 是旧版本的产物，硬塞进新版大概率白屏或样式错乱。

正确做法（任选）：
  A. 想留在新版 + 想回干净态：
     bash "$RT/backup-app.sh" --from-dmg ~/Downloads/Pi-Agent-Desktop-$VER-mac-universal.dmg
     bash "$RT/revert.sh"
  B. 想直接消失定制（不依赖备份）：用官方 DMG 重装 App（最干净）：
     cp 项目里的 backup/installer/*.dmg 挂载 → 拖 App 到 /Applications
  C. 确实要用旧备份强还原（风险自负）：bash "$RT/revert.sh" --force
EOF
    exit 3
fi
[ $FORCE -eq 1 ] && echo "⚠️  --force：跳过版本守卫"

# --- 2. 冻结看护 -------------------------------------------------------------
mkdir -p "$RT"
if [ -f "$FROZEN" ]; then
    echo "· 看护已是冻结状态"
else
    cat > "$FROZEN" <<'EOF'
此文件存在 → Pi Agent Desktop UI 补丁看护（launchd com.user.pi-ui-patch / watch_and_apply.sh）
将跳过自动重打补丁。删掉本文件或执行 patch-on.sh 即可恢复自动看护。
EOF
    echo "✅ 已冻结看护（$FROZEN）——防止 1 小时内补丁被自动打回"
fi
[ $KEEP_PATCHED -eq 1 ] && { echo "（--keep-patched：仅冻结，未回滚）"; exit 0; }

# --- 3. 回滚前快照 -----------------------------------------------------------
mkdir -p "$SNAP"
PRE="$SNAP/pre-revert-$(date '+%Y%m%d-%H%M%S').tar.gz"
if tar czf "$PRE" -C "$APP" .next/static/chunks components 2>/dev/null; then
    echo "✅ 回滚前快照：$PRE"
else
    echo "⚠️ 快照失败（继续回滚）"
fi

# --- 4. 逐文件还原（fail-soft） ----------------------------------------------
echo
echo "▶ 还原官方原版文件："
ok=0; skip=0
restored_js=()   # 数组：App 路径含空格（"Pi Agent Desktop.app"），字符串拼接会被 for 词切分误报
for f in "$BK"/*.orig; do
    [ -f "$f" ] || continue
    base="$(basename "$f" .orig)"
    case "$base" in
        *.js|*.css) target="$APP/.next/static/chunks/$base" ;;
        *.ts|*.tsx) target="$(find "$APP/components" -type f -name "$base" 2>/dev/null | head -1)" ;;
        *) target="" ;;
    esac
    if [ -z "$target" ]; then
        echo "  · 跳过 $base（目标路径未知）"; skip=$((skip+1)); continue
    fi
    if [ ! -f "$target" ]; then
        echo "  · 跳过 $base（目标不存在：$target）"; skip=$((skip+1)); continue
    fi
    if ! cp "$f" "$target" 2>/dev/null; then
        echo "  ❌ 失败 $base（权限？）"; skip=$((skip+1)); continue
    fi
    # 5. 校验
    h_ok=""
    exp="$(grep -F "  $(basename "$f")" "$BK/MANIFEST.txt" 2>/dev/null | awk '{print $1}' | head -1)"
    [ -n "$exp" ] && { [ "$(sha "$target")" = "$exp" ] && h_ok="sha256✓" || h_ok="sha256✗"; }
    case "$base" in *.js) restored_js+=("$target") ;; esac
    echo "  ✅ $base → ${target#$APP/}  $h_ok"
    ok=$((ok+1))
done
echo "  还原 $ok 个，跳过 $skip 个"

# --- 6. 语法校验（白屏首要原因就是 JS 语法坏） -------------------------------
NODE=""
for c in node "$HOME/.pi/agent/bin/node" /opt/homebrew/bin/node /usr/local/bin/node; do
    command -v "$c" >/dev/null 2>&1 && { NODE="$c"; break; }
done
if [ -n "$NODE" ] && [ ${#restored_js[@]} -gt 0 ]; then
    echo
    echo "▶ 语法校验（$NODE --check）："
    for j in "${restored_js[@]}"; do
        if $NODE --check "$j" 2>/dev/null; then echo "  ✅ $(basename "$j")"
        else echo "  ❌ $(basename "$j") 语法错误！备份文件可能损坏"; fi
    done
fi

# --- 7. 清缓存 --------------------------------------------------------------
if [ -z "${PI_NO_CACHE:-}" ]; then
    rm -rf "$CACHE/Cache/Cache_Data" 2>/dev/null
    rm -rf "$CACHE/Code Cache"/* 2>/dev/null
    echo
    echo "✅ 已清缓存"
fi

cat <<EOF

✅ 回滚完成（干净原版）。请完全退出 Pi Agent Desktop（Cmd+Q）后重新打开。
   想重新启用定制：bash "$RT/patch-on.sh"
   看当前状态    ：bash "$RT/status.sh"
EOF
