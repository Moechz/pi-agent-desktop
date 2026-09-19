# Pi Agent Desktop 紧急修复手册（EMERGENCY.md）

> **用途**：当 Pi Agent Desktop 白屏 / 起不来 / 界面异常 / 数据损坏时，
> 把**本文件全文**交给任何 AI 助手（Claude / ChatGPT / 其他编码代理均可），
> 让它按「§3 决策树」逐步执行。本文件**自包含**，执行者不需要任何先前上下文。
>
> 本文件有三份副本，内容应一致（以 git 里的为准）：
> ① `~/Documents/projects/pi-agent-UI-change-memo/EMERGENCY.md`（git 管理）
> ② `~/.pi-ui-patches/EMERGENCY.md`（运行时）
> ③ GitHub 公开仓库 `https://github.com/Moechz/pi-agent-desktop`（手机也能看，终极保险）

---

## 1. 背景（30 秒读懂）

- 机器：macOS。App：`/Applications/Pi Agent Desktop.app`（Electron + Next.js，v0.8.8）。
- 用户对其**前端编译产物**打了 17 组二进制补丁（P1–P17：会话只留结果、侧边栏分组、
  DSH 主题、新建目录按钮等）。补丁由**生成器脚本** `apply_patches.py` 从官方原版动态重演，
  而非手工改文件。
- 有 launchd 看护（`com.user.pi-ui-patch`）每小时检查补丁在位、每日备份用户数据。
- **核心原则：任何状态都可逆**。官方 DMG 安装包已归档，最坏情况覆盖重装必定恢复；
  用户数据（会话/记忆/模型配置）另有独立备份。**不存在不可逆的坏状态。**

## 2. 地图（所有路径，动手前先看懂）

| 路径 | 是什么 |
|---|---|
| `/Applications/Pi Agent Desktop.app/Contents/Resources/standalone` | 被补丁的 App 前端（补丁面：`.next/static/chunks/*.js\|css`、`components/`） |
| `~/.pi-ui-patches/` | **运行时权威工具+备份目录**（本文件所在地） |
| `~/.pi-ui-patches/apply_patches.py` | 补丁生成器（17 组补丁的真源，幂等，全成功才写盘） |
| `~/.pi-ui-patches/backup/pristine-0.8.8/` | 官方 DMG 提取的真原版（gold 基准，66 文件） |
| `~/.pi-ui-patches/backup/installer/*.dmg` | 官方安装包（终极还原手段） |
| `~/.pi-ui-patches/backup/*.orig` + `MANIFEST.txt` | 8 个原文件 + 版本/sha256 清单 |
| `~/.pi-ui-patches/snapshots/` | 补丁面快照（保留 10 份） |
| `~/.pi-ui-patches/userdata/` | **用户数据备份**（会话/记忆/模型配置，保留 10 份） |
| `~/.pi-ui-patches/FROZEN` | 哨兵文件：存在 = 看护冻结（不会自动重打补丁） |
| `~/Documents/projects/pi-agent-UI-change-memo/` | 归档项目（git + GitHub 远端） |
| `~/.pi/agent/` | 用户数据本体：`sessions/`（会话）、`memory/`、`models.json` 等 |
| `~/Library/Application Support/@chasen-liao/pi-agent-desktop` | App 数据目录（含缓存） |
| `~/.pi/agent/bin/node` | node 二进制（本机无系统 node，语法校验用它） |

配套脚本（都在 `~/.pi-ui-patches/`，项目里另有归档副本）：
`revert.sh`（回滚原版）｜`patch-on.sh`（重打补丁）｜`patch-off.sh`（冻结看护）｜
`backup-app.sh`（备份采集）｜`status.sh`（体检）｜`user-data-backup.sh`（数据备份/恢复）｜
`watch_and_apply.sh`（看护本体）

## 3. 决策树（先诊断，再动手；每步都有验证）

### 第 0 步：永远先跑体检（只读磁盘，App 打不开也能跑）

```bash
bash ~/.pi-ui-patches/status.sh
```

输出会标注：补丁在位与否 / 备份版本匹配 / 真原版存在 / DMG 校验 / .orig 可信 /
看护状态 / 快照 / chunk 语法 / 用户数据备份。**按下面的症状对号入座。**

