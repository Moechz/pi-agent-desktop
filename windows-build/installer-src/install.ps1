$ErrorActionPreference = 'Stop'
$target = Join-Path $env:LOCALAPPDATA 'Programs\pi-agent-desktop'
$src    = Join-Path $PSScriptRoot 'app'

Write-Host '==============================================='
Write-Host '   Pi Agent Desktop 定制版 安装程序 (0.8.8)'
Write-Host '==============================================='
Write-Host ''

# 应用若正在运行则提示退出（避免文件占用导致复制失败）
$proc = Get-Process -Name 'Pi Agent Desktop' -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host '[!] Pi Agent Desktop 正在运行，请先完全退出后重新运行本安装程序。' -ForegroundColor Yellow
    Read-Host  '按回车键退出'
    exit 1
}

Write-Host "[1/4] 复制文件到 $target （约 600MB，请稍候）..."
robocopy $src $target /E /MIR /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "[X] 复制失败（robocopy 代码 $LASTEXITCODE），请截图反馈。" -ForegroundColor Red
    Read-Host  '按回车键退出'
    exit 1
}

Copy-Item (Join-Path $PSScriptRoot 'uninstall.ps1')       $target -Force
Copy-Item (Join-Path $PSScriptRoot 'README-安装说明.txt') $target -Force

Write-Host '[2/4] 创建快捷方式（桌面 + 开始菜单）...'
$ws = New-Object -ComObject WScript.Shell
foreach ($dir in @("$env:USERPROFILE\Desktop", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")) {
    $lnk = $ws.CreateShortcut((Join-Path $dir 'Pi Agent Desktop.lnk'))
    $lnk.TargetPath    = Join-Path $target 'Pi Agent Desktop.exe'
    $lnk.WorkingDirectory = $target
    $lnk.IconLocation  = Join-Path $target 'Pi Agent Desktop.exe'
    $lnk.Save()
}

Write-Host '[3/4] 注册卸载信息（开始菜单可搜索"卸载"）...'
$reg = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PiAgentDesktopCustom'
New-Item -Path $reg -Force | Out-Null
Set-ItemProperty $reg -Name DisplayName       -Value 'Pi Agent Desktop (定制版)'
Set-ItemProperty $reg -Name DisplayVersion    -Value '0.8.8-custom'
Set-ItemProperty $reg -Name Publisher         -Value '内部定制分发'
Set-ItemProperty $reg -Name InstallLocation   -Value $target
Set-ItemProperty $reg -Name DisplayIcon       -Value (Join-Path $target 'Pi Agent Desktop.exe')
Set-ItemProperty $reg -Name NoModify          -Value 1
Set-ItemProperty $reg -Name NoRepair          -Value 1
Set-ItemProperty $reg -Name UninstallString   -Value ('powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $target 'uninstall.ps1') + '"')

Write-Host '[4/4] 安装完成！'
Write-Host ''
Write-Host "  安装位置 : $target"
Write-Host "  本定制版已禁用自动更新（保护界面定制不被覆盖）。"
Write-Host "  首次启动若被 Windows 拦截，见安装目录内 README-安装说明.txt。"
Write-Host ''
$launch = Read-Host '是否立即启动 Pi Agent Desktop？(Y/N)'
if ($launch -match '^[Yy]') { Start-Process (Join-Path $target 'Pi Agent Desktop.exe') }
