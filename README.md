# pi-agent-UI-change-memo — Pi Agent Desktop 界面定制备忘

对 Pi Agent Desktop（`/Applications/Pi Agent Desktop.app`）所做的 **7 组 UI 定制补丁**的完整档案：
补丁内容、技术原理、自动重打工具、原始文件备份。目的：**应用更新覆盖定制后能快速恢复**。

> 最后验证时间：2026-09-20（回滚消防演练通过：打补丁→revert→与官方真原版逐字节一致）· 适配版本：当前安装版 v0.8.8（chunk `0wz_4dmun1la1.js` + CSS `0_d0l-y8ld00j.css`）

---

## 一、定制内容一览

| # | 名称 | 效果 |
|---|---|---|
| P1 | 会话只留结果（v2） | 任务执行中实时可见全过程；**任务完成后**隐藏思考块、工具调用、中间叙述消息、消息内非末尾文本——每轮只显示最后一条文字结果 |
| P2 | 输入框边框加强 | 未聚焦边框从"几乎隐形"改为跟随文字颜色 24%（暗黑=白/浅色=深灰） |
| P3 | 侧边栏平铺+状态点+折叠箭头 | 所有项目目录分组默认展开（点击组头/会话即切换）；运行中会话前有 🟢绿点（空闲无点）；组头有执行中计数徽章；**组头左侧 ▼/▲ 箭头可按目录收起/展开会话**（▼=收起态点击向下展开，▲=展开态点击向上收起，不影响点击组头切换项目） |
| P5 | 侧边栏菜单字体对齐 DSH | 侧边栏改用 DSH Desktop 同款系统字体栈（PingFang SC 等，中文更清晰）；组头/会话标题/cwd 行 13px、meta/按钮/路径 12px（原 10.5-12px 混杂偏小）；+New 按钮只留绿色 + 号；侧边栏默认宽 347px |
| P6 | 菜单弹窗不透明无色偏 | 全部菜单/弹窗/弹卡背景不透明：popover 系（右键菜单、下拉、对话框、toast）用 var(--bg) 与主题背景同色；flyout 二级弹卡、危险提示卡同改 var(--bg)；工具面板/模态框表头/权限确认按钮等 65% 半透明表面去 alpha 变实。明暗自适应 |
| P7 | 输入框下方图标统一 18px | 工具行全部图标（附件、模型选择器、模式切换、工具预设、更多控件）、右下角发送按钮、执行中停止方块、完成提示音喇叭统一 18px（与左下角附件同尺寸）；思考级别弹窗图标 11→14px |
| P8 | 全应用 DSH 风格（字体+色彩+字号阶梯） | 全局换 DSH Desktop 字体栈（PingFang SC 等）+ 抗锯齿；背景/文字/边框/状态色映射 DSH 设计令牌（明暗两套），**强调色保留 Pi 原橙**；正文行高 1.71，markdown 标题对齐 DSH 绝对字号；二轮：字号阶梯对齐 DSH（按钮/菜单项 13px、次级 12→13、说明 11→12），修复表单控件 text-[Npx] 被无层 font:inherit 压制导致设置菜单字体不变的问题 |
| P15 | 会话条目紧凑化 | 删去标题下方 meta 行（时间+消息数，排版乱）；标题行最右固定位置显示紧凑相对时间（now/Nm/Nh/Nd，数字等宽不跳动，悬停看完整时间戳）；取消空闲灰点，只保留运行中绿点；行高自定义类 __piRowH + patch_css 注入规则（现 40px；⚠ Tailwind h-[Npx] 是编译期类，改字符串无效——五轮调高不生效的根因）；**目录名与会话标题文字左对齐**（固定 21px 圆点槽，标题恒从 35px 起，绿点落文件夹图标正下方且不引起标题跳动）；组头文件夹图标 14→17px |
| P16 | 顶部路径栏 → 新建目录钮 | 侧边栏顶部不再显示当前工作目录路径；第二行统一为四个同规格 chrome 方形图标钮（28px），左→右：新会话（图标+文字）/ 新建目录（直通系统文件夹选择器）/ ▾ 历史目录下拉 / 刷新；整行内联 marginTop:24 下移、右对齐。📄 详 PATCHES.md §4f |
| P17 | 新会话输入框目录名 + ▾ 切换目录 | 点“+ 新会话”后输入框左上角显当前目录名（末段，hover 全路径），▾ 弹窗切换：「已添加目录」=会话目录∪自选过目录（localStorage 记忆，全量不截断；每行 13px 文件夹 icon + 目录名，当前项行尾打勾，可滚动）/ 使用默认目录 / 选择其他目录…；目录清单为弹窗打开时自 fetch /api/sessions 计算；复用 ej(id,cwd)（与侧边栏“+ 新会话”同函数，目录在第 2 参）；仅新会话态显示。📄 详 PATCHES.md §4g |
| P18 | 资源管理器默认收起 | 重启后左侧栏底部「资源管理器」区块默认收起（原默认展开）；仅改 useState 默认值 /*__piExpl*/!1，点击展开逻辑不变、不持久化；收起时会话列表自动占满剩余高度 |

