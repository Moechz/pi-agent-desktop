#!/bin/bash
# Pi Agent Desktop 定制版 Windows 安装器构建脚本
# 产物：Pi-Agent-Desktop-Custom-Setup-<ver>.exe（7z.sfx 自解压安装器，免管理员）
# 依赖：~/tools/7zip/7zz（7-Zip 独立版）+ 7z.sfx（官方模块，取自 7-Zip 官方安装器）
# 流程：app-custom（已打补丁）→ staging → payload.7z → sfx+config+7z 拼接 → 校验
set -euo pipefail
cd "$(dirname "$0")"

VER="0.8.8"
SEVENZ="$HOME/tools/7zip/7zz"
SFX="$HOME/tools/7zip/7z.sfx"
APP="app-custom"                     # 已打 UI 补丁的应用目录
OUT="Pi-Agent-Desktop-Custom-Setup-${VER}.exe"

[ -x "$SEVENZ" ] || { echo "缺少 7zz：$SEVENZ"; exit 1; }
[ -f "$SFX" ]    || { echo "缺少 sfx 模块：$SFX"; exit 1; }
[ -d "$APP" ]    || { echo "缺少应用目录：$APP（先跑 apply_patches.py）"; exit 1; }

echo "[1/5] 组装 staging ..."
rm -rf staging payload.7z "$OUT"
mkdir -p staging
cp -R "$APP" staging/app
# 清除 macOS 目录元数据（厂商包自带 + 本机 Finder 生成，均无必要）
find staging -name ".DS_Store" -delete

# PowerShell 脚本需 UTF-8 BOM（Windows PowerShell 5.1 才能正确读中文）
for f in install.ps1 uninstall.ps1; do
  printf '\xef\xbb\xbf' > "staging/$f"; cat "installer-src/$f" >> "staging/$f"
done
cp "installer-src/README-安装说明.txt" staging/
# sfx 配置必须 UTF-8 无 BOM
cp installer-src/sfx-config.txt sfx-config.tmp

echo "[2/5] 压缩 payload.7z（约 600MB，需数分钟）..."
"$SEVENZ" a -t7z -mx=7 -mmt=8 payload.7z ./staging/app ./staging/install.ps1 \
  ./staging/uninstall.ps1 "./staging/README-安装说明.txt" >/dev/null

echo "[3/5] 拼接自解压安装器 ..."
cat "$SFX" sfx-config.tmp payload.7z > "$OUT"
rm -f sfx-config.tmp

echo "[4/5] 结构校验（7z 应能识别内嵌归档，路径应在归档根级）..."
"$SEVENZ" l "$OUT" | sed -n '9,14p'
"$SEVENZ" l "$OUT" | grep -E " (app|install.ps1|uninstall.ps1|README-[^ ]*\.txt)$" || true

echo "[5/5] 回环校验：解包比对与 app-custom 一致 ..."
rm -rf /tmp/pi-setup-verify
"$SEVENZ" x -y -o/tmp/pi-setup-verify "$OUT" >/dev/null
diff -rq "$APP" /tmp/pi-setup-verify/app | grep -v "app-update.yml" || true
diff <(tail -n +2 staging/install.ps1) <(tail -n +2 /tmp/pi-setup-verify/install.ps1) \
  && echo "install.ps1 内容一致（仅 BOM 差异）"
cmp -s staging/uninstall.ps1 /tmp/pi-setup-verify/uninstall.ps1 && echo "uninstall.ps1 字节一致"
echo "校验的文件数：$(find /tmp/pi-setup-verify/app -type f | wc -l | tr -d ' ') / 应为 $(find "$APP" -type f | wc -l | tr -d ' ')-1（少 app-update.yml）"

ls -lh "$OUT"
echo "完成：$OUT"
