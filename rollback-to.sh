#!/bin/bash
# ============================================================================
# Pi Agent Desktop UI 补丁 —— 回滚补丁集到任意历史版本
#
# 场景：改了 100 项，前 99 项是好的，第 100 项改坏了 → 回到第 99 项。
# 原理：每项修改 = 一个 git 提交。把 apply_patches.py 换成指定提交的版本，
#       从官方原版（pristine）重新长出补丁 = 精确回到那一项完成时的状态。
#
# 用法：
#   bash rollback-to.sh <commit|tag>     # 如 bash rollback-to.sh 9640fd3
#                                        #     bash rollback-to.sh v0.8.8-custom.2
#   bash rollback-to.sh --list           # 列出可用存档点（最近 20 个提交+tag）
#
# 设计要点：
#   - 用 git show 提取旧版补丁器，**不动项目工作区**（项目保持最新版，
#     方便你继续修第 100 项；修好后再按标准流程部署回来）
#   - 流程：git show → 覆盖运行时补丁器 → revert.sh(还原原版+冻结看护)
#           → patch-on.sh(旧补丁器重演 + 解冻 + 备份用户数据)
#   - 修好第 100 项后回到最新版：
#       cp <项目>/apply_patches.py ~/.pi-ui-patches/ && bash ~/.pi-ui-patches/patch-on.sh
#
# 环境变量（测试用）：PI_UI_HOME / PI_STANDALONE
# ============================================================================
set -u

PROJ="$(cd "$(dirname "$0")" && pwd)"
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"

cd "$PROJ" || { echo "❌ 不在项目目录内：$PROJ" >&2; exit 1; }

if [ "${1:-}" = "--list" ] || [ "${1:-}" = "-l" ]; then
    echo "═══ 可用存档点（提交 + tag，新的在上）═══"
    git log --format="%h  %ad  %s" --date=format:"%m-%d %H:%M" | head -20
    echo; echo "═══ tags ═══"; git tag | tail -5
    exit 0
fi

REV="${1:-}"
[ -n "$REV" ] || { sed -n '2,24p' "$0"; exit 2; }

# 解析提交号（不存在则报错退出）
FULL="$(git rev-parse --verify --quiet "$REV^{commit}")" \
    || { echo "❌ 无效的提交/tag：$REV（用 --list 查看）" >&2; exit 1; }
SHORT="$(git rev-parse --short "$FULL")"
SUBJ="$(git log -1 --format=%s "$FULL")"

echo "═══ 补丁集回滚到存档点 ═══"
echo "目标: $SHORT  $SUBJ"

# 工作区有未提交改动时警告（不影响本命令，但提醒那可能是没存档的新改动）
if [ -n "$(git status --porcelain -- apply_patches.py)" ]; then
    echo "⚠️  项目里的 apply_patches.py 有未提交改动（可能包含还没存档的工作！）"
    read -r -p "继续回滚运行时？（y=继续 / N=中止）" ans
    case "$ans" in y|Y) ;; *) echo "已中止（建议先 git add+commit 存档）"; exit 0 ;; esac
fi

# 1) 提取该版本的补丁器 → 运行时
if ! git show "$FULL:apply_patches.py" > "$RT/apply_patches.py"; then
    echo "❌ 该提交里没有 apply_patches.py（太早的提交？）" >&2; exit 1
fi
echo "✅ 已提取 $SHORT 版补丁器 → $RT/apply_patches.py"

# 2) 还原官方原版（版本守卫 + 冻结看护）
bash "$RT/revert.sh" || { echo "❌ revert 失败，App 可能仍在原版/半补丁态"; exit 1; }

# 3) 用旧补丁器重演（解冻 + 数据备份 + 清缓存）
bash "$RT/patch-on.sh" || { echo "❌ 旧补丁器重演失败（该版本锚点与当前 App 不符？）"; exit 1; }

# 4) 回滚后验收：chunk 语法必须通过（存档点本身可能带 bug，如 9640fd3 的 P17 三元语法错）
NODE=""
for c in node "$HOME/.pi/agent/bin/node" /opt/homebrew/bin/node; do
    command -v "$c" >/dev/null 2>&1 && { NODE="$c"; break; }
done
if [ -n "$NODE" ]; then
    BAD=0
    APPCH="${PI_STANDALONE:-/Applications/Pi Agent Desktop.app/Contents/Resources/standalone}/.next/static/chunks"
    for j in "$APPCH"/*.js; do
        "$NODE" --check "$j" 2>/dev/null || { echo "❌ 语法坏：$(basename "$j")"; BAD=1; }
    done
    if [ $BAD -eq 1 ]; then
        cat <<'EOF' >&2

⚠️⚠️ 该存档点生成的补丁语法损坏（重启会白屏）！它本身就带 bug。
   换一个存档点（bash rollback-to.sh --list 看列表，一般选更早一个），
   或直接回最新版：cp <项目>/apply_patches.py ~/.pi-ui-patches/ && bash ~/.pi-ui-patches/patch-on.sh
EOF
        exit 4
    fi
    echo "✅ 回滚后验收：全部 chunk 语法通过"
fi

cat <<EOF

✅ App 已回到 $SHORT 的定制态（$SUBJ）
   → Cmd+Q 完全退出后重开生效。

   后续：
   · 确认这就是想要的稳定态：继续用没问题，随时可再回别的存档点
   · 想修第 100 项：项目里最新 apply_patches.py 没动，修好后部署回最新版：
       cp "$PROJ/apply_patches.py" "$RT/"
       bash "$RT/patch-on.sh"
   · 以后每改一项就 git commit + push —— 提交 = 存档点，这是本命令的前提
EOF
