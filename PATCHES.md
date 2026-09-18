# PATCHES.md — 补丁技术档案

> 目标读者：未来需要重新适配这些补丁的人/助手。请先读 README.md 了解全貌。

## 0. 背景知识

- 应用是 Electron + Next.js standalone 构建，运行时只读编译产物
  `/Applications/Pi Agent Desktop.app/Contents/Resources/standalone/.next/static/chunks/*.js`。
  **改 .tsx 源码不影响运行**（本项目早期改过的源码仅作参考镜像）。
- chunk 按内容哈希命名，每次构建文件名和内部压缩变量名（如 `c7`、`y`、`D`）都会变。
- 渲染进程从内嵌 server（端口 30141）拉 chunk，带 `Cache-Control: immutable` 缓存；
  每次改文件后要清 `~/Library/Application Support/@chasen-liao/pi-agent-desktop/Cache/Cache_Data` 和 `Code Cache`。
- 当前版本的关键编译标识符（`0wz_4dmun1la1.js`）：
  - `X`=SessionSidebar 组件（props: selectedCwd=`p`, onCwdChange=`g`, sessions state=`y`, loadSessions=`D`…）
  - `Y`=SessionTreeItem、`K`=SessionItem（prop `session`=`e`）
  - `c1`=AssistantMessageView（props: message=`e`, isStreaming=`t`, blocks=`m`…）
  - `c2`=BlockView、`cQ`=MessageView（消息分发）、`c7`=MessageList（messages=`e`）

## 1. 定位目标 chunk

`apply_patches.py::find_chunk()`：同时含 `t-acc-panel-inner`（折叠面板）、`sidebar.noSessions`
（i18n 键）、`"/api/sessions"`、`composer-shell`（输入框类名）的那个 `.js`。

## 2. P1 — 会话只留结果（v2）

**产品语义**：任务执行中（消息 `isStreaming=true`）一切照旧实时显示；完成后：
- 块级（`c1` 内）：只渲染最后一个 `text` 块，`thinking`/`toolCall` 渲染 null；
- 消息级（`cQ` 分发处）：assistant 消息若一个 text 块都没有 → 整条 null；
- 消息列表级（`c7`）：assistant 消息的后一条也是 assistant → 本条是中间叙述 → null；
- 保留的最后一条消息内也只显示末尾 text 块（块级规则兜底）。

**变换**（3 处）：

1. 块级 map：锚 = `children:M.map((b,q)=>(0,n.jsx)(C,{block:b,toolResults:a,streamingDuration:w.get(q)??("thinking"===b.type?T:void 0),toolCallDurations:A},q))`，
   外包 IIFE：**先在 IIFE 顶部把 `!IS` 快照到新变量 `_piS`**（`var _piS=!t;`），再算最后 text 块下标 `li`，
   map 回调内条件渲染 `_piS&&("text"!==b.type||q!==li)?null:(原渲染)`。
   isStreaming 变量名 `IS` 从同组件后方的 `MSG.usage&&!IS&&`（页脚 usage 显示条件）捕获。
   ⚠ **必须快照**（2026-09-13 踩坑）：某构建里 IS 恰好叫 `t`，而 map 回调参数 `(e,t)` 的块下标也叫 `t`，
   内层遮蔽外层 → `!IS` 变成"第 0 块才判断"，toolCall 全部漏网。快照在外层作用域求值即可杜绝。
2. 消息级：锚 = `"assistant"===MSG.role?(0,n.jsx)(c1,{message:MSG,isStreaming:IS,toolResults:...,prevTimestamp:...}):`（prop 键名稳定），
   改为 `"assistant"===MSG.role?(!IS&&!(MSG.content??[]).some(b=>"text"===b.type)?null:(原渲染)):`。
