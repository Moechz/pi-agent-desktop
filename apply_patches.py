#!/usr/bin/env python3
"""
Pi Agent Desktop UI 补丁自动重打器（语义锚点版）
更新应用后编译产物的文件名/压缩变量名会变，本脚本用稳定结构特征
（CSS 类名、prop 键名、内联样式串）动态定位，跨版本重打 4 组补丁：
  P1 会话完成后只留最后一条文本结果（消息级 + 块级 + 无文本整条隐藏）
  P2 输入框边框加强
  P3 侧边栏项目平铺 + 会话运行状态点（树构建器存档/轮询器/分组渲染/空态/圆点）
     + 组头 ▼/▲ 折叠箭头（点击按目录展开/收起会话，状态存于组件 useState）
  P5 侧边栏菜单字体对齐 DSH Desktop（系统字体栈 PingFang SC 等；菜单 13px/次级 12px）
  P6 菜单/弹窗不透明（CSS：--material-popover→var(--bg) + --bg-elevated/--bg-panel 去 alpha；
     JS：flyout/危险弹卡内联背景→var(--bg)；独立于 JS 幂等）
  P7 输入框下方图标统一 18px（工具行：附件/模型/模式/预设/更多控件均 18，与左下角附件同尺寸；
     思考级别弹窗图标 11→14；发送按钮：主发送 + 排队追问圆钮内箭头 15→18）
  P8 全应用 DSH Desktop 风格（字体栈 + 明暗色板 + 正文行高/标题字号；纯 CSS 追加）
  P15 会话条目紧凑化：删 meta 行（时间+消息数），标题行最右紧凑相对时间 now/Nm/Nh/Nd，
     圆点只留运行中绿点（空闲不渲染），行高 52→40px；组头图标改文件夹（收起=关闭/accent，
     展开=打开/muted，lucide folder/folder-open）
用法：
  python3 apply_patches.py            # 打补丁（幂等，已打过则跳过）
  PI_STANDALONE=/path python3 ...     # 指定 standalone 目录（测试用）
退出码：0=成功或已是最新；1=锚点失配（需人工重新适配）；2=其他错误
"""
import glob
import os
import re
import sys

STANDALONE = os.environ.get(
    "PI_STANDALONE",
    "/Applications/Pi Agent Desktop.app/Contents/Resources/standalone",
)
MARKER = "__piSM"  # P3 轮询器标记，存在即认为已打补丁
DSH_MARK = "/*__piDSH*/"  # P8 全局 DSH 主题追加标记
PI_ROW_H = 40  # P15 会话行高（px）。⚠ h-[Npx] 是 Tailwind 编译期类——编译 CSS 只含
# 构建时用过的规则（本构建仅 .h-\[52px\]），改 className 字符串造不出新高度类，
# 必须换自定义类 __piRowH 并由 patch_css() 注入规则；调行高只改这个常量。
DSH2_MARK = "/*__piDSH2*/"  # P8b 字号阶梯追加标记
FS_MARK = "/*__piFS*/"  # P8c JS 字号扫掠一次性标记（防 11→12 后被二次升 13）
DSH_FONT = (
    '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",'
    '"Hiragino Sans GB","Microsoft YaHei","Helvetica Neue",Helvetica,Arial,sans-serif'
)
ID = r"[A-Za-z_$][A-Za-z0-9_$]*"


class PatchError(Exception):
    pass


def jsx_expr_end(text, start):
    """切出从 start 开始的整段 JS 表达式（形如 `(0,ns.jsx)("div",{…})`）。
    做括号配对扫描（跳过普通/模板字符串）；回到 0 层后，仅当下一个非空字符是
    `(` `[` `.` 时继续（链式调用/成员访问），否则视为表达式结束。
    ⚠ 不能简单地“0 层即结束”——`(0,ns.jsxs)` 这个前缀括号会先闭合。"""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n and text[i] != q:
                if text[i] == "\\":
                    i += 1
                i += 1
        elif c == "`":
            i += 1
            while i < n and text[i] != "`":
                if text[i] == "\\":
                    i += 1
                i += 1
        elif c in "([{":
            stack.append(c)
        elif c in ")]}":
            if not stack or stack[-1] != pairs[c]:
                raise PatchError(f"jsx_expr_end 括号不匹配 @{i}")
            stack.pop()
            if not stack:
                j = i + 1
                while j < n and text[j] in " \t\n":
                    j += 1
                if j < n and text[j] in "([.":
                    i = j - 1  # 同一表达式的延续（下轮从 ( / [ 开始）
                else:
                    return i + 1
        i += 1
    raise PatchError("jsx_expr_end 扫描到末尾仍未闭合")


def find_chunk():
    """定位包含侧边栏+消息视图的编译 chunk（用稳定字符串特征）"""
    for f in sorted(glob.glob(os.path.join(STANDALONE, ".next/static/chunks/*.js"))):
        try:
            data = open(f, encoding="utf-8").read()
        except OSError:
            continue
        if (
            "t-acc-panel-inner" in data
            and "sidebar.noSessions" in data
            and '"/api/sessions"' in data
            and "composer-shell" in data
        ):
            return f, data
    raise PatchError("找不到目标 chunk（应用结构可能大改）")


def find_css():
    """定位主题 CSS（含 --material-popover 变量的那个，文件名随内容哈希变）"""
    for f in sorted(glob.glob(os.path.join(STANDALONE, ".next/static/chunks/*.css"))):
        try:
            data = open(f, encoding="utf-8").read()
        except OSError:
            continue
        if "--material-popover:" in data:
            return f, data
    raise PatchError("找不到主题 CSS（应用结构可能大改）")


def patch_css():
    """P6（v3）：菜单/弹窗全面不透明。
    ① --material-popover 两处归一为 var(--bg)（不透明+无色偏+明暗自适应，
      覆盖 material-popover 系菜单/下拉/对话框/toast）。
    ② --bg-elevated / --bg-panel 去 alpha（保留自身色调仅变实）：
      flyout 二级弹卡、模态框表头、工具面板、权限确认按钮/输入框等
      65% 半透明表面全部变实（原设计靠 backdrop blur 混合底下内容）。
    两组独立幂等（部分打过的中间态也能收敛）。官方不透明覆盖规则只在
    prefers-reduced-transparency/@media 里，普通设置不生效，故需打补丁。"""
    css, data = find_css()
    # P8 追加块也会重定义 --bg-elevated/--bg-panel，P6 只在前段（DSH 标记之前）检测/替换
    if DSH_MARK in data:
        head, _tail = data.split(DSH_MARK, 1)
        tail = DSH_MARK + _tail
    else:
        head, tail = data, ""
    changed = False
    # ① popover 族 → var(--bg)（任意历史色值部归一，兼容原版/v1/v2 三态）
    if head.count("--material-popover:var(--bg)") != 2:
        pat_hex = re.compile(r"--material-popover:#[0-9a-fA-F]+")
        if len(pat_hex.findall(head)) != 2:
            raise PatchError("[P6] --material-popover 色值锚点异常")
        head = pat_hex.sub("--material-popover:var(--bg)", head)
        changed = True
    # ② elevated/panel 去 alpha：8位hex → 6位；已是 6位×2 则跳过
    for var in ("--bg-elevated", "--bg-panel"):
        pat8 = re.compile(re.escape(var) + r":(#[0-9a-fA-F]{6})[0-9a-fA-F]{2}")
        n8 = len(pat8.findall(head))
        if n8 == 2:
            head = pat8.sub(lambda mm, v=var: v + ":" + mm.group(1), head)
            changed = True
        else:
            n6 = len(re.findall(re.escape(var) + r":#[0-9a-fA-F]{6}(?![0-9a-fA-F])", head))
            if n6 != 2:
                raise PatchError(f"[P6] {var} 锚点异常（8位×{n8} / 6位×{n6}）")
    # ③ P15 行高规则注入（幂等：无则文末追加 .__piRowH{height:Npx}，有则校正高度）
    full = head + tail
    rule_re = re.compile(r"\.__piRowH\{height:\d+px\}")
    want = f".__piRowH{{height:{PI_ROW_H}px}}"
    if rule_re.search(full):
        new_full = rule_re.sub(want, full)
    else:
        new_full = full + want
    if new_full != full:
        changed = True
    if changed:
        tmp = css + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new_full)
        os.replace(tmp, css)
        print(f"✅ [P6] 弹窗/面板不透明已写入 {css}")
    else:
        print("ℹ️ [P6] CSS 已是补丁状态")
    return 0


