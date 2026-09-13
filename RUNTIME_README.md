# Pi Agent Desktop UI 补丁集

## 补丁 1：会话完成后只保留结果（全局，v2 升级）

### 效果（全局，对所有会话生效）

- **任务执行中**（消息正在流式输出）：保持原样——思考块、工具调用、文本都实时可见，方便观察进度
- **任务完成后**（含重新打开的历史会话）：
  - 思考（thinking）块 → 完全隐藏
  - 工具调用（toolCall）及其结果 → 完全隐藏
  - **中间叙述消息**（每次调工具前的进度说明）→ 整条隐藏（v2 新增：assistant 消息若后面还有 assistant 消息则为中间产物）
  - 消息内部的多个文本块 → 只保留最后一个（v2 新增）
  - 最终只显示每轮任务的最后一条文字结果；无文字的轮次整条隐藏

会话数据本身未做任何修改（`~/.pi/agent/sessions/` 完整保留），仅改变页面显示。

## 修改的文件

| 文件 | 说明 |
|---|---|
| `.next/static/chunks/0wz_4dmun1la1.js` | 编译产物（实际生效的文件），补丁 1 共 2 处 + 补丁 2 共 1 处 + 补丁 3 共 6 处 |
| `components/MessageView.tsx` | 补丁 1 源码同步（不参与运行，仅保持一致） |
| `components/ChatInput.tsx` | 补丁 2 源码同步（不参与运行，仅保持一致） |
| `components/SessionSidebar.tsx`、`session-sidebar/SessionTree.tsx`、`session-sidebar/helpers.ts` | 补丁 3 源码同步 |

原始文件备份在 `~/.pi-ui-patches/backup/`。

## 补丁 2：输入框边框加强（全局，重点暗黑模式）

原样式：未聚焦时 `1px solid color-mix(var(--border) 70%, transparent)`——暗黑模式 `--border` 仅 `rgba(255,255,255,0.08)`，再打 7 折几乎不可见。
新样式：`1px solid color-mix(var(--text) 24%, transparent)`——跟随文字颜色，暗黑模式为 24% 白、浅色模式为 24% 深灰，两个主题都清晰。聚焦时仍显示原有 accent 光环。

## 补丁 3：侧边栏项目目录平铺 + 会话运行状态点（全局）

### 项目平铺
原来：侧边栏一次只显示「当前选中项目」的会话，其它项目藏在顶部下拉框里。
现在：**所有项目目录各自成组、全部展开**，按最近活跃排序；组头显示目录名（末两段），点击组头切换项目；点击任意会话直接打开并自动切换到对应项目（文件浏览器同步跟随）。顶部下拉框仍保留。

### 会话状态点
每个会话条目前有一个圆点，侧边栏每 4 秒轮询 `/api/agent/{id}`：

- 🟢 **绿色发光** = 该会话有任务正在执行（agent 正在流式输出）
- ⚫ **灰色半透明** = 空闲 / 任务已结束

组头右侧还有绿色徽章显示该组内正在执行的任务数（如 `2 ▶`）。

### 修改文件
编译 chunk `0wz_4dmun1la1.js`（6 处：树构建器存档 window.__piBT、轮询器 window.__piSM/__piIsRun、分组渲染、空态修正、状态圆点）
+ 源码 `components/SessionSidebar.tsx`、`components/session-sidebar/SessionTree.tsx`、`components/session-sidebar/helpers.ts`。

## 生效方式（三个补丁相同）

完全退出 Pi Agent Desktop（Cmd+Q）→ 重新打开。已清渲染缓存，无需其他操作。
若打开后仍未生效：窗口内按 Cmd+Shift+R 强制刷新。

## 回滚（一次性回滚全部补丁）

```bash
bash ~/.pi-ui-patches/revert.sh
```

然后重启应用。

## 注意事项

1. **应用自动更新会覆盖此补丁**（electron-updater 更新会替换整个 Resources 目录）。
   更新后如需保留效果，需重新打补丁（编译 chunk 文件名会变化，不能直接复用备份覆盖）。
2. 会话导出（/export）、分支树等其它视图不受影响，仍包含完整过程。
3. 该修改会使 app 包内文件与代码签名不一致；本机已放行的应用不受影响（Gatekeeper 只在首次启动检查）。