### 症状 A：App 白屏 / 窗口打不开 / 前端加载失败

```bash
# 1) 还原官方原版（版本守卫+回滚前快照+sha256+node语法校验+自动冻结看护）
bash ~/.pi-ui-patches/revert.sh
# 2) 用户操作：Cmd+Q 完全退出 Pi Agent Desktop，重新打开 → 此时是官方原版界面（必然能开）
# 3) 若仍打不开（极少见）→ 官方 DMG 覆盖重装：
hdiutil attach -nobrowse ~/.pi-ui-patches/backup/installer/Pi-Agent-Desktop-0.8.8-mac-universal.dmg
cp -R "/Volumes/Pi Agent Desktop/Pi Agent Desktop.app" /Applications/    # 覆盖
hdiutil detach "/Volumes/Pi Agent Desktop"
# 用户数据在 ~/Library 和 ~/.pi 下，重装不受影响
```

修好 App 后想找回定制界面 → 见症状 B。想定位是哪个补丁坏的 → 见 §4「取证」。

### 症状 B：App 能开但界面是原版（补丁丢失 / 应用更新覆盖）

```bash
bash ~/.pi-ui-patches/patch-on.sh    # 解冻看护 + 备份用户数据 + 重打全部补丁 + 清缓存
# 然后 Cmd+Q 重启 App。若界面没变：Cmd+Shift+R 强刷
```

### 症状 C：界面错乱 / 半应用态 / 各种诡异（标准化重建，万能招）

```bash
bash ~/.pi-ui-patches/revert.sh && bash ~/.pi-ui-patches/patch-on.sh
# Cmd+Q 重启。= 从纯官方原版单遍重演全部补丁，得到最干净的定制态
```

### 症状 D：用户数据坏了（自定义模型消失 / cwd 被清空 / 会话异常）

先例：P11 补丁 bug 曾把 `models.json` 自定义供应商全写丢。回滚 App **救不回数据**，用数据备份：

```bash
# 1) 用户先 Cmd+Q 退出 App（否则运行中的 App 会把坏状态写回）
# 2) 列出备份，挑最近一份好的
bash ~/.pi-ui-patches/user-data-backup.sh --list
# 3) 恢复（有交互确认）
bash ~/.pi-ui-patches/user-data-backup.sh --restore ~/.pi-ui-patches/userdata/userdata-<时间戳>.tar.gz
# 4) 重开 App 验证
```

### 症状 E：应用自动升级了（版本号 ≠ 0.8.8）

更新会替换整个 Resources 目录 → 补丁全丢、锚点可能失配。流程：

```bash
# 1) 拿到新版官方 DMG（github.com/Chasen-Liao/pi-agent-desktop 的 releases；
#    本机直连 github.com 443 不通，走代理：curl -x http://127.0.0.1:7890 -L -o ... 或浏览器下载）
# 2) 固化新版本备份（真原版 + MANIFEST + 归档 DMG）
bash ~/.pi-ui-patches/backup-app.sh --from-dmg ~/Downloads/Pi-Agent-Desktop-<新版本>-mac-universal.dmg
# 3) 沙盒测试补丁（不碰真 App）：
rm -rf /tmp/pi-test && mkdir -p /tmp/pi-test/.next/static
cp -R ~/.pi-ui-patches/backup/pristine-<新版本>/chunks /tmp/pi-test/.next/static/chunks
cp -R ~/.pi-ui-patches/backup/pristine-<新版本>/components /tmp/pi-test/components
PI_STANDALONE=/tmp/pi-test python3 ~/.pi-ui-patches/apply_patches.py
#    成功（退出码 0，输出各组 ✅）→ 直接跳第 5 步
#    失败（报「[Px] xxx 未找到」= 锚点失配）→ 第 4 步
# 4) 锚点失配：读项目里 PATCHES.md §6「重新适配指南」，微调 apply_patches.py 顶部
#    pat_* 正则后回到第 3 步（原则：标记 __piSM + 幂等 + 全成功才写盘）
# 5) 部署到真 App 并更新 .orig：
bash ~/.pi-ui-patches/patch-on.sh
#    若提示版本守卫拒绝/backup 里 .orig 仍是旧版：重跑 backup-app.sh --from-dmg 后再 revert+patch-on
```

