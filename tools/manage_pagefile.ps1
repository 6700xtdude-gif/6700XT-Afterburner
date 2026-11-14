# manage_pagefile.ps1 - Manage Windows Pagefile Settings for Strata / 6700XT
param(
    [ValidateSet("default", "system", "64gb", "96gb", "32gb", "custom", "status")]
    [string]$Mode = "status",
    [int]$MinGB = 0,
    [int]$MaxGB = 0
)

# 1. Self-Elevation to Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin -and $Mode -ne "status") {
    Write-Host "[*] Administrator privileges required to modify Windows pagefile settings." -ForegroundColor Yellow
    Write-Host "[*] Triggering Windows UAC elevation..." -ForegroundColor Cyan
    
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode `"$Mode`""
    if ($MinGB -gt 0) { $argList += " -MinGB $MinGB" }
    if ($MaxGB -gt 0) { $argList += " -MaxGB $MaxGB" }

    try {
        $process = Start-Process powershell.exe -Verb RunAs -ArgumentList $argList -PassThru -Wait
        exit $process.ExitCode
    } catch {
        Write-Error "UAC Elevation cancelled or failed: $_"
        exit 1
    }
}

# 2. Status Display
function Show-Status {
    $cs = Get-CimInstance Win32_ComputerSystem
    $pf = Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue

    Write-Host "`n=======================================================" -ForegroundColor Cyan
    Write-Host " Windows Virtual Memory / Pagefile Telemetry" -ForegroundColor Yellow
    Write-Host "=======================================================" -ForegroundColor Cyan
    Write-Host " Automatic Managed (Let Windows manage):" ($cs.AutomaticManagedPagefile) -ForegroundColor White
    if ($pf) {
        foreach ($p in $pf) {
            $minGB = [math]::Round($p.InitialSize / 1024, 2)
            $maxGB = [math]::Round($p.MaximumSize / 1024, 2)
            Write-Host " Pagefile File:" ($p.Name) -ForegroundColor Green
            Write-Host "   Initial Size (Min):" ("$($p.InitialSize) MB ($minGB GB)") -ForegroundColor White
            Write-Host "   Maximum Size (Max):" ("$($p.MaximumSize) MB ($maxGB GB)") -ForegroundColor White
        }
    } else {
        Write-Host " Pagefile: Managed dynamically by Windows kernel." -ForegroundColor Green
    }
    Write-Host "=======================================================`n" -ForegroundColor Cyan
}

if ($Mode -eq "status") {
    Show-Status
    exit 0
}

# 3. Apply Configuration
Write-Host "[*] Configuring Windows Pagefile: Mode = $Mode..." -ForegroundColor Cyan

if ($Mode -eq "default" -or $Mode -eq "system") {
    # Set to System Managed
    Set-CimInstance -Query "Select * from Win32_ComputerSystem" -Property @{AutomaticManagedPagefile=$True} -ErrorAction Stop
    
    # Remove explicit PageFileSetting entries so Windows fully owns pagefile.sys
    $existing = Get-CimInstance Win32_PageFileSetting -ErrorAction SilentlyContinue
    if ($existing) {
        $existing | Remove-CimInstance -ErrorAction SilentlyContinue
    }
    Write-Host "[+] SUCCESS: Pagefile set to 'System-Managed' (Let Windows manage)." -ForegroundColor Green
} else {
    # Manual Configuration
    $initialMB = 0
    $maxMB = 0

    if ($Mode -eq "64gb") {
        $initialMB = 98304   # 96 GB (1.5x)
        $maxMB     = 196608  # 192 GB (3.0x)
    } elseif ($Mode -eq "96gb") {
        $initialMB = 147456  # 144 GB (1.5x of 96GB)
        $maxMB     = 294912  # 288 GB (3.0x of 96GB)
    } elseif ($Mode -eq "32gb") {
        $initialMB = 32768   # 32 GB (1.0x)
        $maxMB     = 98304   # 96 GB (3.0x)
    } elseif ($Mode -eq "custom") {
        if ($MinGB -le 0 -or $MaxGB -le 0) {
            Write-Error "Custom mode requires -MinGB and -MaxGB parameters."
            exit 1
        }
        $initialMB = $MinGB * 1024
        $maxMB     = $MaxGB * 1024
    }

    # Disable automatic management
    Set-CimInstance -Query "Select * from Win32_ComputerSystem" -Property @{AutomaticManagedPagefile=$False} -ErrorAction Stop

    # Set or create PageFileSetting
    $existing = Get-CimInstance Win32_PageFileSetting | Where-Object {$_.Name -like "C:*"}
    if ($existing) {
        Set-CimInstance -InputObject $existing -Property @{InitialSize=$initialMB; MaximumSize=$maxMB} -ErrorAction Stop
    } else {
        New-CimInstance -ClassName Win32_PageFileSetting -Property @{Name="C:\pagefile.sys"; InitialSize=$initialMB; MaximumSize=$maxMB} -ErrorAction Stop
    }
    Write-Host "[+] SUCCESS: Pagefile set to Min: $initialMB MB ($([math]::Round($initialMB/1024,1)) GB), Max: $maxMB MB ($([math]::Round($maxMB/1024,1)) GB)." -ForegroundColor Green
}

Show-Status

Write-Host "=======================================================" -ForegroundColor Magenta
Write-Host " [!] REBOOT REQUIRED: Windows requires a system restart" -ForegroundColor Yellow
Write-Host "     for the memory manager to physically apply this pagefile change." -ForegroundColor Yellow
Write-Host "=======================================================" -ForegroundColor Magenta