def patch_css_dsh():
    """P8：全应用 DSH Desktop 风格（字体栈 + 色彩体系 + 正文排版）。
    参考值解包自 DSH Desktop.app（@deepseek-ai/dsh-web-frontend + dsh-client-ui-theme）：
      · 字体栈 -apple-system/BlinkMacSystemFont/Segoe UI/PingFang SC/...（body 同款）
      · 色板 = DSH neutral-bluish 灰阶，明暗两套 alias 映射到 Pi 变量
        （light: bg #fff / label #0f1115 / secondary #61666b；
         dark: bg #151517 / label #f9fafb / secondary #cfd3d6）
      · ⚠ 强调色家族保留 Pi 原橙不变（用户明确要求）：accent/hover/contrast、
        user 气泡渐变/边框、focus-ring 均为官方原值，仅背景/文字/边框/状态色走 DSH。
      · 正文 14px 行高 24px（Pi 本就 14px，调 line-height 1.68→1.71）；
        markdown 标题对齐 DSH 绝对值 h1 21/30 h2 19/28 h3 18/26 h4 14(w600)
      · 抗锯齿 -webkit-font-smoothing:antialiased
    实现全部为文件末尾追加（非 @layer 无层级规则天然压过 @layer theme 的
    --font-sans；同特异性后写胜过原 :root/html.dark），零锚点依赖，官方更新极鲁棒。
    JS 侧无改动；幂等标记 /*__piDSH*/。"""
    css, data = find_css()
    block = (
        DSH_MARK
        + ":root{"
        # ---- 浅色 = DSH light alias（static neutral-bluish / deepseek 色阶）----
        + "--bg:#ffffff;--bg-panel:#f5f6f7;--bg-elevated:#ffffff;"
        + "--bg-hover:#2631480f;--bg-selected:#2631481a;"
        + "--border:#e1e5ee;--border-subtle:#e9ecf2;"
        + "--text:#0f1115;--text-strong:#0f1115;--text-muted:#61666b;--text-dim:#adb2b8;"
        + "--accent:#ff8f40;--accent-hover:#f27d2f;--accent-contrast:#fff;"
        + "--user-bg:linear-gradient(135deg,#fff3e3 0%,#ffe9cc 100%);--user-border:#ffd6a880;"
        + "--assistant-bg:#f9fafbcc;--tool-bg:#f5f6f7cc;--bg-subtle:#2631480d;"
        + "--code-bg:#f9fafb;--code-header-bg:#ebeef2;"
        + "--success:#22c55e;--success-bg:#22c55e1c;--success-border:#22c55e52;"
        + "--danger:#ec1313;--danger-bg:#ec13131a;--danger-border:#ec131352;"
        + "--warning:#f59e0b;--warning-bg:#f59e0b1f;--warning-border:#f59e0b57;"
        + "--info:#3b82f6;--info-bg:#3b82f61c;--info-border:#3b82f652;"
        + "--focus-ring:#ff8f405c;"
        + "--font-sans:" + DSH_FONT + ";"
        + "}"
        # ---- 深色 = DSH dark alias（挂 html.dark 与 .dark 双选择器兜底）----
        + "html.dark,.dark{"
        + "--bg:#151517;--bg-panel:#1b1b1c;--bg-elevated:#2c2c2e;"
        + "--bg-hover:#ffffff14;--bg-selected:#ffffff24;"
        + "--border:#ffffff1a;--border-subtle:#ffffff0f;"
        + "--text:#f9fafb;--text-strong:#ffffff;--text-muted:#cfd3d6;--text-dim:#81858c;"
        + "--accent:#ffb454;--accent-hover:#ffd173;--accent-contrast:#1b1307;"
        + "--user-bg:linear-gradient(135deg,#ffb45426 0%,#ffb4540d 100%);--user-border:#ffb45433;"
        + "--assistant-bg:#232324cc;--tool-bg:#1b1b1ccc;--bg-subtle:#ffffff0d;"
        + "--code-bg:#1b1b1c;--code-header-bg:#232324;"
        + "--success:#4ed17e;--success-bg:#4ed17e14;--success-border:#4ed17e42;"
        + "--danger:#f25a5a;--danger-bg:#f25a5a1a;--danger-border:#f25a5a47;"
        + "--warning:#f7ad31;--warning-bg:#f7ad311a;--warning-border:#f7ad314d;"
        + "--info:#60a5fa;--info-bg:#60a5fa14;--info-border:#60a5fa47;"
        + "--focus-ring:#ffb4546b;"
        + "}"
        # ---- 字体栈 + 抗锯齿（压过原 html,body 的 var(--font-inter) 规则）----
        + "html,body{font-family:" + DSH_FONT + "}"
        + "body{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}"
        # ---- 正文排版对齐 DSH（14px/24px；标题绝对字号）----
        + ".markdown-body{line-height:1.71}"
        + ".markdown-body h1{font-size:21px;line-height:30px}"
        + ".markdown-body h2{font-size:19px;line-height:28px}"
        + ".markdown-body h3{font-size:18px;line-height:26px}"
        + ".markdown-body h4{font-size:14px;font-weight:600}"
    )
    rules = block[len(DSH_MARK) :]
    if DSH_MARK in data:
        # 已有旧版块（如 v1 蓝色强调色）→ 就地升级为当前版；已是当前版则跳过
        head, old_tail = data.split(DSH_MARK, 1)
        if old_tail == rules or old_tail.startswith(rules):
            # 尾部可能还追加过 P8b 等后续块（startswith 容忍），避免每小时看护误重写
            print("ℹ️ [P8] DSH 主题已是补丁状态")
            return 0
        tmp = css + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(head + block)
        os.replace(tmp, css)
        print(f"✅ [P8] DSH 主题块已升级（就地重写尾部）→ {css}")
        return 0
    tmp = css + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data + block)
    os.replace(tmp, css)
    print(f"✅ [P8] DSH 主题已追加到 {css}")
    return 0


def patch_css_dsh2():
    """P8b：字号阶梯对齐 DSH（修复设置菜单/弹窗观感不变问题）。
    根因：Pi 全局无 layer 规则 `button,input,textarea,select{font:inherit}`（紧跟
    html,body 之后）压过 @layer utilities 的 text-[Npx]，导致所有表单控件字号
    恒等于 body 14px（Pi 原生行为，非 P8 引入）；而设置弹窗正文多为 div/span 的
    text-[12px]/text-[11px]（12/11px 原样渲染），未达 DSH 次级文字节奏。
    追加无 layer 规则（后写胜 + 无层压层）：
      · button 13px（DSH 菜单项 xs-13/20；input/textarea/select 仍 inherit=14 对齐 DSH 输入 14）
      · .text-[12px] → 13px（DSH 次级）
      · .text-[11px] → 12px（DSH 说明文字）
    幂等标记 /*__piDSH2*/，与 P8 块独立（已部署过 P8 的文件也能补加）。"""
    css, data = find_css()
    if DSH2_MARK in data:
        print("ℹ️ [P8b] 字号阶梯已是补丁状态")
        return 0
    block = (
        DSH2_MARK
        + "button{font-size:13px}"
        + ".text-\\[12px\\]{font-size:13px}"
        + ".text-\\[11px\\]{font-size:12px}"
    )
    tmp = css + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data + block)
    os.replace(tmp, css)
    print(f"✅ [P8b] 字号阶梯已追加到 {css}")
    return 0


def patch_js_dsh_sizes():
    """P8c：JS inline 字号阶梯对齐（fontSize:12→13、11→12；≤10 的徽标不动）。
    与 P8b 的 CSS 类选择器阶梯保持一致，覆盖消息 meta/时间戳/提示文字等 inline 样式。
    ⚠ 幂等必须用一次性标记：扫掠后文件里仍存在 12（由原 11 升来），
    若按"0 命中即已打"判断会把它们再升一级（11→12→13 连升）。
    标记 /*__piFS*/ 追加在 chunk 末尾（独立注释，语法安全）。
    ⚠ 必须在 P1-P7 之后执行：P5 锚点引用原始 fontSize 值（11/12），先扫会破坏锚点。"""
    chunk, src = find_chunk()
    if FS_MARK in src:
        print("ℹ️ [P8c] JS 字号阶梯已是补丁状态")
        return 0
    n12 = src.count("fontSize:12,") + src.count("fontSize:12}")
    n11 = src.count("fontSize:11,") + src.count("fontSize:11}")
    if n12 == 0 and n11 == 0:
        print("ℹ️ [P8c] 无可扫掠字号（可能官方已改）")
        return 0
    # 顺序关键：先 12→13，后 11→12（同一次调用内不会再回头升 12）
    src = src.replace("fontSize:12,", "fontSize:13,").replace("fontSize:12}", "fontSize:13}")
    src = src.replace("fontSize:11,", "fontSize:12,").replace("fontSize:11}", "fontSize:12}")
    src = src + "\n" + FS_MARK + "\n"
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P8c] JS 字号扫掠已写入 {chunk}（12→13：{n12} 处，11→12：{n11} 处）")
    return 0


def patch_dot_solid():
    """P3-glow：运行状态圆点去光晕 → 实体圆点（用户 2026-09-19 要求）。
    旧版 P3 注入了 boxShadow 光晕（0 0 9px 2px 绿晕）+ box-shadow 过渡；
    本函数把已部署文件里的条件 boxShadow 归为恒 none 并简化 transition。
    独立于 JS MARKER 幂等：无光晕串即跳过（新版 P3 注入直接无光晕，不命中）。
    ⚠ 必须在 P1-P7 之后/之外执行（针对已注入产物做迁移，不参与锚点链）。"""
    chunk, src = find_chunk()
    if "0 0 9px 2px" not in src:
        print("ℹ️ [P3-glow] 已是无光晕状态")
        return 0
    pat = re.compile(
        r'boxShadow:window\.__piIsRun&&window\.__piIsRun\(' + ID + r'\.id\)'
        r'\?"0 0 9px 2px rgba\(34,224,107,\.75\)":"none"'
    )
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        raise PatchError(f"[P3-glow] 光晕锚点命中 {len(ms)} 次（期望 1）")
    src = pat.sub('boxShadow:"none"', src)
    src = src.replace(
        '"background .3s,opacity .3s,box-shadow .3s"', '"background .3s,opacity .3s"'
    )
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P3-glow] 圆点光晕已移除 → {chunk}")
    return 0


def patch_model_save_filter():
    """P11：模型配置保存前过滤空 id 模型（防 models.json 整体失效）。
    背景（2026-09-19 用户反馈）：添加模型供应商后原供应商从菜单消失。
    根因链：ModelsConfig.addModel 会 append {id:""} 空白行 → handleSave 把 config
    原样 PUT 到 /api/models-config → ModelConfig.load 用 TypeBox 校验（id minLength:1）
    失败 → 整个 models.json 被丢弃 → 所有自定义供应商（如 zhipu）从运行时消失，
    只剩内置供应商（auth.json 有 key 的 deepseek）。
    本补丁：handleSave 里 JSON.stringify(config) 前包一层 IIFE，过滤掉
    providers[*].models 中 id 为空的条目（其余字段原样保留）。
    锚点：body:JSON.stringify(VAR)}),t=await e.json()（VAR 构建期变量名）。
    注意：g1 吞了 stringify 开括号后，VAR 后还有 stringify 的闭合括号 )，
    故第三组须为 (\)\}\) 而非 \}\)（少一层就永不命中）。
    独立于 MARKER 幂等：锚点自消失，用注入标记 m?.id?.trim() 判已打。"""
    chunk, src = find_chunk()
    pat = re.compile(
        r"(body:JSON\.stringify\()([A-Za-z_$][A-Za-z0-9_$]*)(\)\}\),t=await e\.json\(\))"
    )
    ms = list(pat.finditer(src))
    if not ms:
        if "m?.id?.trim()" in src:
            print("ℹ️ [P11] 模型保存过滤已是补丁状态")
            return 0
        raise PatchError("[P11] 模型保存过滤锚点未命中")
    if len(ms) != 1:
        raise PatchError(f"[P11] 锚点命中 {len(ms)} 次")
    g = ms[0]
    v = g.group(2)
    ii = (
        "(()=>{let _z={..." + v + ",providers:Object.fromEntries(Object.entries(" + v
        + ".providers??{}).map(([k,x])=>[k,{...x,models:(x.models??[]).filter(m=>m?.id?.trim())}]))};return _z})()"
    )
    repl = "body:JSON.stringify(" + ii + g.group(3)
    src = src[: g.start()] + repl + src[g.end():]
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P11] 模型保存过滤已写入 {chunk}")
    return 0