## 二、更新后被覆盖怎么办

> 🚨 **App 白屏/起不来/数据坏了**：别读本文，直接开
> [`EMERGENCY.md`](EMERGENCY.md)（零上下文 AI 可执行的决策树修复手册，
> 运行时副本在 `~/.pi-ui-patches/EMERGENCY.md`，GitHub 上也有）。

### 备份与回滚（先读这个）

所有备份/回滚/体检命令见 **[BACKUP-RESTORE.md](BACKUP-RESTORE.md)**。五条命令：

```bash
bash ~/.pi-ui-patches/status.sh    # 体检（版本/补丁/备份可信度/看护/快照/语法）
bash ~/.pi-ui-patches/revert.sh    # 🚨 修坏了 → 一键回滚到干净原版（自动冻结看护+快照+校验）
bash ~/.pi-ui-patches/patch-on.sh  # 回滚后恢复定制（解冻+重打+清缓存）
bash ~/.pi-ui-patches/patch-off.sh # 只冻结看护（不让 launchd 自动打补丁）
bash ~/.pi-ui-patches/backup-app.sh --snapshot  # 改补丁前打一份快照（强烈建议）
```

保险层级：真原版（从官方 DMG 提取，66 文件）→ `.orig`（8 个，已验证与 DMG 逐字节一致）
→ 官方 DMG 归档（backup/installer/）→ 补丁面快照（最近 10 份）。

### 自动（已配置，无需操作）
`launchd` 看护（`com.user.pi-ui-patch`）在**登录时和每小时**检查补丁标记（`__piSM`）：
- 补丁在位 → 跳过
- 被更新抹掉 → 自动运行 `apply_patches.py` 重打 + 清渲染缓存 + 发系统通知
- 重打失败（应用内部结构大改，锚点失配）→ 发通知提醒，此时需人工适配（见 `PATCHES.md` §重新适配指南）

