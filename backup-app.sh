#!/bin/bash
# ============================================================================
# Pi Agent Desktop UI 定制 —— 备份采集器
#
# 作用：把「真原版」+「当前补丁面」+「清单」落盘，确保任何时候都能一键回到干净态。
#   L1 真原版（gold）：从官方 DMG 提取补丁面文件  → backup/pristine-<版本>/
#   L2 打补丁前的采集：backup/*.orig              （靠 patch-off 前采集，或由 DMG 校验）
#   L3 快照：补丁面 tar 包                         → ~/.pi-ui-patches/snapshots/
#
# 用法：
#   bash backup-app.sh --from-dmg ~/Downloads/Pi-Agent-Desktop-<ver>-mac-universal.dmg
#   bash backup-app.sh --snapshot            # 只做一次补丁面快照（改补丁前跑一次最稳）
#   bash backup-app.sh                       # 校验现有 .orig 与真原版是否一致
#
# 环境变量（测试用）：PI_STANDALONE / PI_UI_HOME / PI_APP_VERSION
# ============================================================================
set -u

APP="${PI_STANDALONE:-/Applications/Pi Agent Desktop.app/Contents/Resources/standalone}"
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
BK="$RT/backup"
SNAP="$RT/snapshots"
KEEP=10   # 保留最近快照数

die() { echo "❌ $*" >&2; exit 1; }

app_version() {
    [ -n "${PI_APP_VERSION:-}" ] && { echo "$PI_APP_VERSION"; return; }
    local plist; plist="$(dirname "$(dirname "$APP")")/Info.plist"
    [ -f "$plist" ] && /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$plist" 2>/dev/null
}

sha() { shasum -a 256 "$1" 2>/dev/null | cut -d' ' -f1; }

# --- 参数 -------------------------------------------------------------------
FROM_DMG=""
DO_SNAPSHOT=0
while [ $# -gt 0 ]; do
    case "$1" in
        --from-dmg) FROM_DMG="$2"; shift 2 ;;
        --snapshot) DO_SNAPSHOT=1; shift ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) die "未知参数：$1" ;;
    esac
done

VER="$(app_version)"
[ -n "$VER" ] || die "读不到应用版本（$APP 是否存在？）"
mkdir -p "$BK" "$SNAP"

echo "═══ Pi Agent Desktop UI 备份 ═══"
echo "应用版本 : $VER"
echo "补丁面   : $APP"
echo "备份目录 : $BK"

# --- L1：从 DMG 提取真原版 ---------------------------------------------------
if [ -n "$FROM_DMG" ]; then
    [ -f "$FROM_DMG" ] || die "找不到 DMG：$FROM_DMG"
    MP="$(mktemp -d /tmp/pidmg.XXXXXX)"
    echo
    echo "▶ 挂载 DMG 提取真原版…"
    hdiutil attach -nobrowse -readonly -mountpoint "$MP" "$FROM_DMG" >/dev/null 2>&1 \
        || die "DMG 挂载失败"
    SRC="$(ls -d "$MP"/*.app 2>/dev/null | head -1)/Contents/Resources/standalone"
    [ -d "$SRC" ] || { hdiutil detach "$MP" >/dev/null 2>&1; die "DMG 里没有 standalone 目录"; }
    PDIR="$BK/pristine-$VER"
    rm -rf "$PDIR"; mkdir -p "$PDIR/chunks"
    cp "$SRC/.next/static/chunks/"*.js  "$PDIR/chunks/" 2>/dev/null
    cp "$SRC/.next/static/chunks/"*.css "$PDIR/chunks/" 2>/dev/null
    cp "$SRC/server.js" "$PDIR/" 2>/dev/null   # P19 补丁面（服务器响应头）
    [ -d "$SRC/components" ] && cp -R "$SRC/components" "$PDIR/components"
    hdiutil detach "$MP" >/dev/null 2>&1
    echo "  ✅ 真原版已存：$PDIR（$(find "$PDIR" -type f | wc -l | tr -d ' ') 个文件）"
    # DMG 自身归档一份（若还没归档过）
    INSDIR="$BK/installer"
    mkdir -p "$INSDIR"
    if [ ! -f "$INSDIR/$(basename "$FROM_DMG")" ]; then
        echo "  ▶ 归档安装包（$(du -h "$FROM_DMG" | cut -f1)）…"
        cp "$FROM_DMG" "$INSDIR/" && echo "  ✅ $INSDIR/$(basename "$FROM_DMG")"
    fi
    DMG_PATH="$INSDIR/$(basename "$FROM_DMG")"
