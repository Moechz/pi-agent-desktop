#!/usr/bin/env python3
"""
Pi Agent Desktop UI 补丁自动重打器（语义锚点版）
更新应用后编译产物的文件名/压缩变量名会变，本脚本用稳定结构特征
（CSS 类名、prop 键名、内联样式串）动态定位，跨版本重打 4 组补丁：
  P1 会话完成后只留最后一条文本结果（消息级 + 块级 + 无文本整条隐藏）
  P2 输入框边框加强
  P3 侧边栏项目平铺 + 会话运行状态点（树构建器存档/轮询器/分组渲染/空态/圆点）
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
    repl_block = (
        rf'children:(function(){{var li=-1;{g["m"]}.forEach(function(bb,i2){{if("text"===bb.type)li=i2}});'
        rf'return {g["m"]}.map(({g["b"]},{g["q"]})=>!{IS}&&("text"!=={g["b"]}.type||{g["q"]}!==li)?null:'
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
    inject = (
        f"{g4['v']}=\"assistant\"==={g4['msg']}.role&&{g4['msgs']}[{g4['idx']}+1]"
        f"&&\"assistant\"==={g4['msgs']}[{g4['idx']}+1].role?null:"
    )
    seg = m_ml[0].group(0)
    src = src[: m_ml[0].start()] + seg.replace(
        g4["v"] + "=(0,", inject + "(0,", 1
    ) + src[m_ml[0].end():]

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
    # 会话数组 state：[y,x]=r.useState([])
    m_state = re.search(rf"\[(?P<y>{ID}),{ID}\]=(?:\(0,)?{ID}\.useState\)?\(\[\]\)", src[S0:])
    if not m_state:
        raise PatchError("[P3] useState([]) 未找到")
    Y = m_state.group("y")
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
    src = src[:RET] + poller + src[RET:]

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
        "return (0," + G["n"] + ".jsxs)(\"div\",{children:["
        "(0," + G["n"] + ".jsxs)(\"div\",{onClick:function(){return " + GS["ocwd"] + "?.(G.cwd)},"
        "style:{display:\"flex\",alignItems:\"center\",gap:6,padding:\"8px 12px 4px\",cursor:\"pointer\",userSelect:\"none\"},children:["
        "(0," + G["n"] + ".jsx)(\"svg\",{width:11,height:11,viewBox:\"0 0 24 24\",fill:\"none\",stroke:\"currentColor\",strokeWidth:1.8,"
        "style:{color:\"var(--text-dim)\",flexShrink:0},children:(0," + G["n"] + ".jsx)(\"path\","
        "{d:\"M1 3A1 1 0 0 1 2 2H4L5 3.5H8.5a.5.5 0 0 1 .5.5v4a.5.5 0 0 1-.5.5h-7A.5.5 0 0 1 1 8V3Z\"})}),"
        "(0," + G["n"] + ".jsx)(\"span\",{title:G.cwd,style:{fontSize:10.5,fontWeight:600,letterSpacing:\"0.03em\","
        "textTransform:\"uppercase\",flex:1,overflow:\"hidden\",textOverflow:\"ellipsis\",whiteSpace:\"nowrap\","
        "color:" + GS["scwd"] + "===G.cwd?\"var(--accent)\":\"var(--text-muted)\"},"
        "children:G.cwd.split(\"/\").filter(Boolean).slice(-2).join(\"/\")}),"
        "run>0?(0," + G["n"] + ".jsx)(\"span\",{title:\"running\",style:{fontSize:9.5,fontWeight:700,padding:\"1px 6px\","
        "borderRadius:9999,background:\"var(--success-bg)\",color:\"var(--success)\","
        "border:\"1px solid var(--success-border)\",flexShrink:0},children:String(run)+\" \\u25b6\"}):null]}),"
        "tree.map(function(r){return (0," + G["n"] + ".jsx)(" + G["Y"] + ",{node:r,selectedSessionId:" + G["sel"] + ","
        "onSelectSession:OS,onRenamed:" + G["ren"] + ",onSessionDeleted:function(id){" + G["cb"] + "?.(id)," + G["ld"] + "()},"
        "onBranchSession:" + G["obs"] + ",onCloneSession:" + G["ocl"] + ",onExportSession:" + G["oex"] + ",depth:0},r.session.id)})"
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
        "background:window.__piIsRun&&window.__piIsRun(" + S + '.id)?"var(--success)":"var(--text-dim)",'
        "opacity:window.__piIsRun&&window.__piIsRun(" + S + '.id)?1:.35,'
        "boxShadow:window.__piIsRun&&window.__piIsRun(" + S + '.id)?"0 0 7px var(--success)":"none",'
        'transition:"background .3s,opacity .3s,box-shadow .3s"}}),'
        '(0,' + m_dot.group(1) + '.jsxs)("div",{className:"flex-1 min-w-0",children:['
    )
    src = src[: m_dot.start()] + dot + src[m_dot.end():]

    if MARKER not in src:
        raise PatchError("自检失败：补丁标记未出现在产物中")

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