3. 列表级：锚 = `MSGS.map((MSG,IDX)=>{ ... V=(0,n.jsx)(cQ,{message:MSG,`（配合 `contentVisibility:"auto"` 特征，lazy ≤2000 字符），
   注入 `V=!AG&&"assistant"===MSG.role&&(向后扫描)?null:` ——
   ⚠ 会话 jsonl 是 **assistant/toolResult 交替存储**（toolResult 是独立角色消息，cQ 里渲染 null；
   结果经 `eL` Map(toolCallId→result) 传入 c1），"下一条是 assistant"永不成立，必须向后扫描：
   从 IDX+1 起遇到 `user` 返回 false、遇到 `assistant` 返回 true（跳过 toolResult/custom），
   即"本轮内还有更晚的 assistant → 本条是中间叙述 → 隐藏"。
   `AG`=agentRunning（c7 签名 prop，从 map 前 600 字内 `agentRunning:(\w+)` 捕获）做门控：
   执行中全显、完成后才收起。
   同时给该 cQ 调用补 `isStreaming:AG`（原调用不传 → 恒 undefined）：执行中块级/消息级规则放行，
   实时可见全过程；完成后统一收起。（末尾的 streaming 消息本就显式传 `isStreaming:!0`，不受影响。）

**坑**：rf 字符串里 `\"` 会保留反斜杠字面量 → 用单引号 rf'...' 写普通引号。
（曾因此产出 `\"text\"` 造成 JSC "Invalid escape in identifier"。）

## 3. P2 — 输入框边框

未聚焦态样式串 `"color-mix(in srgb, var(--border) 70%, transparent)"`（全 chunk 唯一）
→ `"color-mix(in srgb, var(--text) 24%, transparent)"`。CSS 变量名随主题自适应，暗黑模式下清晰可见。

## 4. P3 — 侧边栏平铺 + 运行状态点 + 组头折叠箭头

**产品语义**：左侧栏不再只显示单项目会话树，而是按 cwd 分组、全部会话平铺（组按最新活动排序，
组头=项目目录名+执行中计数 `N ▶`，点击切换项目）；每会话前圆点 🟢(发光)=运行中 / ⚫(暗)=空闲。
运行状态来自**轮询** `/api/agent/{id}`（GET 只读，不会孵化会话）的 `state.isStreaming`。
组头最左侧有折叠箭头（14px、strokeWidth 3 加粗，看得清）：▼(accent色)=已收起、点击向下展开；▲(muted色)=展开中、点击向上收起；
点击箭头 `stopPropagation`，不会触发组头的切换项目。折叠状态存于组件内新增的 `useState`
（`__piCLst` map: cwd→1），应用重启后回到默认全展开。

**变换**（7 处）：
1. 树构建器存档：`Z=function(E){let T=new Map;for(let N of E)T.set(N.id,{session:N,children:[]});` … `return A(R),R}(U);`
   → 改名挂到 `window.__piBT`（首定义后复用），供分组渲染调用。
2. 轮询器注入（组件 return 前）：`window.__piSM`（状态 map + key + 4s interval）、`window.__piIsRun(id)` 访问器；
   key 变化（项目集合变）时重建。注入位置锚 = 组件根 `return(0,n.jsxs)("div",{style:{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden"}}`（取组件内第一个）。
   同位置（轮询器前）注入折叠状态 hook：`var __piCS=(0,<RCT>.useState)({}),__piCLst=__piCS[0],__piCLset=__piCS[1];`
   —— React 命名空间变量 `<RCT>`（如 `r`）从同组件 `[y,x]=(0,r.useState)([])` 捕获；
   组件体在根 return 前无提前 return（已验证），hook 顺序稳定安全。
3. 分组渲染替换：原 `Z.map((R)=>(0,n.jsx)(Y,{node:R,selectedSessionId:…,onSessionDeleted:P=>{CB?.(P),LD()},…},R.session.id))`
   整体替换为 IIFE：按 `y`(sessions) 分组→排序→每组调 `window.__piBT(arr)` 建树→渲染组头（▼/▲ 切换箭头 +
   cwd 末两段 + 徽章，**无文件夹图标**）+ 会话条目。选中项目高亮用 `p===G.cwd`（selectedCwd prop）。
   会话列表包 `paddingLeft:14` 容器形成二级菜单缩进（嵌套子会话层级线随容器整体右移）。
   箭头 onClick=`TG`（stopPropagation + `__piCLset` 切换 `__piCLst[G.cwd]`）；chevron path 收起=`M6 9l6 6 6-6`(▼)/展开=`M18 15l-6-6-6 6`(▲)；
   会话列表渲染包裹条件 `__piCLst[G.cwd]?null:tree.map(...)`（已收起的组整组隐藏）。
