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
DSH2_MARK = "/*__piDSH2*/"  # P8b 字号阶梯追加标记
FS_MARK = "/*__piFS*/"  # P8c JS 字号扫掠一次性标记（防 11→12 后被二次升 13）
DSH_FONT = (
    '-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",'
    '"Hiragino Sans GB","Microsoft YaHei","Helvetica Neue",Helvetica,Arial,sans-serif'
)
ID = r"[A-Za-z_$][A-Za-z0-9_$]*"


class PatchError(Exception):
    pass


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
    if changed:
        tmp = css + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(head + tail)
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
    chunk, src = find_chunk()
    if MARKER in src:
        print("已是补丁状态，跳过")
        patch_js_dsh_sizes()  # P8c 独立幂等，已打 P1-P7 的文件也能补
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
        # 切换箭头：收起=▼(向下,点击展开,accent 色) / 展开=▲(向上,点击收起,muted 色)，14px 加粗描边看得清
        "(0," + G["n"] + ".jsx)(\"span\",{onClick:TG,title:__piCLst[G.cwd]?\"expand\":\"collapse\","
        "style:{display:\"inline-flex\",alignItems:\"center\",justifyContent:\"center\",padding:2,marginRight:2,flexShrink:0,"
        "lineHeight:0,cursor:\"pointer\",borderRadius:4,color:__piCLst[G.cwd]?\"var(--accent)\":\"var(--text-muted)\"},"
        "children:(0," + G["n"] + ".jsx)(\"svg\",{width:14,height:14,viewBox:\"0 0 24 24\",fill:\"none\",stroke:\"currentColor\","
        "strokeWidth:3,strokeLinecap:\"round\",strokeLinejoin:\"round\",style:{display:\"block\"},"
        "children:(0," + G["n"] + ".jsx)(\"path\",{d:__piCLst[G.cwd]?\"M6 9l6 6 6-6\":\"M18 15l-6-6-6 6\"})})}),"
        "(0," + G["n"] + ".jsx)(\"span\",{title:G.cwd,style:{fontSize:13,fontWeight:600,letterSpacing:\"0.03em\","
        "textTransform:\"uppercase\",flex:1,overflow:\"hidden\",textOverflow:\"ellipsis\",whiteSpace:\"nowrap\","
        "color:" + GS["scwd"] + "===G.cwd?\"var(--accent)\":\"var(--text-muted)\"},"
        "children:G.cwd.split(\"/\").filter(Boolean).slice(-2).join(\"/\")}),"
        "run>0?(0," + G["n"] + ".jsx)(\"span\",{title:\"running\",style:{fontSize:9.5,fontWeight:700,padding:\"1px 6px\","
        "borderRadius:9999,background:\"var(--success-bg)\",color:\"var(--success)\","
        "border:\"1px solid var(--success-border)\",flexShrink:0},children:String(run)+\" \\u25b6\"}):null]}),"
        # 已收起的组不渲染会话列表；未收起时包 paddingLeft:14 容器（二级菜单缩进效果）
        "__piCLst[G.cwd]?null:(0," + G["n"] + ".jsx)(\"div\",{style:{paddingLeft:14},children:tree.map(function(r){return (0,"
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
    # 2) 字号提升（DSH: 菜单项 13px / 次级 12px）
    size_subs = [
        ("会话标题 12→13",
         "text-[12px] leading-[1.4] overflow-hidden text-ellipsis whitespace-nowrap ",
         "text-[13px] leading-[1.4] overflow-hidden text-ellipsis whitespace-nowrap "),
        ("meta 行 11→12",
         '"mt-0.5 flex gap-2 text-text-dim text-[11px]"',
         '"mt-0.5 flex gap-2 text-text-dim text-[12px]"'),
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
    dot = (
        ']}),(0,' + m_dot.group(1) + '.jsx)("span",{title:window.__piIsRun&&window.__piIsRun(' + S + '.id)?"running":"idle",'
        "style:{width:8,height:8,borderRadius:9999,flexShrink:0,marginLeft:2,marginRight:8,"
        "background:window.__piIsRun&&window.__piIsRun(" + S + '.id)?"#22e06b":"var(--text-muted)",'
        "opacity:window.__piIsRun&&window.__piIsRun(" + S + '.id)?1:.55,'
        # v2：去光晕实体圆点（用户 2026-09-19 要求），无 boxShadow；旧文件由 patch_dot_solid 迁移
        'transition:"background .3s,opacity .3s"}}),'
        '(0,' + m_dot.group(1) + '.jsxs)("div",{className:"flex-1 min-w-0",children:['
    )
    src = src[: m_dot.start()] + dot + src[m_dot.end():]

    if MARKER not in src or "__piCLst" not in src or "_piS" not in src or "PingFang SC" not in src:
        raise PatchError("自检失败：补丁标记未出现在产物中")
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

    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ 补丁已写入 {chunk}")
    print(f"   大小 {len(orig)} -> {len(src)}")
    patch_js_dsh_sizes()  # P8c：在 P1-P7 之后扫（P5 锚点依赖原始字号值）
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
