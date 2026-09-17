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
  P6 菜单/弹窗不透明（CSS：--material-popover 两主题去 alpha；独立于 JS 幂等）
  P7 输入框下方工具行图标加大（附件/模型/模式/预设/更多控件 +3px）
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
    """P6：菜单/弹窗不透明。
    透明度来源是设计默认值 --material-popover 带 alpha（暗 #161b23e6≈90%、
    亮 #ffffffdb≈86%）+ .material-popover 的 30px backdrop blur；不透明覆盖规则
    只在 prefers-reduced-transparency/@media 里，普通设置不生效。
    修法：两个主题的变量值直接去掉 alpha（背景全不透明后 blur 无视觉效果）。
    .ui-dialog-surface 等弹窗同用此变量，一并变实。幂等：已打则跳过。"""
    css, data = find_css()
    subs = [
        ("--material-popover:#161b23e6", "--material-popover:#161b23"),
        ("--material-popover:#ffffffdb", "--material-popover:#ffffff"),
    ]
    changed = False
    for old, new in subs:
        n = data.count(old)
        if n == 1:
            data = data.replace(old, new)
            changed = True
        elif n == 0 and re.search(re.escape(new) + r"(?![0-9a-fA-F])", data):
            pass  # 已是补丁状态
        else:
            raise PatchError(f"[P6] CSS 锚点 {old} 命中 {n} 次（主题色板可能已改）")
    if changed:
        tmp = css + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, css)
        print(f"✅ [P6] 弹窗不透明已写入 {css}")
    else:
        print("ℹ️ [P6] CSS 已是补丁状态")
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
    # P6 是 CSS 补丁，独立于 JS MARKER 幂等（JS 已打过时也要能补 CSS）
    patch_css()
    chunk, src = find_chunk()
    if MARKER in src:
        print("已是补丁状态，跳过")
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
    # 用 !agentRunning 门控：任务执行中全显，完成后才收起。
    inject = (
        f"{g4['v']}=!{AG}&&\"assistant\"==={g4['msg']}.role"
        f"&&(function(){{for(var k2={g4['idx']}+1;k2<{g4['msgs']}.length;k2++){{"
        f"var r2={g4['msgs']}[k2].role;if(\"user\"===r2)return!1;if(\"assistant\"===r2)return!0}}"
        f"return!1}})()?null:"
    )
    seg = m_ml[0].group(0)
    seg = seg.replace(g4["v"] + "=(0,", inject + "(0,", 1)
    # cQ 调用补传 isStreaming=agentRunning：执行中块级/消息级规则放行（全过程可见）
    cqcall = g4["cq"] + ",{message:" + g4["msg"] + ","
    if seg.count(cqcall) != 1:
        raise PatchError("[P4] cQ 调用锚点异常")
    seg = seg.replace(cqcall, cqcall + "isStreaming:" + AG + ",", 1)
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

    # ---------- P7：输入框下方工具行图标加大（用户反馈太小看不清） ----------
    # 1) 工具行窗口（输入框下方 marginTop:8 那行）：附件 15→18、更多控件 13→16、
    #    思考级别选择器图标 11→14（窗口内各尺寸均恰一个，弹窗内 10px 勾选标不动）
    pat_tb = 'style:{marginTop:8,display:"flex",alignItems:"center",gap:6,minHeight:32}'
    i_tb = src.find(pat_tb)
    if i_tb < 0:
        raise PatchError("[P7] 工具行锚点未找到")
    win = src[i_tb : i_tb + 6000]
    for old_i, new_i in [
        ('svg",{width:"15",height:"15"', 'svg",{width:"18",height:"18"'),
        ('svg",{width:"13",height:"13"', 'svg",{width:"16",height:"16"'),
        ('svg",{width:"11",height:"11"', 'svg",{width:"14",height:"14"'),
    ]:
        c_i = win.count(old_i)
        if c_i != 1:
            raise PatchError(f"[P7] 工具行 {old_i} 命中 {c_i} 次")
        win = win.replace(old_i, new_i)
    src = src[:i_tb] + win + src[i_tb + 6000 :]
    # 2) 三个工具行组件触发图标（组件压缩名会变，用 props 签名锚定）：
    #    模型选择器 14→17 / 模式切换 14→17 / 工具预设 11→14（只动触发图标，弹窗内不动）
    for label7, pat7, old7, new7 in [
        ("模型选择器",
         rf"function\s?[\w$]*\(\{{isStreaming:{ID},model:{ID},modelNames:{ID},modelList:{ID},onModelChange:{ID}\}}",
         'svg",{width:"14",height:"14"', 'svg",{width:"17",height:"17"'),
        ("模式切换",
         rf"function\s?[\w$]*\(\{{mode:{ID},disabled:{ID},onChange:{ID}\}}",
         'svg",{width:"14",height:"14"', 'svg",{width:"17",height:"17"'),
        ("工具预设",
         rf"function\s?[\w$]*\(\{{isStreaming:{ID},toolPreset:{ID},onToolPresetChange:{ID}\}}",
         'svg",{width:"11",height:"11"', 'svg",{width:"14",height:"14"'),
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
        "boxShadow:window.__piIsRun&&window.__piIsRun(" + S + '.id)?"0 0 9px 2px rgba(34,224,107,.75)":"none",'
        'transition:"background .3s,opacity .3s,box-shadow .3s"}}),'
        '(0,' + m_dot.group(1) + '.jsxs)("div",{className:"flex-1 min-w-0",children:['
    )
    src = src[: m_dot.start()] + dot + src[m_dot.end():]

    if MARKER not in src or "__piCLst" not in src or "_piS" not in src or "PingFang SC" not in src:
        raise PatchError("自检失败：补丁标记未出现在产物中")
    if src.count('svg",{width:"18",height:"18",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"1.8"') != 1:
        raise PatchError("自检失败：P7 图标标记异常")

    tmp = chunk + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, chunk)
    print(f"✅ 补丁已写入 {chunk}")
    print(f"   大小 {len(orig)} -> {len(src)}")
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