4. 空态改判定：`!A&&!B&&0===U.length&&`（过滤后数组）→ `0===y.length&&`（全部会话为空才显示空态）。
5. 状态圆点：SessionItem 内 `className:"flex-1 min-w-0"` 容器前插 span（8px 圆点；运行=鲜绿 #22e06b 实心 + title"running"；空闲=var(--text-muted) opacity .55）。**v2（2026-09-19）：去光晕实体圆点**——不再注入 boxShadow（旧版带 0 0 9px 2px 绿晕），transition 去掉 box-shadow 项；已部署旧产物由独立幂等的 `patch_dot_solid()` 迁移（无光晕串即跳过，不参与锚点链）。
   session 变量名从往前最近的 `function K({session:S,isSelected:` 签名捕获。
6. 自检：除 `__piSM` 外同时校验 `__piCLst` 在产物中。
7. 以上涉及侧边栏作用域变量名的，全部从组件签名
   `function X({selectedSessionId:SEL,onSelectSession:OSEL,…,selectedCwd:SCWD,onCwdChange:OCWD,…})` 捕获
   （prop 键名稳定）。React hook 编译形态是 `(0,r.useState)([])` / `(0,r.useCallback)(async(`（带 0 前缀包裹），正则要兼容。

**坑**：编译后具名函数是 `function X({...})`（function 与名字间有空格），正则须 `function\s?[\w$]*\(\{…`。

## 4b. P5 — 侧边栏菜单字体对齐 DSH Desktop

**产品语义**：侧边栏"菜单"（会话列表/组头/顶栏项目选择/底部面板）字体与字号对齐 DSH Desktop
（解包 `DSH Desktop.app/Contents/Resources/app.asar` 内 `@deepseek-ai/dsh-web-frontend` 得出参考值：
body 字体栈 `-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",
"Helvetica Neue",Helvetica,Arial,sans-serif`；菜单项 `--dsh-content-font-size-secondary: 13px`，次级 12px）。
作用域仅侧边栏根 div（注入 fontFamily），聊天区仍用 Inter。

**变换**（9 处）：
1. 根容器：在侧边栏根 `return(0,n.jsxs)("div",{style:{display:"flex",flexDirection:"column",height:"100%",
   overflow:"hidden"}` 的 style 里注入 `fontFamily:"<DSH栈>"`（JS 内层单引号）。
   ⚠ RET 坐标在 hook+poller 插入后已偏移（插入物在 RET 前），必须 `re.search(pat_ret, src[RET:])` 重定位。
2. 字号（均验证全 chunk 唯一后替换）：组头 10.5→13（P3 grouped 内）；会话标题 `text-[12px] leading-[1.4]
   overflow-hidden text-ellipsis whitespace-nowrap `→13；meta 行 `"mt-0.5 flex gap-2 text-text-dim
   text-[11px]"`→12；重命名输入（`flex-1 text-[12px] py-1.25...h-[30px]`）→13；新会话按钮
   （`sidebar-new-session-button ... text-[11px]`）→12；cwd 行 →13；cwd 路径（`font-mono text-[11px]
   ${e?...}`）→12；项目下拉项（`border-b border-divider text-left text-[11px] font-mono`）→12；
   底部面板 toggle（`fontSize:11,fontWeight:600,letterSpacing:"0.04em"`）→12。
3. +New 按钮：去 New 文字（锚 `,D("common.new")]` → `]`，D 为 i18n 变量名）；注入
   `style:{background:"var(--success-bg)",borderColor:"var(--success-border)",color:"var(--success)"}`（锚
   `"aria-label":D("sidebar.newSession"),`，⚠ 锚点截到逗号为止，含 `className:` 会把 style 插错位）。
   svg 用 currentColor 自动继承按钮 color。
4. 侧边栏默认宽度：宽度常量模块（webpack id 34442，含 `LEFT_PANEL_DEFAULT_WIDTH`/`clampPanelWidth`/
   `getDefaultPanelWidths`）默认 260 → 347（加宽 1/3；clamp 范围 220–480、45% 视口内自动收敛）。
   两处锚：`LEFT_PANEL_DEFAULT_WIDTH:260` 与 `"left",260,`（均全 chunk 唯一）。仍可手动拖边缘调整。
5. 自检标记：`PingFang SC`。

