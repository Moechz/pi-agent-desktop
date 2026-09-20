#!/bin/bash
# ============================================================================
# Pi Agent Desktop 定制版 —— 一条命令发布（v<上游>-<序号>，如 0.8.8-2）
#
# 前提：上游版本未变（变了先跑 precheck-update.sh 适配 + 重新解包 app-official）；
#       P 系补丁已测试稳定；git 工作区干净。
#
# 用法：
#   bash release.sh 0.8.8-2            # 完整发布（构建→门禁→tag→上传）
#   bash release.sh 0.8.8-2 --dry      # 只构建+门禁+校验，不打 tag 不上传
#
# 内置的门禁与坑（全部真机踩过）：
#   ① 隐私/署名门禁：产物与文档零第三方人名、零本机用户名（Moechz 唯一署名）
#   ② 双平台确定性：win/mac chunk sha256 必须一致
#   ③ 上传走代理 127.0.0.1:7890（>100M 直连 uploads.github.com 必断）
#   ④ hdiutil 僵尸挂载先清；DMG→本地用普通 cp（clonefile 跨设备失败）
#   ⑤ .DS_Store 与 rm 竞赛：find -depth -delete
# ============================================================================
set -euo pipefail

VER="${1:?用法：bash release.sh <版本号> 如 0.8.8-2}"
DRY=0; [ "${2:-}" = "--dry" ] && DRY=1
cd "$(dirname "$0")"
PROJ="$PWD"
WB="$PROJ/windows-build"
RT="$HOME/.pi-ui-patches"
NODE="$HOME/.pi/agent/bin/node"
export PATH="/tmp/gh_2.101.0_macOS_arm64/bin:$PATH"
PROXY="http://127.0.0.1:7890"

step() { echo; echo "════ $* ════"; }

# ---------- 预检 ----------
step "0/7 预检"
[ -x "$NODE" ] || { echo "❌ 缺 node：$NODE"; exit 1; }
[ -n "$(git status --porcelain)" ] && { echo "❌ git 工作区不干净，先提交"; git status --short; exit 1; }
diff -q apply_patches.py "$RT/apply_patches.py" >/dev/null || echo "⚠️ 运行时补丁器与项目不一致（以项目版构建，发布后记得部署运行时）"
curl -s -m 5 -o /dev/null -x "$PROXY" https://github.com || { echo "❌ 代理 $PROXY 不通"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "❌ gh 未登录"; exit 1; }
echo "✅ 预检通过"

# ---------- Windows ----------
step "1/7 Windows：重打补丁面"
cd "$WB"
find app-custom -depth -delete 2>/dev/null || rm -rf app-custom
cp -Rc app-official app-custom 2>/dev/null || cp -R app-official app-custom
find app-custom -name ".DS_Store" -delete
PI_STANDALONE="$WB/app-custom/resources/standalone" python3 "$PROJ/apply_patches.py" | tail -3
rm -f app-custom/resources/app-update.yml
"$NODE" --check app-custom/resources/standalone/.next/static/chunks/*.js && echo "✅ win chunk 语法"

step "2/7 Windows：封装 exe"
sed -i '' "s/VER=\"[0-9.]*-[0-9]*\"/VER=\"$VER\"/" build-installer.sh
sed -i '' "s/(0\.8\.8[^')]*)/($VER)/; s/'0\.8\.8[^']*'/'$VER'/" installer-src/install.ps1
./build-installer.sh | tail -2

# ---------- macOS ----------
step "3/7 macOS：官方 DMG 重演 + 打包"
for m in /private/tmp/pidmg.*; do [ -d "$m" ] && hdiutil detach "$m" >/dev/null 2>&1 || true; done
rm -rf /tmp/pi-mac-build; mkdir -p /tmp/pi-mac-build
MP="$(mktemp -d /tmp/pidmg.XXXXXX)"
DMG="$(ls "$RT"/backup/installer/*.dmg | head -1)"
hdiutil attach -nobrowse -readonly -mountpoint "$MP" "$DMG" >/dev/null 2>&1
cp -R "$MP"/*.app /tmp/pi-mac-build/
hdiutil detach "$MP" >/dev/null 2>&1; rmdir "$MP" 2>/dev/null || true
APP="$(ls -d /tmp/pi-mac-build/*.app)"
PI_STANDALONE="$APP/Contents/Resources/standalone" python3 "$PROJ/apply_patches.py" | tail -3
rm -f "$APP/Contents/Resources/app-update.yml"
"$NODE" --check "$APP/Contents/Resources/standalone/.next/static/chunks/"*.js && echo "✅ mac chunk 语法"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$WB/Pi-Agent-Desktop-Custom-$VER-macOS-universal.zip"

# ---------- 门禁 ----------
step "4/7 门禁：确定性 + 隐私/署名"
WIN_SHA=$(shasum -a 256 app-custom/resources/standalone/.next/static/chunks/0wz_4dmun1la1.js | cut -d' ' -f1)
MAC_SHA=$(shasum -a 256 "$APP/Contents/Resources/standalone/.next/static/chunks/0wz_4dmun1la1.js" | cut -d' ' -f1)
[ "$WIN_SHA" = "$MAC_SHA" ] || { echo "❌ 双平台 chunk 不一致：$WIN_SHA vs $MAC_SHA"; exit 1; }
echo "✅ 双平台 chunk 一致：${WIN_SHA:0:16}…"
BAD=0
for d in app-custom "$APP"; do
  H=$(grep -rl "Chasen\|chasen\|Liao\|liao\|zhoustarstar\|/Users/zhou\|ghp_[A-Za-z0-9]\{8\}\|tnas-57" "$d" 2>/dev/null \
      | grep -v "node_modules/.*/\(package.json\|LICENSE\|README\)" | head -3)
  [ -n "$H" ] && { echo "❌ 隐私/署名门禁失败：$H"; BAD=1; }