### 手动
```bash
# 立即检查并重打（幂等，已打过则跳过；运行时权威副本在 ~/.pi-ui-patches）
python3 ~/.pi-ui-patches/apply_patches.py

# 手动触发一次看护
bash    ~/.pi-ui-patches/watch_and_apply.sh

# 体检（补丁在位/备份可信/语法/看护状态，一眼看清）
bash    ~/.pi-ui-patches/status.sh

# 回滚全部定制（恢复官方原版；版本守卫+回滚前快照+sha/node双校验+自动冻结看护）
bash    ~/.pi-ui-patches/revert.sh
# 然后完全退出 Pi Agent Desktop（Cmd+Q）重新打开

# 只冻结看护不回滚（防止 1 小时内被自动打回；动手改 UI 前先跑这个）
bash    ~/.pi-ui-patches/patch-off.sh        # --revert = 冻结+回滚
# 解冻 + 立即重打补丁
bash    ~/.pi-ui-patches/patch-on.sh

# 备份采集（应用升级到新版本后跑一次）
bash    ~/.pi-ui-patches/backup-app.sh --from-dmg ~/Downloads/Pi-Agent-Desktop-<版本>-mac-universal.dmg
bash    ~/.pi-ui-patches/backup-app.sh --snapshot     # 改补丁前拍快照（保留最近 10 份）

# 上游更新预检（新版 DMG 出来后：沙盒试打，不动真 App；--adopt 顺便采集新版备份）
bash    ~/.pi-ui-patches/precheck-update.sh ~/Downloads/<新官方DMG> [--adopt]

# 回滚到任意历史存档点（改坏了第 N 项，回到第 N-1 项）
bash    ~/.pi-ui-patches/rollback-to.sh --list        # 看存档点（每项修改一个 git 提交）
bash    ~/.pi-ui-patches/rollback-to.sh <提交号>       # 回到该存档点（带语法验收）

# 用户数据备份（会话/记忆/模型配置；看护每日自动，也可手动）
bash    ~/.pi-ui-patches/user-data-backup.sh            # 立即备份
bash    ~/.pi-ui-patches/user-data-backup.sh --list     # 列出
bash    ~/.pi-ui-patches/user-data-backup.sh --restore <文件>  # 恢复（先 Cmd+Q）
```

### 白屏 / 前端加载不出来时（Terminal.app 救援，不依赖 App 界面）

补丁只写 `.next/static/chunks/*.js|css`、`components/*`（P11/P14 另涉 node_modules 内
@earendil-works 包），**主进程 app.asar / Electron 二进制从不被触碰**，最坏也只是渲染层白屏。
救援顺序（全部可在「终端.app」里完成）：

```bash
# ① 还原官方文件（带版本守卫，升级后不会拿旧备份硬塞）
bash ~/.pi-ui-patches/revert.sh
# ② 渲染缓存已由 revert.sh 自动清理
# ③ Cmd+Q 完全退出后重开；仍不行 → ④ 终极：官方 DMG 覆盖重装（必定恢复，用户数据不受影响）
hdiutil attach ~/.pi-ui-patches/backup/installer/Pi-Agent-Desktop-0.8.8-mac-universal.dmg
# 挂载后把 App 拖进 /Applications 覆盖
```

### 验证补丁是否在位
```bash
grep -ls "__piSM" "/Applications/Pi Agent Desktop.app/Contents/Resources/standalone/.next/static/chunks/"*.js
# 有输出 = 在位；无输出 = 被覆盖（跑一次 apply_patches.py）
```

## 三、目录结构

```
pi-agent-UI-change-memo/
├── README.md            # 本文件：总览 + 用法
├── PATCHES.md           # 技术细节：每处补丁的锚点、变换逻辑、重新适配指南（给下次的助手看）
├── sync-from-runtime.sh # 一键把运行时脚本同步进本项目并 git 提交
├── apply_patches.py     # ★ 语义锚点自动重打器（归档副本；运行时在 ~/.pi-ui-patches/）
├── watch_and_apply.sh   # 看护脚本（归档副本；launchd 实际运行 ~/.pi-ui-patches/ 下的那份）
├── com.user.pi-ui-patch.plist  # launchd 配置（归档副本；已安装于 ~/Library/LaunchAgents/）
├── revert.sh            # 一键回滚（硬化版：版本守卫/回滚前快照/fail-soft/sha+node校验/自动冻结）
├── backup-app.sh        # 备份采集器：--from-dmg 固化真原版+MANIFEST；--snapshot 拍快照
├── status.sh            # 体检报告（补丁/备份可信度/语法/看护/快照）
├── patch-off.sh         # 冻结看护（FROZEN 哨兵）；--revert = 冻结+回滚
├── patch-on.sh          # 解冻 + 备份用户数据 + 立即重打补丁 + 清缓存
├── user-data-backup.sh  # 用户数据备份（会话/记忆/模型配置；--list/--restore/--auto）
├── rollback-to.sh       # 回滚补丁集到任意 git 存档点（改坏第 N 项时回到第 N-1 项）
├── precheck-update.sh   # 上游更新预检：新 DMG 沙盒试打逐组报告命中/失配，--adopt 采集新版备份
├── backup/              # 项目侧镜像（git 管历史）：*.orig + pristine-<版本>/（DMG 提取的真原版）
│   ├── 0wz_4dmun1la1.js.orig        # 编译 chunk 原始版（回滚目标）
│   ├── 0_d0l-y8ld00j.css.orig       # 主题 CSS 原始版（P6 回滚目标）
│   ├── pristine-0.8.8/              # 官方 DMG 真原版（gold，sha256 权威基准）
│   └── installer-*.dmg              # 官方安装包归档（gitignore，体积大）
└── logs/                # （看护日志实际在 ~/.pi-ui-patches/watch.log）

**运行时备份布局**（`~/.pi-ui-patches/backup/`，launchd/脚本实际使用的一份）：
`pristine-0.8.8/`（真原版）+ `installer/`（DMG）+ `MANIFEST.txt`（版本+逐文件 sha256）
+ `*.orig`。`snapshots/` 存补丁面快照；`FROZEN` 存在 = 看护冻结。
```

