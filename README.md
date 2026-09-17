# pi-agent-UI-change-memo — Pi Agent Desktop 界面定制备忘

对 Pi Agent Desktop（`/Applications/Pi Agent Desktop.app`）所做的 **6 组 UI 定制补丁**的完整档案：
补丁内容、技术原理、自动重打工具、原始文件备份。目的：**应用更新覆盖定制后能快速恢复**。

> 最后验证时间：2026-09-17 · 适配版本：当前安装版（chunk `0wz_4dmun1la1.js` + CSS `0_d0l-y8ld00j.css`）

---

## 一、定制内容一览

| # | 名称 | 效果 |
|---|---|---|
| P1 | 会话只留结果（v2） | 任务执行中实时可见全过程；**任务完成后**隐藏思考块、工具调用、中间叙述消息、消息内非末尾文本——每轮只显示最后一条文字结果 |
| P2 | 输入框边框加强 | 未聚焦边框从"几乎隐形"改为跟随文字颜色 24%（暗黑=白/浅色=深灰） |
| P3 | 侧边栏平铺+状态点+折叠箭头 | 所有项目目录分组默认展开（点击组头/会话即切换）；每个会话前有状态圆点：🟢绿光=任务执行中，⚫灰=空闲；组头有执行中计数徽章；**组头左侧 ▼/▲ 箭头可按目录收起/展开会话**（▼=收起态点击向下展开，▲=展开态点击向上收起，不影响点击组头切换项目） |
| P5 | 侧边栏菜单字体对齐 DSH | 侧边栏改用 DSH Desktop 同款系统字体栈（PingFang SC 等，中文更清晰）；组头/会话标题/cwd 行 13px、meta/按钮/路径 12px（原 10.5-12px 混杂偏小）；+New 按钮只留绿色 + 号；侧边栏默认宽 347px |
| P6 | 菜单弹窗不透明无色偏 | 全部菜单/弹窗/弹卡背景不透明：popover 系（右键菜单、下拉、对话框、toast）用 var(--bg) 与主题背景同色；flyout 二级弹卡、危险提示卡同改 var(--bg)；工具面板/模态框表头/权限确认按钮等 65% 半透明表面去 alpha 变实。明暗自适应 |
| P7 | 输入框下方图标加大 | 工具行图标 15→18/14→17/13→16/11→14px（附件、模型选择器、模式切换、工具预设、更多控件）；右下角发送按钮图标 15→18px（与左下角附件图标同尺寸） |

## 二、更新后被覆盖怎么办

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

# 回滚全部定制（恢复官方原版）
bash    ~/.pi-ui-patches/revert.sh
# 然后完全退出 Pi Agent Desktop（Cmd+Q）重新打开
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
├── revert.sh            # 一键回滚全部补丁（归档副本）
├── backup/              # 当前版本的原始文件备份（用于精确回滚）
│   ├── 0wz_4dmun1la1.js.orig        # 编译 chunk 原始版（回滚目标）
│   ├── 0_d0l-y8ld00j.css.orig       # 主题 CSS 原始版（P6 回滚目标）
│   ├── *.patchNonly                  # 各阶段中间态（调试参考）
│   └── *.tsx.orig / helpers.ts.orig  # 源码原始版
└── logs/                # （看护日志实际在 ~/.pi-ui-patches/watch.log）
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

## 六、Windows 分发版（分给同事）

`windows-build/` 内有独立流水线：官方 Windows Setup 解包 → 同一 `apply_patches.py` 打
7 组补丁 → 7z.sfx 封装免管理员安装器（用户数据空白、已禁自动更新）。
产物、隐私扫描结论、重建步骤见 `windows-build/README.md`；技术细节见 `PATCHES.md` §8。
