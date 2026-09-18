# Windows 定制版安装器（windows-build）

把 7 组 UI 补丁打包成**免管理员、用户数据空白**的 Windows 安装器，分发给同事。

## 产物

- `Pi-Agent-Desktop-Custom-Setup-0.8.8.exe`（142MB；r2 = 含 P8 字体配色/P3v2 实心点/P1v3 轮次级隐藏，SHA256 见 `SHA256SUMS.txt`）
- 结构 = 官方 `7z.sfx` 模块 + UTF-8 配置（BeginPrompt/RunProgram）+ 7z 归档
  （app/ + install.ps1 + uninstall.ps1 + README-安装说明.txt）
- 安装到 `%LOCALAPPDATA%\Programs\pi-agent-desktop`（每用户，无需管理员），
  建桌面+开始菜单快捷方式，注册 HKCU 卸载项，可选装完启动

## 与官方 0.8.8 的差异（全部）

| 改动 | 目的 |
|---|---|
| `.next/static/chunks/0wz_4dmun1la1.js` 替换为打补丁版（补丁集与 Mac 运行时一致；md5 随补丁版本变，r2 期 Mac=`3d54fccc…`） | 7 组 UI 补丁 + P8 系 + P3v2 + P1v3 |
| `.next/static/chunks/1o8y9tk-h0e51.css` 替换为打补丁版 | P6 弹窗不透明 |
| 删除 `resources/app-update.yml` | 禁自动更新（官方更新会覆盖补丁；主进程对配置缺失是 logError 静默，已核实） |

隐私：已全量扫描（用户名/主机名//Users 路径/tnas/密钥模式/邮箱），零真实命中
（命中项均为 Chromium 语言包随机字节、npm 测试样例、上游开源作者邮箱等误报）。

## 构建流水线（出新版后重跑）

```bash
cd windows-build
# 1) 下载新版官方 Setup exe（改文件名）
curl -L -o Pi-Agent-Desktop-Setup-<ver>-official.exe <github release url>
# 2) 解包 + 解 app-64.7z
~/tools/7zip/7zz x -oofficial-extracted Pi-Agent-Desktop-Setup-<ver>-official.exe
~/tools/7zip/7zz x -oapp-official 'official-extracted/$PLUGINSDIR/app-64.7z'
# 3) 复制为 app-custom 并打补丁（锚点失配则先按 PATCHES.md §6 适配）
cp -R app-official app-custom
PI_STANDALONE="$PWD/app-custom/resources/standalone" python3 ../apply_patches.py
rm app-custom/resources/app-update.yml        # 禁自动更新
# 4) 封装（更新 build-installer.sh 里 VER 变量）
./build-installer.sh
```

依赖：`~/tools/7zip/7zz`（ip7z/7zip releases 的 mac tar.xz）与 `7z.sfx`
（取自官方 7-Zip Windows 安装器解包，见 `~/tools/7zip/payload/7z.sfx`）。
⚠ 本机无 brew/sudo/docker —— 别依赖它们；网络需走代理 `http://127.0.0.1:7890`。

## 同事侧须知

- 未签名：首次运行 SmartScreen → "更多信息" → "仍要运行"
- 已禁自动更新；回官方版 = 卸载后装官方安装器
- 卸载保留会话数据

## 待办 / 已知限制

- [ ] Windows 实机验证（安装、7 组 UI 生效、更新检查静默、卸载干净）
- [ ] install.ps1 未过 pwsh 语法校验（本机无 pwsh），实机验证覆盖
- 若新版官方更新了 UI 结构，apply_patches.py 锚点失配属正常，按 PATCHES.md §6 适配后重跑流水线