def patch_deepseek_catalog():
    """P14：DeepSeek 模型目录只留 deepseek-flash（V4.1）。
    背景（2026-09-19）：官方 API /models 只有 deepseek-flash（V4.1）与 deepseek-v4-pro，
    v4-flash 已下线；用户要求菜单只留 V4.1 Flash。models.json 是 upsert 语义
    （只能追加/覆盖，不能删内置模型），故直接改目录文件。
    ⚠ 目录共有 4 处副本（首次部署只改了外层 node_modules 那份而未生效）：
      A. node_modules/@earendil-works/*/dist/bundle/chunks/*.js 中的 deepseek_default
      B. .next/node_modules/@earendil-works/*<hash>/dist/bundle/chunks/*.js（服务端真身，
         Next standalone 把 node_modules 复制进 .next，包名带哈希后缀）
      C. node_modules/@earendil-works/pi-ai/dist/providers/data/deepseek.json（数据源）
      D. .next/node_modules/@earendil-works/pi-ai-*<hash>/dist/providers/data/deepseek.json
    JS：删 v4-pro 条目、v4-flash 改名（node --check 校验，含动态 import 勿用 JSC 法）。
    JSON：重写为仅 deepseek-flash 条目。
    服务端 require 缓存常驻：需重启应用生效。幂等：各文件内无 v4-flash 即跳过。"""
    import json as _json

    def roots():
        for sub in ("node_modules", os.path.join(".next", "node_modules")):
            yield os.path.join(STANDALONE, sub)

    # --- JS bundle chunks（A+B）---
    js_done = 0
    for root in roots():
        for f in sorted(glob.glob(os.path.join(root, "@earendil-works/*/dist/bundle/chunks/*.js"))):
            try:
                src = open(f, encoding="utf-8").read()
            except OSError:
                continue
            a = src.find("var deepseek_default=")
            if a < 0:
                continue
            b = src.find(";", a)
            seg = src[a : b + 1]
            if "deepseek-v4-flash" not in seg and "deepseek-flash" in seg:
                continue
            idx = seg.find(',"deepseek-v4-pro":')
            if idx < 0:
                raise PatchError(f"[P14] {os.path.basename(f)} 目录结构异常")
            new_seg = seg[:idx] + "}};"
            new_seg = new_seg.replace('"deepseek-v4-flash"', '"deepseek-flash"').replace(
                "DeepSeek V4 Flash", "DeepSeek V4.1 Flash"
            )
            src = src[:a] + new_seg + src[b + 1 :]
            tmp = f + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(src)
            os.replace(tmp, f)
            js_done += 1
            print(f"✅ [P14] JS 目录已改（仅 V4.1 Flash）: {f.split('standalone/')[-1][:90]}")
    # --- JSON 数据文件（C+D）---
    json_done = 0
    for root in roots():
        for f in sorted(glob.glob(os.path.join(root, "@earendil-works/pi-ai*/dist/providers/data/deepseek.json"))):
            try:
                data = _json.load(open(f, encoding="utf-8"))
            except OSError:
                continue
            changed = False
            for api, models in data.items():
                if not isinstance(models, dict) or "deepseek-v4-flash" not in models:
                    continue
                flash = dict(models["deepseek-v4-flash"])
                flash["id"] = "deepseek-flash"
                flash["name"] = "DeepSeek V4.1 Flash"
                data[api] = {"deepseek-flash": flash}
                changed = True
            if changed:
                with open(f, "w", encoding="utf-8") as fh:
                    _json.dump(data, fh, ensure_ascii=False, indent=0, separators=(",", ":"))
                json_done += 1
                print(f"✅ [P14] JSON 目录已改（仅 V4.1 Flash）: {f.split('standalone/')[-1][:90]}")
    if js_done == 0 and json_done == 0:
        print("ℹ️ [P14] deepseek 目录已是仅 V4.1 Flash（或测试环境无目录文件）")
    return 0


def patch_error_banner():
    """P13：模型请求失败时显示红色错误条（治「输入没反应」的可见性）。
    背景（2026-09-19 实锤）：模型调用失败（如 deepseek 402 余额不足、zhipu 500）
    会写入带 errorMessage 的空 assistant 消息；而 P1「只留结果」规则把无文本的
    完成消息全部隐藏 → 错误被吞，用户看到的是"毫无反应"。
    修复：P1 隐藏规则命中时，若 message.errorMessage 存在则渲染错误条而非 null。
    锚点：P1 编译产物规则 `(!t&&!(MSG.content??[]).some(b=>"text"===b.type)?null:`
    （注意 `??[])` 后有闭合括号再 `.some`——本补丁第四次栽在括号上）。
    样式用内联 style + CSS 变量（--danger/-bg/-border 已存在），不依赖 Tailwind JIT。
    幂等：chunk 含「模型请求失败」即跳过。"""
    chunk, src = find_chunk()
    if "模型请求失败" in src:
        print("ℹ️ [P13] 错误条已存在")
        return 0
    pat = re.compile(
        r'\(!([A-Za-z_$][A-Za-z0-9_$]*)&&!\(([A-Za-z_$][A-Za-z0-9_$]*)\.content\?\?\[\]\)\.some\('
        r'[A-Za-z_$][A-Za-z0-9_$]*=>"text"===[A-Za-z_$][A-Za-z0-9_$]*\.type\)\?null:'
    )
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        raise PatchError(f"[P13] P1 规则锚点命中 {len(ms)} 次")
    m = ms[0]
    msg = m.group(2)
    banner = (
        f'?({msg}.errorMessage?(0,n.jsx)("div",{{style:{{margin:"2px 0 18px",maxWidth:680,'
        f'borderRadius:"var(--radius-panel)",border:"1px solid var(--danger-border)",'
        f'background:"var(--danger-bg)",color:"var(--danger)",fontSize:12,padding:"6px 10px",'
        f'whiteSpace:"pre-wrap",wordBreak:"break-word"}},children:["⚠ 模型请求失败：",{msg}.errorMessage]}}):null):'
    )
    start = m.end() - len("?null:")
    src = src[:start] + banner + src[start + len("?null:"):]
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P13] 失败消息错误条已写入 {chunk}")
    return 0


def patch_model_name_button():
    """P12：输入框下方模型按钮显示当前模型名。
    原按钮（ModelSelector 触发器）只有 32px 芯片图标，模型名只在 title 提示里。
    改为：图标 + 模型名文字（fontSize:12，maxWidth:180 溢出省略），按钮由固定宽
    32 改为自适应 padding。锚点：芯片 svg 顶针脚 x1:"9",y1:"1" + 尾针脚
    x2:"4",y2:"14"})]})})（均全局唯一）；currentName 变量从窗口内 title:VAR 提取。
    幂等：窗口内已含 maxWidth:180 则跳过。"""
    chunk, src = find_chunk()
    if 'whiteSpace:"nowrap",maxWidth:180,overflow:"hidden",textOverflow:"ellipsis"' in src:
        print("ℹ️ [P12] 模型名已显示")
        return 0
    tail = 'x2:"4",y2:"14"})]})})'
    if src.count(tail) != 1:
        raise PatchError("[P12] svg 尾锚点命中异常")
    # 芯片图形全文件复用 3 处，须用「尾锚+紧邻 dropdown」唯一组合定位本组件
    t = src.find(tail)
    if "visualViewport" not in src[t + len(tail):t + len(tail) + 300]:
        raise PatchError("[P12] 尾锚后非 dropdown（定位错误）")
    w0, w1 = max(0, t - 3000), t + len(tail)
    win = src[w0:w1]
    m = re.search(r"title:([A-Za-z_$][A-Za-z0-9_$]*),", win)
    if not m:
        raise PatchError("[P12] currentName 变量未定位")
    var = m.group(1)
    span = f'(0,n.jsx)("span",{{style:{{fontSize:12,whiteSpace:"nowrap",maxWidth:180,overflow:"hidden",textOverflow:"ellipsis"}},children:{var}}})'
    t2 = win.find(tail)
    # 窗口可能跨组件；须取尾锚之前最近的那个 svg（本按钮的）
    a = win.rfind('children:(0,n.jsxs)("svg",', 0, t2)
    if a < 0:
        raise PatchError("[P12] children svg 锚点未命中")
    win = win[:a + 9] + "[" + win[a + 9:]
    t2 = win.find(tail)
    win = win[: t2 + len(tail) - 2] + "," + span + "]" + win[t2 + len(tail) - 2:]
    m2 = re.search(r"width:32,padding:0,", win)
    if m2:
        win = win.replace("width:32,padding:0,", 'gap:6,padding:"0 8px 0 9px",', 1)
    else:
        print("⚠️ [P12] 按钮 width:32 未命中（可能已自适应），跳过宽度调整")
    src = src[:w0] + win + src[w1:]
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P12] 模型按钮已显示模型名（变量 {var}）")
    return 0


def patch_orb_expand():
    """P10b：状态球思考面板默认展开（真正的实时思考显示位置）。
    关键发现（2026-09-19）：ChatWindow 在把流式消息传给消息列表前，用
    splitActiveThinking() 把 thinking 块剥离——流式消息根本不渲染思考块！
    实时思考的唯一显示位置是 AgentThinkingOrb 的思考面板（expanded 默认 false
    收起，需手动点状态球）。P10（c3 手风琴默认展开）只影响消息内思考块渲染路径
    （完成态被 P1 隐藏、流式态被剥离），对直播路径无效——本补丁才是正解。
    锚点：orb 组件（签名 phase:X,thinking:Y=""）内、紧邻 useId() 的 useState，
    其前一个是 entering 的 useState(!1)。改为 !0：一有思考内容即展开直播
    （组件已有自动滚动到底逻辑）；点击仍可收起；空 thinking 由 hasThinking 门控。
    ⚠ 正则坑（连犯三次）：useState)(!1) 的调用括号——组须含 `useState\)(`。
    独立于 MARKER 幂等：以 orb 区域内是否存在 useState)(!0) 判定。"""
    chunk, src = find_chunk()

    def orb_state(code):
        """返回 orb 区域内 expanded 的 useState 值（"!1"/"!0"）或 None"""
        i = code.find('phase:')
        while i != -1:
            m = re.match(r"phase:[A-Za-z_$][A-Za-z0-9_$]*,thinking:[A-Za-z_$][A-Za-z0-9_$]*=\"\"\"?", code[i:i+80])
            j = code.find("useId", i)
            if m and j != -1:
                region = code[i:j+10]
                mm = re.search(r"useState\)\((\!\d)\),[A-Za-z_$][A-Za-z0-9_$]*=\(0,[A-Za-z_$][A-Za-z0-9_$]*\.useId", region)
                if mm:
                    return mm.group(1)
            i = code.find("phase:", i + 1)
        return None

    state = orb_state(src)
    if state == "!0":
        print("ℹ️ [P10b] 状态球思考面板已默认展开")
        return 0
    if state != "!1":
        raise PatchError(f"[P10b] orb 区域锚点异常（state={state}）")
    i = src.find('phase:')
    while i != -1:
        j = src.find("useId", i)
        region = src[i:j+10]
        if re.match(r"phase:[A-Za-z_$][A-Za-z0-9_$]*,thinking:[A-Za-z_$][A-Za-z0-9_$]*=\"\"", src[i:i+80]) and j != -1:
            mm = re.search(r"(useState\)\()(\!1)(\),)(?=[A-Za-z_$][A-Za-z0-9_$]*=\(0,[A-Za-z_$][A-Za-z0-9_$]*\.useId)", region)
            if mm:
                start = i + mm.start(2)
                src = src[:start] + "!0" + src[start + 2:]
                tmp = chunk + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(src)
                os.replace(tmp, chunk)
                print(f"✅ [P10b] 状态球思考面板默认展开已写入 {chunk}")
                return 0
        i = src.find("phase:", i + 1)
    raise PatchError("[P10b] orb 内 useState 锚点未命中")