## 4c. P6 — 菜单弹窗不透明 + P7 — 输入框下方图标加大

> P3 状态圆点 v2：实体无光晕，详见 §4 第 5 条与 apply_patches.py `patch_dot_solid()`。

**P6 产品语义**：所有菜单/弹窗（右键菜单、模型/模式/预设下拉、对话框等）背景**不透明且无色偏，
明暗模式自适应**：与主题基础背景完全同色（靠 border + shadow-popover 区分层次），
不随内容透出底下文字。透明度未源是设计默认值：
`.material-popover{background:var(--material-popover);-webkit-backdrop-filter:blur(30px)saturate(160%)}`，
变量带 alpha（暗 `#161b23e6`≈90%、亮 `#ffffffdb`≈86%）；官方的不透明覆盖规则只在
`@media (prefers-reduced-transparency:reduce)` 和 `(prefers-contrast:more)` 里，普通设置不生效。

**P6 变换（v3，全局扫描后两层修复）**（CSS 文件，独立于 JS 幂等，在 main() 里先于 JS MARKER 检查执行；
两组变换各自独立幂等，部分打过的中间态也能收敛）：
- `find_css()`：`chunks/*.css` 中含 `--material-popover:` 的那个（文件名哈希随构建变）
- ① popover 族：正则 `--material-popover:#[0-9a-fA-F]+` 恰中两处（:root 与 html.dark）
  → 全部归一为 `var(--bg)`（暗 #050505 纯中性近黑 / 亮 #f8f9fc 近白，随主题自动切换；
  CSS 变量引用在使用时解析，定义顺序无关）。归一写法兼容原版带 alpha/v1 纯色/v2 三态。
  覆盖 material-popover 系菜单/下拉/对话框/toast/内部 modal 卡
- ② 弹卡/面板族：`--bg-elevated` / `--bg-panel` 各两处 8位hex → 去 alpha 保色调
  （暗 #0c1118/#10151d、亮 #ffffff/#f3f5f8）：flyout 二级弹卡、工具面板表头、
  模态框标题栏、权限确认按钮/输入框等 65% 半透明表面全部变实；hover 态仍工作
- 背景 var(--bg) 全不透明后 backdrop blur 无视觉效果，不必动

**P6b 变换（JS）**：两个不走 material-popover 的内联弹层背景直接改 var(--bg)，
与主弹窗同色无色偏：
- flyout 二级弹卡：锚 `right:"100%",marginRight:6,background:"var(--bg-elevated)"`
- 危险提示弹卡（附件出错等）：锚 `bottom:"calc(100% + 6px)",right:0,background:"var(--bg-panel)"`
（各验证全 chunk 唯一）

**遗留的透明面（有意保留）**：对话框背后的变暗遮罩 .ui-dialog-backdrop（#0006b+blur，
横幅 scrim 语义）；顶部工具栏/侧边栏/输入框的 material-toolbar/sidebar/input 毛玻璃
（ chrome 不是菜单）；消息气泡 --assistant-bg/--tool-bg（内容非弹层）；
hover/border/focus 类半透明色（本来就是设计薄涂）。若用户后续要求一并变实，
同理处理（material-input→var(--bg) 等）。

**P7 变换**（JS，三段；第三轮调整后工具行图标统一 18px）：
1. 工具行窗口（输入框下方 `style:{marginTop:8,display:"flex",alignItems:"center",gap:6,minHeight:32}`
   唯一锚点，窗口 6000 字符）：窗口内恰一个的 `svg",{width:"15"→"18"`（附件）、`"13"→"18"`
   （更多控件 sliders）、`"11"→"14"`（思考级别选择器，在弹窗内不常见故保持适度）
2. 三个工具行组件触发图标（**压缩名 dt/ds/da 会变，锚 props 签名**，统一 18px）：
   模型选择器 `function X({isStreaming:,model:,modelNames:,modelList:,onModelChange:})` 首个 14→18；
   模式切换 `function X({mode:,disabled:,onChange:})` 首个 14→18；
   工具预设 `function X({isStreaming:,toolPreset:,onToolPresetChange:})` 首个 11→18
   （各取签名后 2500 字符窗口内首个命中；弹窗内 10px 勾选标不动）
