(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,53348,e=>{"use strict";var r=e.i(18050),t=e.i(71645),a=e.i(29761);let o=`
  :root {
    --pge-bg: #f8f9fc;
    --pge-panel: #ffffff;
    --pge-border: rgba(0, 0, 0, 0.08);
    --pge-text: #364152;
    --pge-text-strong: #182230;
    --pge-text-muted: #64748b;
    --pge-accent: #ff8f40;
    --pge-accent-hover: #f27d2f;
    --pge-accent-contrast: #ffffff;
    --pge-danger: #d95757;
    --pge-danger-bg: rgba(217, 87, 87, 0.1);
    --pge-danger-border: rgba(217, 87, 87, 0.32);
    --pge-shadow: 0 12px 40px rgba(15, 23, 42, 0.16);
    color-scheme: light;
  }
  html.dark {
    --pge-bg: #050505;
    --pge-panel: #0c1118;
    --pge-border: rgba(255, 255, 255, 0.08);
    --pge-text: #d9deea;
    --pge-text-strong: #f0f3f8;
    --pge-text-muted: #a7b0c0;
    --pge-accent: #ffb454;
    --pge-accent-hover: #ffd173;
    --pge-accent-contrast: #1b1307;
    --pge-danger: #ff8f8f;
    --pge-danger-bg: rgba(255, 143, 143, 0.08);
    --pge-danger-border: rgba(255, 143, 143, 0.28);
    --pge-shadow: 0 12px 40px rgba(0, 0, 0, 0.6);
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    background: var(--pge-bg);
    color: var(--pge-text);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  .pge-panel {
    width: 100%;
    max-width: 28rem;
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 24px;
    border: 1px solid var(--pge-border);
    border-radius: 12px;
    background: var(--pge-panel);
    box-shadow: var(--pge-shadow);
  }
  .pge-title {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--pge-text-strong);
  }
  .pge-description {
    margin: 0;
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--pge-text-muted);
  }
  .pge-message {
    margin: 0;
    max-height: 10rem;
    overflow: auto;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    padding: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.75rem;
    color: var(--pge-danger);
    background: var(--pge-danger-bg);
    border: 1px solid var(--pge-danger-border);
    border-radius: 8px;
  }
  .pge-digest {
    margin: 0;
    font-size: 0.75rem;
    color: var(--pge-text-muted);
    opacity: 0.75;
  }
  .pge-footer { display: flex; justify-content: flex-end; }
  .pge-button {
    cursor: pointer;
    padding: 6px 12px;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--pge-accent-contrast);
    background: var(--pge-accent);
    border: none;
    border-radius: 8px;
    transition: background-color 0.15s ease;
  }
  .pge-button:hover { background: var(--pge-accent-hover); }
`;e.s(["default",0,function({error:e,retry:g}){let[n,s]=(0,t.useState)(a.DEFAULT_LOCALE);return(0,t.useEffect)(()=>{s(function(){try{let e=(0,a.normalizePreference)(localStorage.getItem(a.LOCALE_STORAGE_KEY)),r=navigator.languages?.length?navigator.languages:[navigator.language];return(0,a.resolveLocale)(e,r)}catch{return a.DEFAULT_LOCALE}}()),console.error("[global-error-boundary]",e)},[e]),(0,r.jsxs)("html",{lang:n,suppressHydrationWarning:!0,children:[(0,r.jsxs)("head",{children:[(0,r.jsx)("script",{dangerouslySetInnerHTML:{__html:'(function(){try{var t=localStorage.getItem("pi-theme");document.documentElement.classList.toggle("dark",t==="dark")}catch(e){}})();'}}),(0,r.jsx)("style",{dangerouslySetInnerHTML:{__html:o}})]}),(0,r.jsx)("body",{children:(0,r.jsxs)("div",{className:"pge-panel",children:[(0,r.jsx)("h2",{className:"pge-title",children:(0,a.translate)(n,"error.title")}),(0,r.jsx)("p",{className:"pge-description",children:(0,a.translate)(n,"error.description")}),(0,r.jsx)("pre",{className:"pge-message",children:e.message}),e.digest?(0,r.jsx)("p",{className:"pge-digest",children:(0,a.translate)(n,"error.digest",{digest:e.digest})}):null,(0,r.jsx)("div",{className:"pge-footer",children:(0,r.jsx)("button",{type:"button",onClick:()=>g(),className:"pge-button",children:(0,a.translate)(n,"error.reload")})})]})})]})}])}]);