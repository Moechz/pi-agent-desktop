$target = Join-Path $env:LOCALAPPDATA 'Programs\pi-agent-desktop'
$ans = Read-Host '确定卸载 Pi Agent Desktop（定制版）吗？会话/聊天数据将保留 (Y/N)'
if ($ans -notmatch '^[Yy]') { exit 0 }

Get-Process -Name 'Pi Agent Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

# 先删除除本脚本外的全部文件（脚本自身运行中无法删除）
Get-ChildItem $target | Where-Object { $_.Name -ne 'uninstall.ps1' } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Remove-Item "$env:USERPROFILE\Desktop\Pi Agent Desktop.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Pi Agent Desktop.lnk" -Force -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\PiAgentDesktopCustom' -Force -ErrorAction SilentlyContinue

# 自删除：延迟后由 cmd 删除脚本自身与目录
Start-Process cmd.exe -WindowStyle Hidden -ArgumentList '/c', ("timeout /t 3 /nobreak >nul & del /q `"$target\uninstall.ps1`" & rmdir /q `"$target`"")
Write-Host '卸载完成（会话数据保留在 %APPDATA% 下）。'