### 症状 F：`~/.pi-ui-patches/` 或项目目录被删（工具丢失）

```bash
git clone git@github.com:Moechz/pi-agent-desktop.git ~/Documents/projects/pi-agent-UI-change-memo
cd ~/Documents/projects/pi-agent-UI-change-memo
cp apply_patches.py revert.sh patch-on.sh patch-off.sh backup-app.sh status.sh \
   user-data-backup.sh watch_and_apply.sh ~/.pi-ui-patches/
chmod +x ~/.pi-ui-patches/*.sh
launchctl load ~/Library/LaunchAgents/com.user.pi-ui-patch.plist   # 看护
# 备份（pristine/DMG）不在 git 里（体积大）。丢了就按症状 E 重新固化，
# 或从 Downloads 里的官方 DMG / 官方 releases 重新下载
```

## 4. 给修复 AI 的规则（红 lines）

1. **先诊断后动手**：永远先跑 `status.sh`，再按决策树走，不要跳步。
2. **幂等性**：所有脚本二次运行安全；`apply_patches.py` 全部补丁成功才写盘，失败不动 App。
3. **版本守卫不可绕**：`revert.sh` 备份版本 ≠ 应用版本时拒绝执行（防旧文件塞新版白屏）。
   跨版本必须先 `backup-app.sh --from-dmg` 重新采集。`--force` 仅在用户明确知情下用。
4. **FROZEN 哨兵**：`~/.pi-ui-patches/FROZEN` 存在 = 看护冻结。`patch-on.sh` 会清掉它；
   只想冻结不回滚用 `patch-off.sh`。
5. **改任何 chunk 后必须语法校验**：`~/.pi/agent/bin/node --check <chunk.js>`
   （本机无系统 node；python3 有，用 /usr/bin/python3）。
6. **改补丁的标准流程**：改 `apply_patches.py`（项目里的）→ `/tmp/pi-test` 沙盒测 →
   二次运行验证幂等跳过 → `cp` 到 `~/.pi-ui-patches/` → 真机 `patch-on.sh` →
   更新 PATCHES.md → `git commit && git push origin main`。
7. **git 远端走 SSH**（`git@github.com:...`，HTTPS 443 被墙；代理 `127.0.0.1:7890` 可用）。
8. **取证**：白屏修复后，坏掉的定制态自动存在 `~/.pi-ui-patches/snapshots/pre-revert-*.tar.gz`，
   白屏时窗口若还开着可试 Cmd+Option+I 看 DevTools 报错——这两样是定位坏补丁的素材。
9. **改不动就退**：任何时刻觉得没把握，`revert.sh` 回官方原版是零风险兜底，用户数据毫发无损。

## 5. 深入资料（按需读，都在项目目录）

| 文件 | 内容 |
|---|---|
| `PATCHES.md` | 17 组补丁全部技术细节：锚点、变换逻辑、验证流程；**§6 重新适配指南（版本更新后必读）** |
| `README.md` | 体系总览 + 日常用法 + 白屏救援 |
| `apply_patches.py` | 补丁生成器源码（每组补丁有注释说明锚点特征） |
| `windows-build/README.md` | Windows 分发版流水线（与紧急修复无关） |

## 6. 一页速查（贴墙版）

```bash
bash ~/.pi-ui-patches/status.sh                                    # 体检
bash ~/.pi-ui-patches/revert.sh                                    # 回官方原版
bash ~/.pi-ui-patches/patch-on.sh                                  # 重打全部定制
bash ~/.pi-ui-patches/patch-off.sh                                 # 冻结看护
bash ~/.pi-ui-patches/user-data-backup.sh --list                   # 数据备份列表
bash ~/.pi-ui-patches/user-data-backup.sh --restore <文件>          # 数据恢复
grep -l __piSM "/Applications/Pi Agent Desktop.app/Contents/Resources/standalone/.next/static/chunks/"*.js   # 补丁在位？
# 白屏三连：revert.sh → Cmd+Q 重开 → 还不行 DMG 覆盖重装
```