### 运行时 vs 归档（重要）

- **运行时（权威）**: `~/.pi-ui-patches/` —— launchd 每小时执行这里的脚本。
  放 home 根目录是因为 `~/Documents` 受 macOS TCC 保护，launchd 无权读取其中的脚本（已踩坑）。
- **归档（本项目）**: `~/Documents/projects/pi-agent-UI-change-memo/` —— 文档 + 备份 + 脚本快照，
  git 管理历史。适配新版本后跑一次 `sync-from-runtime.sh` 归档。

## 四、原理一句话

应用更新会替换整个 `Resources` 目录，编译 chunk 的**文件名和内部压缩变量名都会变**，
所以不能靠"拷备份回去"。`apply_patches.py` 用**稳定的结构特征**定位——CSS 类名
（`flex-1 min-w-0`、`t-acc-panel-inner`、`composer-shell`）、React prop 键名（`selectedSessionId:`
、`message:`、`isStreaming:`）、CSS 变量名、字面样式串——动态捕获当次构建的压缩变量名再注入补丁，
因此小版本更新（压缩变量名变化）通常无需人工介入。

## 五、注意事项

1. **大版本 UI 重构**（源码改了类名/组件结构）会导致锚点失配 → 脚本退出码 1 并通知，
   此时按 `PATCHES.md` §重新适配指南 重新适配。
2. 应用自动更新后，看护最迟 1 小时内补上；等不及就手动跑一次 `apply_patches.py`。
3. 重打后需**重启应用**才生效（看护已自动清渲染缓存；若界面未变按 Cmd+Shift+R）。
4. 本项目已 git 初始化，适配新版本后记得提交。
5. **用户数据另有一套独立备份**（`user-data-backup.sh`）：会话历史/记忆/models.json 等，
   看护每天自动备一次、patch-on 前必备。App 文件回滚（revert.sh）救不回被补丁 bug
   写坏的数据（P11 models.json 事故先例），那要靠 `user-data-backup.sh --restore`。

## 六、Windows 分发版（分给同事）

`windows-build/` 内有独立流水线：官方 Windows Setup 解包 → 同一 `apply_patches.py` 打
17 组补丁 → 7z.sfx 封装免管理员安装器（用户数据空白、已禁自动更新）。
macOS 定制包（zip）同流水线产出：官方 DMG 提取 → 打补丁 → ditto zip。
产物、隐私扫描结论、重建步骤见 `windows-build/README.md`；技术细节见 `PATCHES.md` §8。

**版本号规则**：`<上游版本>-<我们的 release 序号>`，如 `0.8.8-1` = 上游 0.8.8 第 1 次发布。
发布 = GitHub Release（tag `v0.8.8-1`）+ 双平台产物 + SHA256SUMS。
