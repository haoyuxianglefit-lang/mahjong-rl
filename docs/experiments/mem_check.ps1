$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
$freeGB = [math]::Round($os.FreePhysicalMemory/1MB,1)
$usedGB = [math]::Round($totalGB - $freeGB,1)
$pct = [math]::Round(($usedGB/$totalGB)*100,1)
Write-Output "Total RAM: $totalGB GB"
Write-Output "Used RAM:  $usedGB GB ($pct%)"
Write-Output "Free RAM:  $freeGB GB"
Write-Output ""
Write-Output "Top processes by memory:"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, Id, @{N='MemGB';E={[math]::Round($_.WorkingSet64/1GB,2)}} | Format-Table -AutoSize
try {
    $gpu = Get-CimInstance Win32_VideoController | Select-Object Name, @{N='AdapterRAMGB';E={[math]::Round($_.AdapterRAM/1GB,1)}}
    $gpu | Format-Table -AutoSize
} catch {}