3. 发送按钮图标 15→18（用户反馈右下角仍太小，对齐左下角附件 18px）：锚
   `svg",{width:"15",height:"15",viewBox:"0 0 14 14"` 全 chunk 恰 2 处——主发送
   （`chat.sendMessage`）与排队追问（`chat.sendRunningAgent`/`queueFollowUp`）两个 38px
   圆钮（`composer-icon-button`）内的箭头，两处全换；viewBox 14 与工具行图标（viewBox 24）
   区分不互撞，替换等长不影响后续坐标
4. 右组尾部两个小图标（第四轮反馈"图案占位太小"）：执行中停止钮方块 10→18
   （`chat.stopAgent`，锚含 aria-hidden + rect x:"1.5"，与 compacting 方块区分）；
   完成提示音喇叭 12→18（`chat.*DoneSound`，volume-2/volume-x 两态恰 2 处，
   锚 polygon points "11 5…" 喇叭形）
   ⚠ 坑：**单子元素 svg 编译为 `children:(0,n.jsx)(`（无数组括号），多子元素才是
   `children:[(0,n.jsx)(`**——停止钮锚点曾因此 0 命中

**P7 坑**：自检标记不能用裸 `width:"18"` 或仅 svg 头（附件与更多控件同为 18x18 viewBox 24
 strokeWidth 1.8），必须延伸到首个子元素（附件 `rect x:"3"` / 更多控件 `line x1:"4"`）验
count==1；发送图标用 viewBox 14 签名验 count==2。

**P6 坑**：部分打过 CSS 的中间态（popover 已 var(--bg) 但 elevated 未打）不能早退 return，
必须逐组独立判断；正则去 alpha 用 `sub(lambda)` 避免反斜杠组引用问题。

## 4d. P8 — 全应用 DSH 风格（字体栈 + 色彩 + 正文排版）

**产品语义**：整个应用的字体与配色对齐 DSH Desktop（解包其 app.asar 内
`@deepseek-ai/dsh-web-frontend` CSS + `dsh-client-ui-theme` 设计令牌得出参考值）。
P5 只做了侧边栏字体，本组扩展到全局且首次引入**色彩体系**替换。

**参考体系**（DSH 设计令牌）：
- 字体栈：`-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",
"Microsoft YaHei","Helvetica Neue",Helvetica,Arial,sans-serif`（body 同款 + antialiased）
- 色板：neutral-bluish 灰阶（00 #fff … 1000 #0f1115）+ deepseek 品牌蓝
  （400 #679efe / 450 #5686fe / 500 #4176e6）+ 状态色（green-500 #22c55e / amber-500 #f59e0b…）
- alias 映射：light bg=00、label-primary=1000、secondary=700、tertiary=400、
  link=deepseek-500、interactive-hover=#2631480f；dark bg=950 #151517、label=50 #f9fafb、
  secondary=300、tertiary=600、link=deepseek-400、hover=#ffffff14
- 排版：正文 14px/24px、xs 13px/20px；markdown h1 21/30 h2 19/28 h3 18/26 h4 14(w600)

**变换**（`patch_css_dsh()`，纯 CSS **文件末尾追加**，零锚点依赖，幂等标记 `/*__piDSH*/`）：
1. 追加 `:root{…}` 浅色整套变量重定义：bg/panel/elevated/hover/selected/border/text×4/
   accent×3/user 气泡/assistant/tool 气泡/code×2/success/danger/warning/info×3/focus-ring
   + `--font-sans`（Pi 原值在 `@layer theme` 内，非 layer 规则天然压过）
2. 追加 `html.dark,.dark{…}` 深色整套（双选择器兜底 class 挂 body 场景；同特异性后写胜）
3. 追加 `html,body{font-family:DSH栈}`（压过原 `var(--font-inter)` 规则；
   `--font-inter` 仅这一处引用，不必碰 next/font 哈希类）+ body 抗锯齿
4. 追加 `.markdown-body{line-height:1.71}` + h1-h4 绝对字号（正文本就 14px 不动）

**字号未动说明**：正文 14px、输入框 14px、侧边栏 13/12px 均已与 DSH 对齐；
UI chrome 的 fontSize:12 inline（79 处）保留 Pi 节奏，避免大面积布局回归（如需可后续单独做）。