def patch_thinking_live():
    """P10：思考面板默认展开（流式时直接看到推理内容）。
    背景（2026-09-19 用户澄清需求）：思考过程要「显示」——原应用思考折叠面板
    useState(false) 默认收起，每条消息都需手动点开。改为默认展开：
    - 流式中的消息：思考内容实时可见
    - 完成态：思考块被 P1 整体隐藏，不受影响
    锚点：c3 组件（block+duration 签名 + useI18n 后首个 useState(!1)）。
    注意：raw 字符串内正则用单反斜杠（双反斜杠=匹配字面反斜杠，首版即栽在这）。
    独立于 MARKER 幂等：useState(!0) 后闭式锚点自消失。"""
    chunk, src = find_chunk()
    SIG = (r"function [A-Za-z_$][A-Za-z0-9_$]*"
           r"\(\{block:[A-Za-z_$][A-Za-z0-9_$]*,duration:[A-Za-z_$][A-Za-z0-9_$]*\}\)"
           r"\{let\{t:[A-Za-z_$][A-Za-z0-9_$]*\}=\(0,[A-Za-z_$][A-Za-z0-9_$]*\.useI18n\)\(\),"
           r"\[[A-Za-z_$][A-Za-z0-9_$]*,[A-Za-z_$][A-Za-z0-9_$]*\]=\(0,[A-Za-z_$][A-Za-z0-9_$]*\.useState\)")
    # (0,r.useState)(!1)：SIG 止于 .useState)，其后还有调用括号 (!1)
    pat = re.compile("(" + SIG + r")\((\!1)\),")
    pat_open = re.compile(SIG + r"\(\!0\),")
    ms = list(pat.finditer(src))
    if not ms:
        if pat_open.search(src):
            print("ℹ️ [P10] 思考面板已默认展开")
            return 0
        raise PatchError("[P10] 思考面板锚点未命中")
    if len(ms) != 1:
        raise PatchError(f"[P10] 锚点命中 {len(ms)} 次")
    m = ms[0]
    src = src[: m.start(2)] + "!0" + src[m.end(2):]
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P10] 思考面板默认展开已写入 {chunk}")
    return 0


def patch_p1_v3():
    """P1 v3 迁移：列表级规则去 agentRunning 门控 + cQ 调用去 isStreaming 注入。
    背景（2026-09-19 用户反馈）：v2 用会话级 agentRunning 门控整个历史，
    正在运行的会话里此前已完成的轮次思考边也不隐藏；且 agentRunning
    滞留 true 的会话永远全显。v3 = 轮次级语义：数组内消息一律按完成态
    渲染（收起），实时过程由尾部流式消息独立调用点（isStreaming:!0）承担。
    独立于 JS MARKER 幂等：两处 v2 注入特征均不存在即视为已是 v3。"""
    chunk, src = find_chunk()
    pat1 = re.compile(
        r"!(?P<ag>" + ID + r")&&\"assistant\"===(?P<msg>" + ID + r")\.role"
        r"&&\(function\(\)\{for\(var k2="
    )
    ms1 = list(pat1.finditer(src))
    pat2 = re.compile(
        # 锚定在扫描 IIFE 尾巴后紧跟的 cQ 调用（避免误伤同形状的 c1 官方调用点）
        r"return!1\}\)\(\)\?null:\(0,(?P<n>" + ID + r")\.jsx\)\((?P<cq>" + ID + r"),"
        r"\{message:(?P<msg2>" + ID + r"),isStreaming:(?P<ag2>" + ID + r"),toolResults:"
    )
    ms2 = list(pat2.finditer(src))
    if not ms1 and not ms2:
        print("ℹ️ [P1v3] 已是轮次级语义")
        return 0
    if len(ms1) != 1 or len(ms2) != 1:
        raise PatchError(f"[P1v3] 锚点异常（门控×{len(ms1)} / isStreaming×{len(ms2)}）")
    g1, g2 = ms1[0].groupdict(), ms2[0].groupdict()
    if g1["msg"] != g2["msg2"] or g1["ag"] != g2["ag2"]:
        raise PatchError("[P1v3] 两处锚点变量不一致，需人工确认")
    # ① 去 !AG&& 门控
    src = src[: ms1[0].start()] + f'"assistant"==={g1["msg"]}.role&&(function(){{for(var k2=' + src[ms1[0].end():]
    # ② 去 cQ 调用的 isStreaming 注入（重新定位，①已改偏移）
    ms2b = list(pat2.finditer(src))
    if len(ms2b) != 1:
        raise PatchError("[P1v3] 去门控后 isStreaming 锚点丢失")
    m2 = ms2b[0]
    repl2 = (
        'return!1})()?null:(0,' + m2.group('n') + '.jsx)(' + m2.group('cq') + ',{message:'
        + m2.group('msg2') + ',toolResults:'
    )
    src = src[: m2.start()] + repl2 + src[m2.end():]
    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ [P1v3] 轮次级语义已写入 {chunk}")
    return 0


def sub_once(src, pattern, repl, name, pos=None):
    """正则替换，强制恰好命中一次；pos 给定时只在 >=pos 处找"""
    flags = 0
    if pos is not None:
        rx = re.compile(pattern, flags)
        ms = list(rx.finditer(src, pos))
        if len(ms) != 1:
            raise PatchError(f"[{name}] 锚点命中 {len(ms)} 次（期望 1）")
        m = ms[0]
        return src[: m.start()] + m.expand(repl) + src[m.end() :]
    ms = list(re.finditer(pattern, src, flags))
    if len(ms) != 1:
        raise PatchError(f"[{name}] 锚点命中 {len(ms)} 次（期望 1）")
    m = ms[0]
    return src[: m.start()] + m.expand(repl) + src[m.end():]