else
    # 未指定 DMG 时，从已归档位置找（运行时目录优先，项目归档兑底）
    for c in "$BK/installer/"*.dmg \
             "$HOME/Documents/projects/pi-agent-UI-change-memo/backup/installer/"*.dmg \
             "$HOME/Documents/projects/pi-agent-UI-change-memo/backup/"installer-*.dmg; do
        [ -f "$c" ] && { DMG_PATH="$c"; break; }
    done
fi

# --- 清单 -------------------------------------------------------------------
MAN="$BK/MANIFEST.txt"
{
    echo "# Pi Agent Desktop UI 补丁备份清单（backup-app.sh 生成，勿手改）"
    echo "app_version=$VER"
    echo "created=$(date '+%F %T')"
    echo "installer=${DMG_PATH:-}"
    [ -n "${DMG_PATH:-}" ] && [ -f "$DMG_PATH" ] && echo "installer_sha256=$(sha "$DMG_PATH")"
    echo "# 真原版逐文件 sha256（gold，来自官方 DMG）"
    if [ -d "$BK/pristine-$VER" ]; then
        (cd "$BK" && find "pristine-$VER" -type f | sort | while read -r f; do echo "$(sha "$BK/$f")  $f"; done)
    fi
    echo "# 打补丁前采集的原版 sha256"
    for f in "$BK"/*.orig; do [ -f "$f" ] && echo "$(sha "$f")  $(basename "$f")"; done
} > "$MAN"
echo "  ✅ 清单：$MAN"

# --- 校验：.orig 是否仍等于真原版 -------------------------------------------
if [ -d "$BK/pristine-$VER" ]; then
    echo
    echo "▶ 校验 .orig 与真原版一致性："
    ok=0; bad=0
    for f in "$BK"/*.orig; do
        [ -f "$f" ] || continue
        base="$(basename "$f" .orig)"
        p="$(find "$BK/pristine-$VER" -type f -name "$base" 2>/dev/null | head -1)"
        [ -n "$p" ] || { echo "  ⚠️  $base：真原版里没找到（跳过）"; continue; }
        if [ "$(sha "$f")" = "$(sha "$p")" ]; then ok=$((ok+1)); else
            bad=$((bad+1)); echo "  ❌ $base：.orig 与真原版不一致（回滚用它可能出问题）"
        fi
    done
    echo "  一致 $ok 个／异常 $bad 个"
fi

# --- L3：快照 ---------------------------------------------------------------
if [ $DO_SNAPSHOT -eq 1 ]; then
    echo
    echo "▶ 生成补丁面快照…"
    T="$(date '+%Y%m%d-%H%M%S')"
    OUT="$SNAP/standalone-v$VER-$T.tar.gz"
    # 只打包会被改动的面（chunks + components，约 2.5MB）：够用且秒级完成
    tar czf "$OUT" -C "$APP" .next/static/chunks components 2>/dev/null \
        || die "快照失败（$APP 结构异常？）"
    echo "  ✅ $OUT（$(du -h "$OUT" | cut -f1)）"
    ls -1t "$SNAP"/standalone-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | while read -r old; do
        rm -f "$old"; echo "  · 清理旧快照 $(basename "$old")"
    done
    echo "  （保留最近 $KEEP 份）"
fi

echo
echo "✅ 备份完成。回滚用：bash $RT/revert.sh"
