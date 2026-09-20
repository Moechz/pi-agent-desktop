# 备份与回滚手册（BACKUP-RESTORE.md）

> 目标：改坏 UI（白屏 / 功能异常 / 补丁打架）后的任何时候，都能在 **1 分钟内**回到
> 「干净官方原版」或「上一次正常的定制态」。本手册 = 你唯一需要看的东西。

## 一、三层保险（都已就位）

| 层级 | 内容 | 位置 | 用途 |
|---|---|---|---|
| L1 真原版 gold | 从官方 DMG 逐字节提取的补丁面（66 文件，含 sha256 清单） | `~/.pi-ui-patches/backup/pristine-0.8.8/`（归档副本在项目 `backup/pristine-0.8.8/`） | 验证任何备份是否可信；对照基线 |
| L2 打补丁前采集 | `*.orig`（8 个，已验证与 L1 逐字节一致） | `~/.pi-ui-patches/backup/` | revert.sh 的还原源 |
| L3 官方安装包 | `Pi-Agent-Desktop-0.8.8-mac-universal.dmg`（sha256 已登记） | 项目 `backup/installer/`（gitignored） | 终极还原：整个 App 重装 |
| 快照 | 补丁面 tar（680K/份，留最近 10 份；改补丁前/回滚前自动生成） | `~/.pi-ui-patches/snapshots/` | 回到「上一次正常的定制态」 |

**MANIFEST.txt**（`~/.pi-ui-patches/backup/`）记录：应用版本、DMG 路径+sha256、
每个备份文件的 sha256。`status.sh` 会用它做一致性体检。

## 二、五条命令（背下来）

```bash
bash ~/.pi-ui-patches/status.sh        # 体检：版本/补丁在位/备份可信度/看护/快照/语法
bash ~/.pi-ui-patches/revert.sh        # 🚨 修坏了 → 回滚到干净原版（含 5 道保险，见下）
bash ~/.pi-ui-patches/patch-on.sh      # 回滚后想恢复定制：解冻看护 + 立即重打 + 清缓存
bash ~/.pi-ui-patches/patch-off.sh     # 只冻结看护（不让 launchd 自动打补丁）
bash ~/.pi-ui-patches/hard-restart.sh  # 硬重启：退出→清 Chromium 缓存→重开（部署后看不到修改时用）
bash ~/.pi-ui-patches/backup-app.sh --snapshot  # 改补丁前打一份快照（强烈建议）
```

日常开发节奏：**每次动手改补丁前** `backup-app.sh --snapshot`；
改完测试通过后 git commit。出事时按下一节流程走。

## 三、故障处置速查

| 症状 | 处置 |
|---|---|
| 白屏 / 界面不加载 | ① `status.sh` 看「语法」行（node --check 会指出坏 chunk）→ ② 直接 `revert.sh` 回原版 → ③ Cmd+Q 重启 → ④ 好了以后再排查补丁 |
| 改完补丁、重启了却还是旧 UI | Next.js 对静态 chunk 发 `immutable`（一年）缓存头，改名不改内容的部署方式命不中回源。P19 已让服务器发 no-cache 治本；存量旧条目需 `hard-restart.sh`（退出态清缓存）清一次。⚠ 清缓存必须在应用完全退出后做，运行中清会被旧进程写回 |
| 某个功能行为怪（如点按钮目录被清空） | 同上先回滚保命；再用 git log 找到上一个好 commit 重打 |
| 应用自动更新（0.8.8→0.8.9） | 看护 1 小时内自动重打；失败会有系统通知 → 打开本项目让助手重新适配。⚠️ 此时 `.orig` 已过时，revert.sh 会拒绝执行并给出指引（防把旧产物塞进新版造成白屏） |
| 想完全卸掉定制 | `revert.sh` + 把 `~/Library/LaunchAgents/com.user.pi-ui-patch.plist` 删掉，或保留 plist 但留 FROZEN |
| 万劫不复（连 revert 都不行） | DMG 重装：`open 项目/backup/installer/*.dmg` → 拖入 /Applications 覆盖 |

## 四、revert.sh 的 5 道保险（为什么可以放心）

1. **版本守卫**：备份版本 ≠ 当前应用版本 → 拒绝（exit 3），提示先从新版 DMG 重采
   或直接重装；`--force` 可越过（风险自负）。
2. **回滚前自动快照**：`snapshots/pre-revert-*.tar.gz`，后悔药。
3. **逐文件 fail-soft**：某文件缺失/权限失败不会中断整个回滚（旧版 `set -e` 会半途死）。
4. **还原后校验**：sha256 对 MANIFEST + `node --check` 语法（白屏首因就是 JS 语法坏）。
5. **自动冻结看护**：写 `~/.pi-ui-patches/FROZEN` 哨兵——否则 launchd 1 小时内会把
   补丁又打回来，你的回滚「不生效」。（2026-09-20 真实踩过：手动还原后以为坏了，
   其实是缺这层。）

看护脚本自身也升级了：FROZEN 存在时不动手；补丁在位时顺带对全部 chunk 跑
`node --check`，语法损坏会弹系统通知（预警白屏）。

## 五、应用更新后的正确姿势

```bash
# 1. 等看护自动重打（1 小时内），或手动：
bash ~/.pi-ui-patches/patch-on.sh
# 2. 失败（锚点失配）→ 打开本项目，按 PATCHES.md §6 让助手重新适配
# 3. 适配好后刷新备份基线（从新版 DMG）：
bash ~/.pi-ui-patches/backup-app.sh --from-dmg ~/Downloads/Pi-Agent-Desktop-<新版本>-mac-universal.dmg
#    然后把新 DMG 也拷进 项目/backup/installer/ 归档
```

## 六、脚本清单

| 脚本 | 作用 |
|---|---|
| `backup-app.sh` | 采集/校验备份 + 生成 MANIFEST；`--from-dmg` 提取真原版；`--snapshot` 打补丁面快照 |
| `revert.sh` | 一键回滚到干净原版（5 道保险） |
| `patch-on.sh` / `patch-off.sh` | 解冻+重打 / 冻结看护（`--revert` = 冻结+回滚） |
| `status.sh` | 体检报告（版本/补丁/备份/看护/快照/语法 7 项） |
| `watch_and_apply.sh` | launchd 看护（已加 FROZEN 检查 + 语法快检） |

**权威副本在 `~/.pi-ui-patches/`（launchd 要求避开 TCC 保护区），项目里是 git 归档。**
改动后用 `sync-from-runtime.sh`（项目→归档）或手动 `cp`（项目→运行时）双向同步。
