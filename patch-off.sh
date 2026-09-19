#!/bin/bash
# 冻结 UI 补丁看护（launchd 每小时自动重打 → 加 FROZEN 哨兵后跳过）。
# 场景：手动回滚到原版后不希望被自动打回；或应用升级后先别让旧补丁乱打。
# 用法：
#   bash patch-off.sh             # 只冻结看护
#   bash patch-off.sh --revert    # 冻结 + 回滚到原版（= revert.sh --keep-patched 的逆操作套件）
# 环境变量（测试用）：PI_UI_HOME
set -u
RT="${PI_UI_HOME:-$HOME/.pi-ui-patches}"
if [ "${1:-}" = "--revert" ]; then
    exec bash "$RT/revert.sh"
fi
cat > "$RT/FROZEN" <<'EOF'
此文件存在 → Pi Agent Desktop UI 补丁看护（launchd com.user.pi-ui-patch / watch_and_apply.sh）
将跳过自动重打补丁。删掉本文件或执行 patch-on.sh 即可恢复自动看护。
EOF
echo "✅ 看护已冻结（$RT/FROZEN）。恢复：bash $RT/patch-on.sh"