**字号阶梯（P8b/P8c，二轮补丁，修复“设置菜单字体没变”反馈）**：
- 根因①：Pi 全局有一条**无 layer** 的 `button,input,textarea,select{font:inherit}`
  （紧跟 html,body 规则之后，非 @layer base 那份 preflight），无层规则压过一切
  @layer，导致所有表单控件的 Tailwind `text-[Npx]` 字号类全部失效，按钮字号
  恒等于 body 14px（Pi 原生行为，与 P8 无关）。
- 根因②：中文字形在原版（Inter 无 CJK→回退 PingFang）与 P8 后（DSH 栈）
  本就相同，所以中文菜单字体“看不出变化”是预期现象；真正能感知的是字号阶梯。
- P8b（CSS 追加，标记 /*__piDSH2*/）：`button{font-size:13px}`（DSH 菜单项
  xs-13；input/textarea/select 仍 inherit=14 对齐 DSH 输入 14）+
  `.text-[12px]→13px`、`.text-[11px]→12px`（无层后写胜，压过 utilities）。
- P8c（JS 扫掠，一次性标记 /*__piFS*/ 追加在 chunk 末尾注释）：inline
  `fontSize:12→13`（79 处）、`11→12`（52 处），≤10 的徽标不动。
  ⚠ 幂等必须用标记：扫掠后文件里仍有 12（原 11 升来），“0 命中即已打”会连升两级；
  ⚠ 必须在 P1-P7 之后执行（P5 锚点引用原始 fontSize 11/12 值）。
- 已知限制：原生 <select> 展开后的下拉列表由 macOS 系统渲染，字体不受页面 CSS 控制。

**P8 坑**：P6 的幂等检查（`--bg-elevated/--bg-panel` 6位×2）会被 P8 追加块里的
同名变量干扰，patch_css() 必须只在 DSH_MARK 之前的前段检测/替换，再拼回尾部。

**色彩映射总表**（Pi 变量 → DSH 值，light / dark）：

| Pi 变量 | light | dark | DSH 来源 |
|---|---|---|---|
| --bg | #ffffff | #151517 | bg-base = bluish-00 / 950 |
| --bg-panel | #f5f6f7 | #1b1b1c | bluish-60 / 900 |
| --bg-elevated | #ffffff | #2c2c2e | bluish-00 / 850（hovercard bg）|
| --bg-hover | #2631480f | #ffffff14 | interactive-bg-hover |
| --bg-selected | #2631481a | #ffffff24 | interactive-bg-active |
| --border | #e1e5ee | #ffffff1a | bluish-200 / 惯用白 12% |
| --border-subtle | #e9ecf2 | #ffffff0f | bluish-150 |
| --text | #0f1115 | #f9fafb | label-primary = bluish-1000 / 50 |
| --text-strong | #0f1115 | #ffffff | label-primary |
| --text-muted | #61666b | #cfd3d6 | label-secondary = bluish-700 / 300 |
| --text-dim | #adb2b8 | #81858c | label-tertiary = bluish-400 / 600 |
| --accent | #ff8f40（Pi 原橙，保留） | #ffb454（Pi 原橙，保留） | ⚠ 用户要求不换 DSH 蓝 |
| --accent-hover | #f27d2f（原值） | #ffd173（原值） | 同上 |
| --code-bg | #f9fafb | #1b1b1c | bluish-50 / 900 |
| --code-header-bg | #ebeef2 | #232324 | bluish-100 / 875 |
| --success | #22c55e | #4ed17e | green-500 / 400 |
| --danger | #ec1313 | #f25a5a | error 系 |
| --warning | #f59e0b | #f7ad31 | amber-500 / 400 |
| --info | #3b82f6 | #60a5fa | blue-500 / 400 |

（user/assistant/tool 气泡与 focus-ring 同理映射，详见 apply_patches.py `patch_css_dsh`；
但 accent 家族与 user 气泡渐变为 Pi 原橙官方值——用户 2026-09-19 明确要求保留）

**P8 升级机制**：已部署旧版块（如 v1 蓝色强调色）时，`patch_css_dsh` 会就地重写
DSH_MARK 之后的尾部为当前版；旧尾部之后追加的 P8b 块会被丢弃并由
`patch_css_dsh2` 自动重新追加（自愈闭环）。

