#!/bin/bash
# ============================================================================
# Pi Agent Desktop 用户数据备份（会话/记忆/模型配置/应用本地存储）
#
# 为什么需要：补丁 bug 可能通过 App 行为写坏用户数据（先例：P11 补丁曾导致
# models.json 自定义供应商全部丢失；P17 曾把 cwd 设置清空）。回滚 App 文件
# 救不回已写坏的数据——这份备份才是数据侧兜底。
#
# 备份内容（真实用户数据，排除缓存/可重装的运行时）：
#   ~/.pi/agent/sessions/          全部会话历史（45M 级）
#   ~/.pi/agent/memory/            agent 长期记忆
#   ~/.pi/agent/{models.json,models-store.json,auth.json,AGENTS.md}
#   App 数据目录的 Local Storage / Session Storage / Cookies（设置类）
#   不含：opt/（node 运行时）、skills/、Cache 系（可重建）
#
# 用法：
#   bash user-data-backup.sh                      # 立即备份（保留最近 10 份）
#   bash user-data-backup.sh --list               # 列出备份
#   bash user-data-backup.sh --restore <文件>     # 恢复（务必先 Cmd+Q 退出 App）
#   bash user-data-backup.sh --auto               # 距上次 >20h 才执行（看护每小时调）
#
# 环境变量（测试用）：PI_UI_HOME
# ============================================================================
set -u

PI_AGENT="$HOME/.pi/agent"
APPDATA="$HOME/Library/Application Support/@chasen-liao/pi-agent-desktop"
DEST="${PI_UI_HOME:-$HOME/.pi-ui-patches}/userdata"
KEEP=10

mkdir -p "$DEST"

# --- 参数 -------------------------------------------------------------------
MODE="backup"; ARG=""
case "${1:-}" in
    --list)    MODE="list" ;;
    --restore) MODE="restore"; ARG="${2:-}" ;;
    --auto)    MODE="auto" ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    "")        : ;;
    *)         echo "未知参数：$1" >&2; exit 2 ;;
esac

latest() { ls -1t "$DEST"/userdata-*.tar.gz 2>/dev/null | head -1; }

if [ "$MODE" = "list" ]; then
    n=$(ls -1 "$DEST"/userdata-*.tar.gz 2>/dev/null | wc -l | tr -d ' ')
    echo "共 $n 份，保留最近 $KEEP 份："
    ls -lhlt "$DEST"/userdata-*.tar.gz 2>/dev/null | awk '{print $5, $9}' | sed "s|$DEST/||"
    exit 0
fi

if [ "$MODE" = "restore" ]; then
    [ -f "$ARG" ] || { echo "❌ 找不到备份文件：$ARG" >&2; exit 1; }
    cat <<EOF >&2
⚠️  恢复将覆盖当前用户数据（会话/记忆/模型配置/本地存储）。
   请先完全退出 Pi Agent Desktop（Cmd+Q），否则运行中的 App 会把旧状态写回去。
EOF
    read -r -p "确认恢复？[y/N] " ans
    case "$ans" in y|Y) ;; *) echo "已取消"; exit 0 ;; esac
    tar xzf "$ARG" -C "$HOME" && echo "✅ 已恢复：$ARG（重开 App 生效）"
    exit 0
fi

# --- auto：距上次备份不足 20h 则跳过 ----------------------------------------
if [ "$MODE" = "auto" ]; then
    LAST="$(latest)"
    # 上次备份的 mtime 比「20 小时前」还新 → 跳过（静默，看护每小时调用）
    if [ -n "$LAST" ] && [ "$(stat -f %m "$LAST")" -gt "$(date -v-20H +%s)" ]; then
        exit 0
    fi
fi

# --- 组装备份清单（只收存在的路径，bsdtar 缺文件会报错）----------------------
MEMBERS=()
for p in \
    ".pi/agent/sessions" \
    ".pi/agent/memory" \
    ".pi/agent/models.json" \
    ".pi/agent/models-store.json" \
    ".pi/agent/auth.json" \
    ".pi/agent/AGENTS.md" \
    "Library/Application Support/@chasen-liao/pi-agent-desktop/Local Storage" \
    "Library/Application Support/@chasen-liao/pi-agent-desktop/Session Storage" \
    "Library/Application Support/@chasen-liao/pi-agent-desktop/Cookies"
do
    [ -e "$HOME/$p" ] && MEMBERS+=("$p")
done
[ ${#MEMBERS[@]} -gt 0 ] || { echo "❌ 没有可备份的用户数据（路径都不存在？）" >&2; exit 1; }

# --- 备份 --------------------------------------------------------------------
OUT="$DEST/userdata-$(date '+%Y%m%d-%H%M%S').tar.gz"
tar czf "$OUT" -C "$HOME" "${MEMBERS[@]}" 2>/dev/null \
    || { echo "⚠️ 备份有警告（文件被占用？一般无碍）：$OUT"; }
[ -s "$OUT" ] || { echo "❌ 备份失败"; exit 1; }

# --- 清理旧备份 --------------------------------------------------------------
ls -1t "$DEST"/userdata-*.tar.gz 2>/dev/null | tail -n +$((KEEP+1)) | while read -r old; do
    rm -f "$old"
done

if [ "$MODE" = "backup" ]; then
    echo "✅ 用户数据已备份：$OUT（$(du -h "$OUT" | cut -f1)，含 ${#MEMBERS[@]} 项，保留 $KEEP 份）"
fi