done
"$HOME/tools/7zip/7zz" e -so "Pi-Agent-Desktop-Custom-Setup-$VER.exe" "README-安装说明.txt" 2>/dev/null | grep -qi "chasen\|liao" && { echo "❌ 安装说明含人名"; BAD=1; }
[ $BAD -eq 0 ] && echo "✅ 隐私/署名门禁通过（Moechz 唯一署名，零第三方人名/本机用户名）" || exit 1

step "5/7 校验和 + 提交"
cd "$WB"
shasum -a 256 "Pi-Agent-Desktop-Custom-$VER-macOS-universal.zip" "Pi-Agent-Desktop-Custom-Setup-$VER.exe" > SHA256SUMS.txt
cat SHA256SUMS.txt
cd "$PROJ"
git add -A
git commit -m "release v$VER：双平台定制包（win exe + mac zip，chunk ${WIN_SHA:0:16}）" | head -2
git push origin main

if [ $DRY -eq 1 ]; then echo; echo "✅ DRY 模式结束：构建与门禁全过，未打 tag 未上传"; exit 0; fi

step "6/7 tag + Release（走代理）"
git tag -a "v$VER" -m "v$VER 定制发布"
git push origin "v$VER"
export HTTPS_PROXY="$PROXY" HTTP_PROXY="$PROXY"
cat > /tmp/release-notes.md <<EOF
## Pi Agent Desktop 定制版 v$VER

**版本规则**：\`<上游版本>-<我们的 release 序号>\`。维护/发布：Moechz。
完整校验和见仓库 \`windows-build/SHA256SUMS.txt\`。

### 安装
**macOS**：解压拖入 /Applications 覆盖；未签名若提示"已损坏"：\`xattr -cr "/Applications/Pi Agent Desktop.app"\`
**Windows**：双击 exe（免管理员）。SmartScreen → 更多信息 → 仍要运行。

### 说明
- 两平台均**已禁用自动更新**（官方更新会覆盖全部定制）。升级请等本仓库新 \`-N\` 版本。
- 定制仅前端渲染层，会话/配置与官方版互通。
EOF
gh release create "v$VER" \
  "Pi-Agent-Desktop-Custom-$VER-macOS-universal.zip" \
  "Pi-Agent-Desktop-Custom-Setup-$VER.exe" \
  --title "Pi Agent Desktop 定制版 v$VER" --notes-file /tmp/release-notes.md

step "7/7 验证"
gh release view "v$VER" --json assets -q '.assets[] | "\(.name)  \(.size)字节"'
echo; echo "✅ 发布完成：https://github.com/Moechz/pi-agent-desktop/releases/tag/v$VER"
echo "⚠️ 发布说明里的 SHA 前缀需按 SHA256SUMS.txt 手动核对补全"