## 5. 验证流程（每次适配后必做）

```bash
# 1) 在原始备份副本上端到端测试（模拟更新后的全新产物；⚠ 需同时拷 JS 和 CSS）
rm -rf /tmp/pi-test && mkdir -p /tmp/pi-test/.next/static/chunks
cp backup/0wz_4dmun1la1.js.orig /tmp/pi-test/.next/static/chunks/app-chunk.js
cp backup/0_d0l-y8ld00j.css.orig /tmp/pi-test/.next/static/chunks/theme.css
PI_STANDALONE=/tmp/pi-test python3 apply_patches.py        # 应 exit 0（含 [P6] CSS 写入）
PI_STANDALONE=/tmp/pi-test python3 apply_patches.py        # 第二次应打印"已是补丁状态，跳过"

# 2) 语法校验（本机无 node，用 JavaScriptCore）
cp /tmp/pi-test/.next/static/chunks/app-chunk.js /tmp/check.mjs
osascript -l JavaScript -e 'ObjC.import("Foundation");
  new Function($.NSString.stringWithContentsOfFileEncodingError("/tmp/check.mjs",4,null).js);"OK"'
# → 输出 OK（报错即语法有问题，重点查引号转义）

# 3) 标记检查：__piSM / __piBT / __piIsRun / var(--text) 24% / "text"=== / width:"17" 等关键子串均在
# 4) 重启应用目视验证六组效果（见 README 表格）
```

## 6. 重新适配指南（锚点失配时）

1. `python3 apply_patches.py` 报 `[P3] xxx 未找到` 之类 → 打开新 chunk，围绕该锚点找新特征：
   先 `grep -c '稳定字符串'` 确认特征串还在；若在但结构变了，微调对应正则（都在 apply_patches.py 顶部可读的 pat_* 变量里）。
2. 特征串本身没了（源码重构）→ 打开 `standalone/components/` 下对应 .tsx 源码读新实现，
   按第 2–4 节的语义重新设计锚点与注入；保持"标记 `__piSM` + 幂等 + 全成功才写盘"三原则。
3. 更新本文件与 README 的"适配版本"，提交 git。
4. 大版本重构若官方改了组件结构（如换掉 SessionSidebar），评估是否放弃该组补丁。

## 7. 源码镜像（早期手工修改，仅参考）

`standalone/components/` 下 `MessageView.tsx`、`MessageList.tsx`、`ChatInput.tsx`、
`SessionSidebar.tsx`、`session-sidebar/SessionTree.tsx`、`session-sidebar/helpers.ts`
曾被同步修改以与编译补丁对应（不影响运行）。原始版备份在本项目 `backup/*.orig`。
新版本适配**不需要**改源码。

## 8. Windows 分发版（windows-build/）

同一套 `apply_patches.py` 直接打在 Windows 官方产物上（跨平台成立的依据）：
- Windows 与 Mac 官方包是**同一次构建**：关键 chunk `0wz_4dmun1la1.js` md5 完全一致；
  仅 CSS 文件名不同（Mac `0_d0l-y8ld00j.css` / Win `1o8y9tk-h0e51.css`，内容差 1 字节），
  `find_css()` 按内容特征定位不受影响。
- 流水线：官方 Setup.exe --7zz 解包--> app-64.7z --> app 目录 --> `PI_STANDALONE=… python3 apply_patches.py`
  --> 删 `resources/app-update.yml` 禁自动更新（主进程缺失配置走 logError 静默，已核实 app.asar）
  --> `cat 7z.sfx + sfx-config + payload.7z` 封自解压安装器（免管理员，per-user 安装）。
- 工具链无 brew/sudo/docker：`~/tools/7zip/7zz`（ip7z releases）+ `7z.sfx`（官方 7-Zip 安装器解包取得）。
- 坑：①sfx 配置必须 UTF-8 **无 BOM**，而 PowerShell 脚本必须 UTF-8 **带 BOM**（PS 5.1 中文）；
  ②ip7z 25.01+ 的 extra 包已不含 sfx 模块，从官方安装器 payload 里拿；
  ③github 下载需走本机代理 http://127.0.0.1:7890。
- 详见 `windows-build/README.md`（含隐私扫描结论与重建步骤）。