def main():
    # P6/P8/P8b 是 CSS 补丁，独立于 JS MARKER 幂等（JS 已打过时也要能补 CSS）
    patch_css()
    patch_css_dsh()
    patch_css_dsh2()
    # P3-glow 迁移也独立于 MARKER（修已部署产物的光晕；全新产物由新版 P3 直接无光晕）
    patch_dot_solid()
    # P1 v3 迁移：轮次级隐藏语义（去 agentRunning 门控）
    patch_p1_v3()
    # P10：思考面板默认展开（流式实时可见；fresh/已部署通吃，幂等）
    patch_thinking_live()
    # P10b：状态球思考面板默认展开（实时思考的真实显示位置，P10 的正解）
    patch_orb_expand()
    # P12：输入框下方模型按钮显示当前模型名
    patch_model_name_button()
    # P11：模型配置保存前过滤空 id 模型（防 models.json 整体失效致供应商消失）
    patch_model_save_filter()
    # P14：deepseek 模型目录仅留 V4.1 Flash（官方已下线 v4-flash；需重启生效）
    patch_deepseek_catalog()
    chunk, src = find_chunk()
    if MARKER in src:
        print("已是补丁状态，跳过")
        patch_js_dsh_sizes()  # P8c 独立幂等，已打 P1-P7 的文件也能补
        # P13 须在 P1-msg（MARKER 流程注入的消息级隐藏规则）之后：
        # 改写其 null 分支为错误条。此处对已部署 chunk 成立。
        patch_error_banner()
        return 0
    orig = src

    # ---------- P2：输入框边框（稳定 CSS 变量名，直接替换） ----------
    p2_old = '"color-mix(in srgb, var(--border) 70%, transparent)"'
    if src.count(p2_old) != 1:
        raise PatchError("[P2] 输入框边框锚点异常")
    src = src.replace(
        p2_old, '"color-mix(in srgb, var(--text) 24%, transparent)"'
    )

    # ---------- P1-块级：完成后只保留最后一个文本块 ----------
    # children:M.map((b,q)=>(0,n.jsx)(C,{block:b,toolResults:a,
    #   streamingDuration:w.get(q)??("thinking"===b.type?T:void 0),
    #   toolCallDurations:A},q))
    pat_block = (
        rf"children:(?P<m>{ID})\.map\(\((?P<b>{ID}),(?P<q>{ID})\)=>"
        rf"\(0,(?P<n>{ID})\.jsx\)\((?P<c2>{ID}),\{{block:(?P=b),"
        rf"toolResults:(?P<a>{ID}),streamingDuration:(?P<w>{ID})\.get\((?P=q)\)"
        rf"\?\?\(\"thinking\"===(?P=b)\.type\?(?P<T>{ID}):void 0\),"
        rf"toolCallDurations:(?P<A>{ID})\}},(?P=q)\)\)"
    )
    m_block = list(re.finditer(pat_block, src))
    if len(m_block) != 1:
        raise PatchError(f"[P1-block] 命中 {len(m_block)} 次")
    # isStreaming 变量名：从同一组件后方的 <msg>.usage&&!<is>&& 页脚特征取
    m_usage = re.search(rf"(?P<mu>{ID})\.usage&&!(?P<is>{ID})&&", src[m_block[0].end():])
    if not m_usage:
        raise PatchError("[P1-block] 找不到 usage&&!isStreaming 页脚锚点")
    g = m_block[0].groupdict()
    IS = m_usage.group("is")
    # ⚠ 防变量遮蔽：IS（本构建里叫 t）可能被 map 回调参数 (e,t) 的下标同名遮蔽，
    # 必须先在 IIFE 外层作用域把 !IS 快照到新变量 _piS，回调内只用 _piS
    repl_block = (
        rf'children:(function(){{var _piS=!{IS};var li=-1;{g["m"]}.forEach(function(bb,i2){{if("text"===bb.type)li=i2}});'
        rf'return {g["m"]}.map(({g["b"]},{g["q"]})=>_piS&&("text"!=={g["b"]}.type||{g["q"]}!==li)?null:'
        rf'(0,{g["n"]}.jsx)({g["c2"]},{{block:{g["b"]},toolResults:{g["a"]},'
        rf'streamingDuration:{g["w"]}.get({g["q"]})??("thinking"==={g["b"]}.type?{g["T"]}:void 0),'
        rf'toolCallDurations:{g["A"]}}},{g["q"]}))}})()'
    )
    src = sub_once(src, pat_block, repl_block, "P1-block")

    # ---------- P1-消息级：无文本整条隐藏（cQ 分发处） ----------
    pat_noq = (
        rf"\"assistant\"===(?P<msg>{ID})\.role\?\(0,(?P<n>{ID})\.jsx\)\((?P<c1>{ID}),"
        rf"\{{message:(?P=msg),isStreaming:(?P<is>{ID}),toolResults:(?P<tr>{ID}),"
        rf"modelNames:(?P<mn>{ID}),entryId:(?P<eid>{ID}),onBranchMessage:(?P<ob>{ID}),"
        rf"showTimestamp:(?P<st>{ID}),prevTimestamp:(?P<pt>{ID})\}}\):"
    )
    m_noq = list(re.finditer(pat_noq, src))
    if len(m_noq) != 1:
        raise PatchError(f"[P1-msg] 命中 {len(m_noq)} 次")
    mm = m_noq[0]
    parts = mm.group(0)
    # inner 形如 (0,n.jsx)(c1,{...}):  → 去掉尾部 ':'，包一层条件后补 ')' 再接 ':'
    inner = parts[len('"assistant"===' + mm.group("msg") + '.role?'):]
    new_noq = (
        '"assistant"===' + mm.group("msg") + '.role?'
        "(!" + mm.group("is") + "&&!(" + mm.group("msg") + ".content??[]).some(b=>\"text\"===b.type)?null:"
        + inner[:-1] + "):"
    )
    src = src[: mm.start()] + new_noq + src[mm.end():]

    # ---------- P4-消息列表：中间叙述整条隐藏 ----------
    # <MSGS>.map((<MSG>,<IDX>)=>{ ... <V>=(0,n.jsx)(cQ,{message:<MSG>, ...
    pat_ml = (
        rf"(?P<msgs>{ID})\.map\(\((?P<msg>{ID}),(?P<idx>{ID})\)=>\{{(?P<mid>.{{0,2000}}?)"
        rf"(?P<v>{ID})=\(0,(?P<n>{ID})\.jsx\)\((?P<cq>{ID}),\{{message:(?P=msg),"
    )
    m_ml = list(re.finditer(pat_ml, src))
    if len(m_ml) != 1:
        raise PatchError(f"[P4] 命中 {len(m_ml)} 次")
    g4 = m_ml[0].groupdict()
    # agentRunning 变量名：从 c7 签名（map 前 600 字内）捕获
    m_ag = re.search(rf"agentRunning:(?P<ag>{ID})",
                     src[max(0, m_ml[0].start() - 600): m_ml[0].start()])
    if not m_ag:
        raise PatchError("[P4] agentRunning 未捕获")
    AG = m_ag.group("ag")
    # 会话格式为 assistant/toolResult 交替存储，"下一条是 assistant"永不成立；
    # 改为向后扫描：到下一条 user 前若还有 assistant → 本条是中间叙述 → 隐藏（跳过 toolResult）。
    # v3（2026-09-19）：去掉 !agentRunning 门控 —— 轮次级语义：完成的轮次立即收起，
    # 不再受会话级 agentRunning 影响（修复：正在运行的会话里历史轮次思考边不隐藏）。
    # 实时过程由尾部流式消息独立渲染（o&&s&&cQ(isStreaming:!0)），不受影响。
    inject = (
        f"{g4['v']}=\"assistant\"==={g4['msg']}.role"
        f"&&(function(){{for(var k2={g4['idx']}+1;k2<{g4['msgs']}.length;k2++){{"
        f"var r2={g4['msgs']}[k2].role;if(\"user\"===r2)return!1;if(\"assistant\"===r2)return!0}}"
        f"return!1}})()?null:"
    )
    seg = m_ml[0].group(0)
    seg = seg.replace(g4["v"] + "=(0,", inject + "(0,", 1)
    # v3：不再给 cQ 补传 isStreaming=agentRunning —— 数组内消息一律按完成态渲染（收起）；
    # 流式中的尾部消息走独立调用点显式传 isStreaming:!0，保持实时可见
    src = src[: m_ml[0].start()] + seg + src[m_ml[0].end():]

    # ---------- P3-1：树构建器存档到 window.__piBT ----------
    pat_bto = (
        rf"(?P<z>{ID})=function\((?P<e>{ID})\)\{{let (?P<t>{ID})=new Map;"
        rf"for\(let (?P<n>{ID}) of (?P=e)\)(?P=t)\.set\((?P=n)\.id,\{{session:(?P=n),children:\[\]\}}\);"
    )
    pat_btc = rf"return (?P<a>{ID})\((?P<r>{ID})\),(?P=r)\}}\((?P<U>{ID})\);"
    src = sub_once(src, pat_bto, r"\g<z>=(window.__piBT=window.__piBT||function(\g<e>){let \g<t>=new Map;"
           r"for(let \g<n> of \g<e>)\g<t>.set(\g<n>.id,{session:\g<n>,children:[]});", "P3-tree-open")
    src = sub_once(src, pat_btc, r"return \g<a>(\g<r>),\g<r>})(\g<U>);", "P3-tree-close")

    # ---------- P3-2：轮询器 + 分组渲染 + 空态（侧边栏组件内） ----------
    # 组件签名（prop 键名来自源码，稳定）
    pat_side = (
        rf"function\s?[\w$]*\(\{{selectedSessionId:(?P<sel>{ID}),onSelectSession:(?P<osel>{ID}),"
        rf"onNewSession:(?P<ons>{ID}),initialSessionId:(?P<ini>{ID}),"
        rf"onInitialRestoreDone:(?P<oid>{ID}),refreshKey:(?P<rk>{ID}),"
        rf"onSessionDeleted:(?P<osd>{ID}),onBranchSession:(?P<obs>{ID}),"
        rf"onCloneSession:(?P<ocl>{ID}),onExportSession:(?P<oex>{ID}),"
        rf"selectedCwd:(?P<scwd>{ID}),onCwdChange:(?P<ocwd>{ID})"
    )
    m_side = re.search(pat_side, src)
    if not m_side:
        raise PatchError("[P3] 侧边栏组件签名未找到")
    S0 = m_side.end()
    # 会话数组 state：[y,x]=r.useState([])（捕获 React 命名空间变量名 r，供注入 hook 用）
    m_state = re.search(
        rf"\[(?P<y>{ID}),{ID}\]=(?:\(0,)?(?P<rct>{ID})\.useState\)?\(\[\]\)", src[S0:]
    )
    if not m_state:
        raise PatchError("[P3] useState([]) 未找到")
    Y = m_state.group("y")
    RCT = m_state.group("rct")
    P0 = S0 + m_state.end()
    # loadSessions：D=r.useCallback(async(
    m_load = re.search(rf"(?P<D>{ID})=(?:\(0,)?{ID}\.useCallback\)?\(async\(", src[P0:])
    if not m_load:
        raise PatchError("[P3] useCallback(loadSessions) 未找到")
    D = m_load.group("D")
    # 注入点：组件 return(0,n.jsxs)("div",{style:{display:"flex",flexDirection:"column",...
    pat_ret = (
        rf'return\(0,(?P<n>{ID})\.jsxs\)\("div",\{{style:\{{display:"flex",'
        rf'flexDirection:"column",height:"100%",overflow:"hidden"\}}'
    )
    m_ret = list(re.finditer(pat_ret, src[P0:]))
    if not m_ret:
        raise PatchError("[P3] 根 return 锚点未找到")
    RET = P0 + m_ret[0].start()
    GS = m_side.groupdict()
    poller = (
        "(function(ids,onTick){var w=window;w.__piSM=w.__piSM||{};"
        "w.__piIsRun=w.__piIsRun||function(id){return !!(w.__piSM&&w.__piSM.map&&w.__piSM.map[id])};"
        "var key=ids.join(\"|\");"
        "if(w.__piSM.key!==key){w.__piSM.key=key;w.__piSM.map={};clearInterval(w.__piSM.timer);w.__piSM.timer=null}"
        "if(!w.__piSM.timer){var poll=async function(){var ch=false;"
        "await Promise.all(ids.map(async function(id){"
        "try{var r=await fetch(\"/api/agent/\"+encodeURIComponent(id));var d=await r.json();"
        "var v=!!(d&&d.running&&d.state&&d.state.isStreaming);"
        "if(w.__piSM.map[id]!==v){w.__piSM.map[id]=v;ch=true}}catch(err){}}));"
        "if(ch&&onTick)onTick()};poll();w.__piSM.timer=setInterval(poll,4e3)}})"
        f"({Y}.map(function(s){{return s.id}}),{D});"
    )
    # 折叠状态 hook（组件体顶层、根 return 前无条件执行，hook 顺序稳定）：
    # __piCLst = {cwd:1} 已收起的组；__piCLset 切换函数
    hook = (
        f"var __piCS=(0,{RCT}.useState)({{}}),__piCLst=__piCS[0],__piCLset=__piCS[1];"
    )
    src = src[:RET] + hook + poller + src[RET:]

    # 分组渲染：替换树 map（组件 props 键名稳定）
    pat_tmap = (
        rf"(?P<z>{ID})\.map\((?P<r>{ID})=>\(0,(?P<n>{ID})\.jsx\)\((?P<Y>{ID}),"
        rf"\{{node:(?P=r),selectedSessionId:(?P<sel>{ID}),onSelectSession:(?P<osel>{ID}),"
        rf"onRenamed:(?P<ren>{ID}),onSessionDeleted:(?P<p>{ID})=>\{{(?P<cb>{ID})\?\.\((?P=p)\),"
        rf"(?P<ld>{ID})\(\)\}},onBranchSession:(?P<obs>{ID}),onCloneSession:(?P<ocl>{ID}),"
        rf"onExportSession:(?P<oex>{ID}),depth:0\}},(?P=r)\.session\.id\)\)"
    )
    m_tm = [m for m in re.finditer(pat_tmap, src) if m.start() > S0]
    if len(m_tm) != 1:
        raise PatchError(f"[P3-groups] 命中 {len(m_tm)} 次")
    G = m_tm[0].groupdict()
    # 分组渲染（v2：组头带 ▼/▲ 切换箭头，可按目录收起/展开会话）
    grouped = (
        "(function(){var gm={};for(var s of " + Y + "){(gm[s.cwd]=gm[s.cwd]||[]).push(s)}"
        "var gs=Object.keys(gm).map(function(cwd){var arr=gm[cwd];"
        "var latest=arr.reduce(function(a,b){return a.modified>b.modified?a:b});"
        "return{cwd:cwd,arr:arr,latest:latest.modified}})"
        ".sort(function(a,b){return b.latest.localeCompare(a.latest)});"
        "var OS=function(ses){" + GS["ocwd"] + "?.(ses.cwd)," + GS["osel"] + "(ses)};"
        "return gs.map(function(G){var run=0;"
        "for(var ses of G.arr){if(window.__piIsRun&&window.__piIsRun(ses.id))run++}"
        "var tree=window.__piBT(G.arr);"
        "var TG=function(ev){ev.stopPropagation();__piCLset(function(pr){var n2=Object.assign({},pr);"
        "if(n2[G.cwd])delete n2[G.cwd];else n2[G.cwd]=1;return n2})};"
        "return (0," + G["n"] + ".jsxs)(\"div\",{children:["
        "(0," + G["n"] + ".jsxs)(\"div\",{onClick:function(){return " + GS["ocwd"] + "?.(G.cwd)},"
        "style:{display:\"flex\",alignItems:\"center\",gap:6,padding:\"8px 12px 4px\",cursor:\"pointer\",userSelect:\"none\"},children:["
        # 组头文件夹图标：收起=关闭文件夹(accent 色，点击展开) / 展开=打开文件夹(muted 色，点击收起)，
        # 17px strokeWidth 2（lucide folder / folder-open 官方 path；14→17 加大显眼，与工具栏主图标同级；
        # 占宽 17+2*2=21px → 圆点槽同步 21px 保持文字左对齐），仍可点击切换且 stopPropagation
        "(0," + G["n"] + ".jsx)(\"span\",{onClick:TG,title:__piCLst[G.cwd]?\"expand\":\"collapse\","
        "style:{display:\"inline-flex\",alignItems:\"center\",justifyContent:\"center\",padding:2,marginRight:2,flexShrink:0,"
        "lineHeight:0,cursor:\"pointer\",borderRadius:4,color:__piCLst[G.cwd]?\"var(--accent)\":\"var(--text-muted)\"},"
        "children:(0," + G["n"] + ".jsx)(\"svg\",{width:17,height:17,viewBox:\"0 0 24 24\",fill:\"none\",stroke:\"currentColor\","
        "strokeWidth:2,strokeLinecap:\"round\",strokeLinejoin:\"round\",style:{display:\"block\"},"
        "children:(0," + G["n"] + ".jsx)(\"path\",{d:__piCLst[G.cwd]"
        "?\"M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z\""
        ":\"m6 14 1.45-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5c0-1.1.9-2 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2\"})})}),"
        "(0," + G["n"] + ".jsx)(\"span\",{title:G.cwd,style:{fontSize:13,fontWeight:600,letterSpacing:\"0.03em\","
        "textTransform:\"uppercase\",flex:1,overflow:\"hidden\",textOverflow:\"ellipsis\",whiteSpace:\"nowrap\","
        "color:" + GS["scwd"] + "===G.cwd?\"var(--accent)\":\"var(--text-muted)\"},"
        "children:G.cwd.split(\"/\").filter(Boolean).slice(-2).join(\"/\")}),"
        "run>0?(0," + G["n"] + ".jsx)(\"span\",{title:\"running\",style:{fontSize:9.5,fontWeight:700,padding:\"1px 6px\","
        "borderRadius:9999,background:\"var(--success-bg)\",color:\"var(--success)\","
        "border:\"1px solid var(--success-border)\",flexShrink:0},children:String(run)+\" \\u25b6\"}):null]}),"
        # 已收起的组不渲染会话列表；未收起时不缩进（左对齐由行内 18px 圆点槽实现：
        # 标题文字恒 32px 与组名对齐；行悬停背景整行贯通，与组头一致）
        "__piCLst[G.cwd]?null:(0," + G["n"] + ".jsx)(\"div\",{style:{paddingLeft:0},children:tree.map(function(r){return (0,"
        + G["n"] + ".jsx)(" + G["Y"] + ",{node:r,selectedSessionId:" + G["sel"] + ","
        "onSelectSession:OS,onRenamed:" + G["ren"] + ",onSessionDeleted:function(id){" + G["cb"] + "?.(id)," + G["ld"] + "()},"
        "onBranchSession:" + G["obs"] + ",onCloneSession:" + G["ocl"] + ",onExportSession:" + G["oex"] + ",depth:0},r.session.id)})})"
        "]},G.cwd)})})()"
    )
    src = src[: m_tm[0].start()] + grouped + src[m_tm[0].end():]

    # 空态：0===U.length（选过滤后数组）→ 0===y.length（全部会话）
    # 空态在 JSX 中位于树 map 之前 → 从组件 return 处向后搜第一个命中
    m_empty = re.search(
        r"!(" + ID + ")&&!(" + ID + ")&&0===(" + ID + r")\.length&&",
        src[RET:],
    )
    if not m_empty:
        raise PatchError("[P3-empty] 空态锚点未找到")
    segs = m_empty.group(0)
    newsegs = segs[: segs.rfind("0===")] + "0===" + Y + ".length&&"
    ABS = RET + m_empty.start()
    src = src[:ABS] + newsegs + src[ABS + len(segs):]

    # ---------- P5：侧边栏菜单字体对齐 DSH Desktop ----------
    # DSH 参考：body 用系统字体栈(-apple-system,...,"PingFang SC",...)；菜单项 13px、次级 12px
    DSH_FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
                "'Hiragino Sans GB','Microsoft YaHei','Helvetica Neue',Helvetica,Arial,sans-serif")
    # 1) 侧边栏根容器注入 DSH 字体栈（作用域仅侧边栏，聊天区不受影响）
    # ⚠ hook+poller 已插在 RET 前，return 实际位置后移，必须重新搜索定位（不能用旧坐标）
    m5 = re.search(pat_ret, src[RET:])
    if not m5:
        raise PatchError("[P5] 侧边栏根 return 未找到")
    POS5 = RET + m5.start()
    seg5 = src[POS5:POS5 + 400]
    old_root = 'height:"100%",overflow:"hidden"},children:'
    if seg5.count(old_root) != 1:
        raise PatchError("[P5] 侧边栏根容器锚点异常")
    src = (
        src[:POS5]
        + seg5.replace(
            old_root,
            'height:"100%",overflow:"hidden",fontFamily:"' + DSH_FONT + '"},children:',
            1,
        )
        + src[POS5 + 400:]
    )
    # 2) 字号提升（DSH: 菜单项 13px / 次级 12px；会话标题/meta 行已并入 P15 处理）
    size_subs = [
        ("重命名输入 12→13",
         '"flex-1 text-[12px] py-1.25 px-2 border border-accent rounded-control outline-none bg-bg text-text h-[30px]"',
         '"flex-1 text-[13px] py-1.25 px-2 border border-accent rounded-control outline-none bg-bg text-text h-[30px]"'),
        ("新会话按钮 11→12",
         "sidebar-new-session-button flex h-7 shrink-0 items-center justify-center gap-1 rounded-control border px-2 text-[11px]",
         "sidebar-new-session-button flex h-7 shrink-0 items-center justify-center gap-1 rounded-control border px-2 text-[12px]"),
        ("cwd 行 12→13",
         'w-full flex items-center px-2.5 py-1.5 rounded-control cursor-pointer text-[12px] text-text text-left',
         'w-full flex items-center px-2.5 py-1.5 rounded-control cursor-pointer text-[13px] text-text text-left'),
        ("cwd 路径 11→12",
         'flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[11px] ${e?"text-text":"text-text-dim"}',
         'flex-1 overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12px] ${e?"text-text":"text-text-dim"}'),
        ("下拉项目项 11→12",
         'gap-[7px] w-full px-2.5 py-2 border-none border-b border-divider text-left text-[11px] font-mono',
         'gap-[7px] w-full px-2.5 py-2 border-none border-b border-divider text-left text-[12px] font-mono'),
        ("底部 toggle 11→12",
         'cursor:"pointer",fontSize:11,fontWeight:600,letterSpacing:"0.04em"',
         'cursor:"pointer",fontSize:12,fontWeight:600,letterSpacing:"0.04em"'),
    ]
    for name5, old5, new5 in size_subs:
        n5 = src.count(old5)
        if n5 != 1:
            raise PatchError(f"[P5] {name5} 锚点命中 {n5} 次")
        src = src.replace(old5, new5)

    # 3) +New 按钮：去掉 New 文字仅留 + 号；浅绿底 + 深绿图标（主题变量随明暗自适应；
    #    svg 用 currentColor，继承按钮 color）
    m_btn = list(re.finditer(
        rf'"aria-label":(?P<d>{ID})\("sidebar\.newSession"\),', src))
    if len(m_btn) != 1:
        raise PatchError(f"[P5] +New 按钮锚点命中 {len(m_btn)} 次")
    mb = m_btn[0]
    src = (
        src[: mb.end()]
        + 'style:{background:"var(--success-bg)",borderColor:"var(--success-border)",'
          'color:"var(--success)"},'
        + src[mb.end():]
    )
    m_txt = list(re.finditer(rf',{ID}\("common\.new"\)\]', src))
    if len(m_txt) != 1:
        raise PatchError(f"[P5] New 文字锚点命中 {len(m_txt)} 次")
    mt = m_txt[0]
    src = src[: mt.start()] + "]" + src[mt.end():]

    # 4) 侧边栏默认宽度 260 → 347（加宽 1/3；clamp 220–480 内，仍可手动拖动调整）
    for old_w, new_w in [
        ("LEFT_PANEL_DEFAULT_WIDTH:260", "LEFT_PANEL_DEFAULT_WIDTH:347"),
        ('"left",260,', '"left",347,'),
    ]:
        n_w = src.count(old_w)
        if n_w != 1:
            raise PatchError(f"[P5] 宽度锚点 {old_w} 命中 {n_w} 次")
        src = src.replace(old_w, new_w)

    # ---------- P7：输入框下方图标统一 18px（用户两轮反馈：右下角三个仍太小） ----------
    # 1) 工具行窗口（输入框下方 marginTop:8 那行）：附件 15→18、更多控件 13→18、
    #    思考级别选择器图标 11→14（弹窗内不常见，保持适度；弹窗内 10px 勾选标不动）
    pat_tb = 'style:{marginTop:8,display:"flex",alignItems:"center",gap:6,minHeight:32}'
    i_tb = src.find(pat_tb)
    if i_tb < 0:
        raise PatchError("[P7] 工具行锚点未找到")
    win = src[i_tb : i_tb + 6000]
    for old_i, new_i in [
        ('svg",{width:"15",height:"15"', 'svg",{width:"18",height:"18"'),
        ('svg",{width:"13",height:"13"', 'svg",{width:"18",height:"18"'),
        ('svg",{width:"11",height:"11"', 'svg",{width:"14",height:"14"'),
    ]:
        c_i = win.count(old_i)
        if c_i != 1:
            raise PatchError(f"[P7] 工具行 {old_i} 命中 {c_i} 次")
        win = win.replace(old_i, new_i)
    src = src[:i_tb] + win + src[i_tb + 6000 :]
    # 2) 三个工具行组件触发图标统一 18px（压缩名 dt/ds/da 会变，锚 props 签名）：
    #    模型选择器 14→18 / 模式切换 14→18 / 工具预设 11→18（只动触发图标，弹窗内不动）
    for label7, pat7, old7, new7 in [
        ("模型选择器",
         rf"function\s?[\w$]*\(\{{isStreaming:{ID},model:{ID},modelNames:{ID},modelList:{ID},onModelChange:{ID}\}}",
         'svg",{width:"14",height:"14"', 'svg",{width:"18",height:"18"'),
        ("模式切换",
         rf"function\s?[\w$]*\(\{{mode:{ID},disabled:{ID},onChange:{ID}\}}",
         'svg",{width:"14",height:"14"', 'svg",{width:"18",height:"18"'),
        ("工具预设",
         rf"function\s?[\w$]*\(\{{isStreaming:{ID},toolPreset:{ID},onToolPresetChange:{ID}\}}",
         'svg",{width:"11",height:"11"', 'svg",{width:"18",height:"18"'),
    ]:
        m7 = list(re.finditer(pat7, src))
        if len(m7) != 1:
            raise PatchError(f"[P7] {label7}签名命中 {len(m7)} 次")
        seg7 = src[m7[0].end() : m7[0].end() + 2500]
        c7 = seg7.count(old7)
        if c7 < 1:
            raise PatchError(f"[P7] {label7}图标锚点未找到")
        seg7 = seg7.replace(old7, new7, 1)
        src = src[: m7[0].end()] + seg7 + src[m7[0].end() + 2500 :]
    # 3) 发送按钮图标 15→18（用户反馈右下角仍太小，对齐左下角附件 18px）：
    #    主发送与排队追问两个 38px 圆钮（composer-icon-button）内的箭头 svg，
    #    viewBox 0 0 14 14 与工具行图标（viewBox 24）区分，恰 2 处、等长替换不影响坐标
    old_snd = 'svg",{width:"15",height:"15",viewBox:"0 0 14 14"'
    new_snd = 'svg",{width:"18",height:"18",viewBox:"0 0 14 14"'
    c_snd = src.count(old_snd)
    if c_snd != 2:
        raise PatchError(f"[P7] 发送按钮图标锚点命中 {c_snd} 次（期望 2）")
    src = src.replace(old_snd, new_snd)
    # 4) 右组尾部两个小图标（第四轮反馈“图案占位太小”）:
    #    执行中停止钮方块 10→18（chat.stopAgent，filled rect viewBox 10，全 chunk 唯一
    #    —— 同尺寸另有 compacting 方块但 rect 坐标不同且无 aria-hidden，不误伤）
    #    完成提示音喇叭 12→18（chat.*DoneSound，volume-2/volume-x 两态恰 2 处，
    #    锚 polygon points "11 5…" 喇叭形才能与其它 12px viewBox24 图标区分）
    old_sq = 'svg",{width:"10",height:"10",viewBox:"0 0 10 10",fill:"none","aria-hidden":"true",children:(0,n.jsx)("rect",{x:"1.5"'
    new_sq = 'svg",{width:"18",height:"18",viewBox:"0 0 10 10",fill:"none","aria-hidden":"true",children:(0,n.jsx)("rect",{x:"1.5"'
    c_sq = src.count(old_sq)
    if c_sq != 1:
        raise PatchError(f"[P7] 停止钮方块锚点命中 {c_sq} 次（期望 1）")
    src = src.replace(old_sq, new_sq)
    old_sp = 'svg",{width:"12",height:"12",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"2",strokeLinecap:"round",strokeLinejoin:"round",children:[(0,n.jsx)("polygon",{points:"11 5'
    new_sp = 'svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"2",strokeLinecap:"round",strokeLinejoin:"round",children:[(0,n.jsx)("polygon",{points:"11 5'
    c_sp = src.count(old_sp)
    if c_sp != 2:
        raise PatchError(f"[P7] 喇叭图标锚点命中 {c_sp} 次（期望 2）")
    src = src.replace(old_sp, new_sp)

    # ---------- P6b：JS 内联半透明菜单背景 → var(--bg)（不走 material-popover 的弹层） ----------
    # flyout 二级弹卡用 var(--bg-elevated)（65%）、危险提示弹卡用 var(--bg-panel)（65%），
    # 与主弹窗同色无色偏；其余 bg-elevated/bg-panel 用途（表头/按钮/输入框）由 CSS 变量去 alpha 覆盖
    for name6, old6, new6 in [
        ("flyout 菜单",
         'right:"100%",marginRight:6,background:"var(--bg-elevated)"',
         'right:"100%",marginRight:6,background:"var(--bg)"'),
        ("危险提示弹卡",
         'bottom:"calc(100% + 6px)",right:0,background:"var(--bg-panel)"',
         'bottom:"calc(100% + 6px)",right:0,background:"var(--bg)"'),
    ]:
        c6 = src.count(old6)
        if c6 != 1:
            raise PatchError(f"[P6b] {name6} 锚点命中 {c6} 次")
        src = src.replace(old6, new6)

    # ---------- P15：会话条目紧凑化（删 meta 行 + 标题右紧凑时间） ----------
    # ① 标题行 → flex 行：标题(13px/ellipsis/flex-1) + 最右紧凑相对时间（now/Nm/Nh/Nd，
    #    tabular-nums 防跳动，title 悬停看完整时间戳）；
    # ② meta 行（mt-0.5 时间+消息数）整块 → null（用户反馈排版乱）；
    #    两锚点均为原始串（P5 已不碰这两处，见 size_subs 注释）
    pat_p15t = (
        r'\(0,(' + ID + r')\.jsx\)\("div",\{className:`text-\[12px\] leading-\[1\.4\] overflow-hidden '
        r'text-ellipsis whitespace-nowrap \$\{(' + ID + r')\?"font-semibold text-text-strong":"font-medium text-text"\}`,'
        r'title:(' + ID + r'),children:\3\}\)'
    )
    ms15t = list(re.finditer(pat_p15t, src))
    if len(ms15t) != 1:
        raise PatchError(f"[P15] 标题行锚点命中 {len(ms15t)} 次")
    # session 变量名：标题锚点前最近的 function({session:X,isSelected: 签名
    m_sig15 = None
    for mm in re.finditer(r"function\s?[\w$]*\(\{session:(" + ID + r"),isSelected:", src[: ms15t[0].start()]):
        m_sig15 = mm
    if not m_sig15:
        raise PatchError("[P15] SessionItem 签名未找到")
    N15, T15, D15, S15 = ms15t[0].group(1), ms15t[0].group(2), ms15t[0].group(3), m_sig15.group(1)
    new_title = (
        '(0,' + N15 + '.jsxs)("div",{style:{display:"flex",alignItems:"baseline",minWidth:0},children:['
        '(0,' + N15 + '.jsx)("div",{className:`text-[13px] leading-[1.4] overflow-hidden text-ellipsis whitespace-nowrap flex-1 min-w-0 '
        '${' + T15 + '?"font-semibold text-text-strong":"font-medium text-text"}`,title:' + D15 + ',children:' + D15 + '}),'
        '(0,' + N15 + '.jsx)("span",{title:' + S15 + '.modified,'
        'style:{fontSize:10.5,color:"var(--text-dim)",flexShrink:0,marginLeft:4,fontVariantNumeric:"tabular-nums"},'
        'children:(function(ms){var df=Date.now()-new Date(ms).getTime();var mi=Math.floor(df/6e4);'
        'if(mi<1)return"now";if(mi<60)return mi+"m";var hh=Math.floor(mi/60);'
        'if(hh<24)return hh+"h";return Math.floor(hh/24)+"d"})(' + S15 + '.modified)})]})'
    )
    src = src[: ms15t[0].start()] + new_title + src[ms15t[0].end():]
    # ② meta 行（时间 + 消息数）整块 → null；内部相对时间函数用非贪婪 `.*?` 跨过函数体
    pat_p15m = (
        r'\(0,(' + ID + r')\.jsxs\)\("div",\{className:"mt-0\.5 flex gap-2 text-text-dim text-\[11px\]",children:\['
        r'\(0,\1\.jsx\)\("span",\{title:(' + ID + r')\.modified,children:function\([^)]*\)\{.*?\}\(\2\.modified,(' + ID + r')\)\}\),'
        r'\(0,\1\.jsx\)\("span",\{children:(' + ID + r')\("common\.messages",\{count:\2\.messageCount\}\)\}\)'
        r'\]\}\)'
    )
    ms15m = list(re.finditer(pat_p15m, src))
    if len(ms15m) != 1:
        raise PatchError(f"[P15] meta 行锚点命中 {len(ms15m)} 次")
    src = src[: ms15m[0].start()] + "null" + src[ms15m[0].end():]
    # ③ 行高：⚠ h-[Npx] 是 Tailwind 编译期类（CSS 仅含构建时的 .h-\[52px\] 规则），
    #    换任意 h-[Npx] 字符串都是死类（行高回落内容自然高~22px，改多大都无效——
    #    2026-09-21 五轮调高全不生效的根因）。改用自定义类，高度由 patch_css() 注入。
    #    兼容历史死类中间态（h-[40/50/60/80/100px] 版本均收敛到 __piRowH）。
    row_done = False
    for old_cls in ("h-[52px]", "h-[40px]", "h-[50px]", "h-[60px]", "h-[80px]", "h-[100px]"):
        anchor = old_cls + " flex items-center pr-2"
        if src.count(anchor) == 1:
            src = src.replace(anchor, "__piRowH flex items-center pr-2")
            row_done = True
            break
    if not row_done and src.count("__piRowH flex items-center pr-2") != 1:
        raise PatchError("[P15] 行高锚点未命中（52/历史值/自定义类均无）")

    # ---------- P3-3：状态圆点（SessionItem 标题前） ----------
    pat_dot = r'\]\}\),\(0,(' + ID + r')\.jsxs\)\("div",\{className:"flex-1 min-w-0",children:\['
    m_dot = re.search(pat_dot, src)
    if not m_dot:
        raise PatchError("[P3-dot] 标题容器锚点未找到")
    # 向前找 session 变量名：function({session:e,isSelected:
    m_sig = None
    for m in re.finditer(rf"function\s?[\w$]*\(\{{session:(?P<s>{ID}),isSelected:", src[: m_dot.start()]):
        m_sig = m
    if not m_sig:
        raise PatchError("[P3-dot] SessionItem 签名未找到")
    S = m_sig.group("s")
    # v5：固定 21px 圆点槽（与组头文件夹图标占宽同宽=17+2*2）——空闲不渲染圆点但占位不变，
    # 标题恒定从 35px 起（行内边距14+槽21=组头12+图标占宽21+2），与目录名文字左对齐，
    # 且空闲/运行切换不再引起标题横向跳动；绿点在槽内居中，正落文件夹图标下方
    dot = (
        ']}),(0,' + m_dot.group(1) + '.jsx)("span",{style:{width:21,flexShrink:0,display:"inline-flex",'
        'alignItems:"center",justifyContent:"center"},'
        'children:(window.__piIsRun&&window.__piIsRun(' + S + '.id))?(0,' + m_dot.group(1) + '.jsx)("span",{title:"running",'
        'style:{width:8,height:8,borderRadius:9999,background:"#22e06b"}}):null}),'
        '(0,' + m_dot.group(1) + '.jsxs)("div",{className:"flex-1 min-w-0",children:['
    )
    src = src[: m_dot.start()] + dot + src[m_dot.end():]

    # ---------- P16：顶部路径栏 → “新建目录”方形图标钮（原生目录选择器直通） ----------
    # 原顶部刍（显示 H(path) 缩写，点击开历史目录下拉）改为一行方形图标钮：
    #   [新建目录 w-7] [▾ w-7]   ……（ml-auto）……   [新会话] [刷新]
    #   （原标题行右侧的“新会话+刷新”按钮组整体下移到同一行，用户 2026-09-21 四调）
    #   新建目录 → 直接调 v()（即原下拉里“+ 自定义路径”：W()→electronAPI.selectDirectory()）
    #   ▾ → 仍开原下拉（历史目录/默认目录/自定义路径）
    # 四钮统一 h-7 w-7（28px 方形，与刷新钮同规格），等高由 h-7 直接保证（无需 stretch）。
    # 文案硬编码中文（未动语言包 chunk；i18n 化思路见 PATCHES.md）。
    pat_cwdbar = re.compile(
        r'\(0,(?P<ns>[A-Za-z_$][\w$]*)\.jsx\)\("button",\{onClick:\(\)=>m\(e=>!e\),className:`[^`]*`,'
        r'children:\(0,(?P=ns)\.jsx\)\("span",\{className:`[^`]*`,title:e\?\?"",'
        r'children:e\?H\(e,u\):l&&!c\.current\?"":d\("sidebar\.selectProject"\)\}\)\}\)'
    )
    m_bar = pat_cwdbar.search(src)
    if not m_bar:
        raise PatchError("[P16] 顶部目录栏锚点未命中")
    ns = m_bar.group("ns")
    jx, jxs = ns + ".jsx", ns + ".jsxs"
    PLUS_SVG = (
        f'(0,{jx})("svg",{{width:"14",height:"14",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",'
        f'strokeWidth:"2",strokeLinecap:"round",strokeLinejoin:"round",children:['
        f'(0,{jx})("path",{{d:"M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"}}),'
        f'(0,{jx})("path",{{d:"M12 10v6"}}),(0,{jx})("path",{{d:"M9 13h6"}})'
        f']}})'
    )
    CHEV_SVG = (
        f'(0,{jx})("svg",{{width:"12",height:"12",viewBox:"0 0 10 10",fill:"none",stroke:"currentColor",'
        f'strokeWidth:"1.8",strokeLinecap:"round",strokeLinejoin:"round",children:'
        f'(0,{jx})("polyline",{{points:"2 3.5 5 6.5 8 3.5"}})}})'
    )
    # ① 分别摘出“新会话”“刷新”两钮（整段抽移、不动内部），以及原标题行按钮组容器（用于置空）
    pat_newsess = re.compile(r'\(0,(?P<mns>' + ID + r')\.jsxs\)\("button",\{onClick:S,disabled:!e,')
    m_ns = pat_newsess.search(src)
    if not m_ns:
        raise PatchError("[P16] 新会话按钮锚点未命中")
    newsess = src[m_ns.start():jsx_expr_end(src, m_ns.start())]
    pat_refresh = re.compile(
        r'\(0,(?P<mrf>' + ID + r')\.jsx\)\("button",\{onClick:\(\)=>o\(!1\),'
        r'"aria-label":d\("sidebar\.refreshSessions"\)'
    )
    m_rf = pat_refresh.search(src)
    if not m_rf:
        raise PatchError("[P16] 刷新按钮锚点未命中")
    refresh = src[m_rf.start():jsx_expr_end(src, m_rf.start())]
    pat_titlebtns = re.compile(
        r'\(0,(?P<tns>' + ID + r')\.jsxs\)\("div",\{className:"ml-auto flex gap-1",children:\['
    )
    m_tb = pat_titlebtns.search(src)
    if not m_tb:
        raise PatchError("[P16] 标题行按钮组锚点未命中")
    titlebtns = src[m_tb.start():jsx_expr_end(src, m_tb.start())]

    # ② 统一样式：四钮同规格（h-7 w-7 p-0 方形 + chrome-button 底 + hover 高亮 + 150ms）
    #   UNI        = 无状态钮（新目录/▾）完整类串
    #   NEWSESS_BASE = 新会话/刷新基础串（颜色与 hover 由各自动态分支给，以保留禁用/完成态）
    UNI = (
        "flex h-7 w-7 shrink-0 items-center justify-center p-0 rounded-control border "
        "bg-chrome-button-bg border-border text-text-muted hover:bg-chrome-button-hover "
        "hover:text-accent hover:border-focus-ring "
        "transition-[background-color,border-color,color,transform] duration-150"
    )
    NEWSESS_BASE = (
        "flex h-7 shrink-0 items-center justify-center gap-1 rounded-control border px-2 "
        "text-[13px] font-medium tracking-normal bg-chrome-button-bg border-border "
        "transition-[background-color,border-color,color,transform] duration-150"
    )
    if newsess.count('style:{background:"var(--success-bg)"') != 1:
        raise PatchError("[P16] 新会话绿色内联样式锚点异常")
    newsess = newsess.replace(
        'style:{background:"var(--success-bg)",borderColor:"var(--success-border)",color:"var(--success)"},', ""
    )
    newsess = re.sub(
        r'className:`sidebar-new-session-button[^`]*`',
        'className:`sidebar-new-session-button ' + NEWSESS_BASE
        + ' ${e?"text-text-muted cursor-pointer hover:bg-chrome-button-hover hover:text-accent'
          ' hover:border-focus-ring":"text-text-dim cursor-not-allowed"}` ',
        newsess,
        count=1,
    )
    if newsess.count('("svg",{width:"11",height:"11",viewBox:"0 0 12 12"') != 1:
        raise PatchError("[P16] 新会话加号图标尺寸锚点异常")
    # 七调：+ 号改小改细（用户反馈太粗大、与文字不协调）——
    #   尺寸回 11px（上轮改 13 偏大）、描边 2.2→1.6、十字从满框（1..11）收进到 2.5..9.5
    for _old, _new in (
        ('strokeWidth:"2.2"', 'strokeWidth:"1.6"'),
        ('{x1:"6",y1:"1",x2:"6",y2:"11"}', '{x1:"6",y1:"2.5",x2:"6",y2:"9.5"}'),
        ('{x1:"1",y1:"6",x2:"11",y2:"6"}', '{x1:"2.5",y1:"6",x2:"9.5",y2:"6"}'),
    ):
        if newsess.count(_old) != 1:
            raise PatchError(f"[P16] 新会话加号锚点异常：{_old} × {newsess.count(_old)}")
        newsess = newsess.replace(_old, _new)
    if refresh.count("duration-250") != 1:
        raise PatchError("[P16] 刷新按钮时长锚点异常")
    refresh = refresh.replace("duration-250", "duration-150")
    # 新会话钮加文字标签“新会话”（图标+文字，宽度自适应；样式仍与其余三钮同底）
    if not newsess.endswith("]})"):
        raise PatchError(f"[P16] 新会话按钮尾部结构异常：{newsess[-12:]!r}")
    newsess = newsess[:-3] + ',(0,' + jx + ')("span",{children:"新会话"})]})'
    # 行容器：再下移一行 → 内联 marginTop:24（⚠ mt-4/5/6 及 mt-2.5 在本构建 CSS 里均不存在，
    #   mt-[24px] 也是死类，故用内联样式；左→右：新会话→新目录→▾→刷新，右对齐）
    new_bar = (
        f'(0,{jxs})("div",{{className:"flex items-center gap-1 justify-end",style:{{marginTop:24}},children:['
        f'{newsess},'
        f'(0,{jx})("button",{{onClick:function(){{return v()}},title:"新建目录（选择本地文件夹作为工作目录）",'
        f'className:"{UNI}",style:{{opacity:f?0.6:1}},children:{PLUS_SVG}}}),'
        f'(0,{jx})("button",{{onClick:function(){{return m(function(z){{return !z}})}},title:"历史目录列表",'
        f'className:"{UNI}",style:{{transform:g?"rotate(180deg)":"none",transition:"transform .15s"}},'
        f'children:{CHEV_SVG}}}),'
        f'{refresh}'
        f']}})'
    )
    src = src[: m_bar.start()] + new_bar + src[m_bar.end():]
    # ③ 原标题行里那组按钮置 null（新行已改由 newsess/refresh 两单钮拼成，容器不再复用）
    if src.count(titlebtns) != 1:
        raise PatchError(f"[P16] 标题行按钮组出现 {src.count(titlebtns)} 次（期望 1）")
    src = src.replace(titlebtns, "null", 1)

    if MARKER not in src or "__piCLst" not in src or "_piS" not in src or "PingFang SC" not in src:
        raise PatchError("自检失败：补丁标记未出现在产物中")
    if src.count("__piRowH flex items-center pr-2") != 1:
        raise PatchError("自检失败：P15 行高自定义类标记异常（CSS 规则由 patch_css 注入）")
    # P16：顶部目录栏已换成“文件夹+加号”图标钮（v()）+ ▾ 展开钮，且旧路径渲染已不存在
    # ⚠ 组头那处路径是三元字面量 `d:__piCLst[...]?"M20 20a2…"`（前面是 ? 不是 d:"），
    #   所以只能用不带前缀的宽松串计数（= 1 组头 + 1 本钮 = 2）
    if (src.count('d:"M12 10v6"') != 1 or src.count('d:"M9 13h6"') != 1
            or src.count('M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9') != 2):
        raise PatchError("自检失败：P16 新建目录图标（文件夹+加号）标记异常")
    if "H(e,u)" in src:
        raise PatchError("自检失败：P16 旧路径渲染尚未移除")
    # P16 四调/五调：四钮统一样式、同行、右对齐，且顺序为 新会话→新目录→▾→刷新
    if src.count("sidebar-new-session-button") != 1 or src.count("sidebar-refresh-button") != 1:
        raise PatchError("自检失败：P16 新会话/刷新按钮下移异常")
    _i1 = src.find("sidebar-new-session-button")
    _i2 = src.find("新建目录（选择本地文件夹")
    _i3 = src.find("历史目录列表")
    _i4 = src.find("sidebar-refresh-button")
    if not (0 <= _i1 < _i2 < _i3 < _i4):
        raise PatchError("自检失败：P16 按钮顺序异常（应 新会话→新目录→▾→刷新）")
    if src.count('className:"flex items-center gap-1 justify-end",style:{marginTop:24}') != 1:
        raise PatchError("自检失败：P16 按钮行容器异常（内联下移 24px / justify-end 右对齐）")
    if src.count('("span",{children:"新会话"})') != 1:
        raise PatchError("自检失败：P16 新会话文字标签异常")
    # 七调：+ 号改小改细（十字收进 2.5..9.5 为原版不存在的唯一标记；
    #   ⚠ strokeWidth:"1.6" 原版已有 2 处，不能当标记）
    if src.count('{x1:"6",y1:"2.5",x2:"6",y2:"9.5"}') != 1:
        raise PatchError("自检失败：P16 新会话加号改细标记异常")
    if "ml-auto flex gap-1" in src:
        raise PatchError("自检失败：P16 旧的按钮组容器未移除")
    if not re.search(r'sidebar-title-row flex items-center justify-between mb-2\.5",children:\[[^\]]{0,160}?,null\]', src):
        raise PatchError("自检失败：P16 标题行原按钮组未置空")
    # ⚠ 本补丁引入的 Tailwind 类必须已存在于编译 CSS（任意值类为构建期生成，
    #   不存在即静默失效——P15 行高踩过：改 h-[Npx] 五轮全无效）
    _css_text = open(find_css()[0], encoding="utf-8").read()
    for _c in ("flex", "items-center", "gap-1", "rounded-control",
               "text-text", "border", "border-border", "text-text-dim",
               "bg-chrome-button-bg", "hover:bg-chrome-button-hover", "hover:text-accent",
               "hover:border-focus-ring", "cursor-not-allowed", "cursor-pointer",
               "transition-[background-color,border-color,color,transform]", "duration-150",
               "shrink-0", "justify-center", "justify-end", "w-7", "h-7", "p-0", "px-2",
               "text-[13px]", "font-medium", "tracking-normal", "text-text-muted"):
        _esc = re.sub(r"([\[\]\.:/\+,%#()])", r"\\\1", _c)
        if "." + _esc not in _css_text:
            raise PatchError(f"自检失败：P16 所用 Tailwind 类在编译 CSS 中不存在：{_c}")
    # ⚠ 更多控件也是 18x18 viewBox 24 strokeWidth 1.8，附件自检必须延伸到子元素 rect 才唯一
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"1.8",strokeLinecap:"round",strokeLinejoin:"round",children:[(0,n.jsx)("rect",{x:"3",y:"3"') != 1:
        raise PatchError("自检失败：P7 附件图标标记异常")
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"1.8",strokeLinecap:"round",strokeLinejoin:"round",children:[(0,n.jsx)("line",{x1:"4",y1:"6"') != 1:
        raise PatchError("自检失败：P7 更多控件图标标记异常")
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 14 14"') != 2:
        raise PatchError("自检失败：P7 发送按钮图标标记异常")
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 10 10"') != 1:
        raise PatchError("自检失败：P7 停止钮方块标记异常")
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"2",strokeLinecap:"round",strokeLinejoin:"round",children:[(0,n.jsx)("polygon",{points:"11 5') != 2:
        raise PatchError("自检失败：P7 喇叭图标标记异常")
    if src.count('marginRight:6,background:"var(--bg)"') != 1:
        raise PatchError("自检失败：P6b 标记异常")
    if src.count('fontVariantNumeric:"tabular-nums"') != 1:
        raise PatchError("自检失败：P15 标记异常")
    if src.count('return mi+"m"') != 1:
        raise PatchError("自检失败：P15 时间函数标记异常")

    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ 补丁已写入 {chunk}")
    print(f"   大小 {len(orig)} -> {len(src)}")
    patch_js_dsh_sizes()  # P8c：在 P1-P7 之后扫（P5 锚点依赖原始字号值）
    # P13 放最后：消息级规则已由 P1-msg 注入，此处改写其 null 分支为错误条
    patch_error_banner()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PatchError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未预期错误: {e}", file=sys.stderr)
        sys.exit(2)
