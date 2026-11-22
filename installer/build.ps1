$ErrorActionPreference = 'Stop'

if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    $goBin = 'C:\Program Files\Go\bin'
    if (Test-Path (Join-Path $goBin 'go.exe')) {
        $env:PATH = "$goBin;$env:PATH"
    } else {
        throw 'Go toolchain not found on PATH or at C:\Program Files\Go\bin'
    }
}

Push-Location $PSScriptRoot
try {
    Write-Host "Using: $(go version)" -ForegroundColor Cyan

    Write-Host "`n[1/4] Running go vet ./..." -ForegroundColor Yellow
    go vet ./...
    if ($LASTEXITCODE -ne 0) { throw "go vet failed (exit $LASTEXITCODE)" }

    Write-Host "`n[2/4] Running go test -v ./..." -ForegroundColor Yellow
    go test -v ./...
    if ($LASTEXITCODE -ne 0) { throw "go test failed (exit $LASTEXITCODE)" }

    $distDir = Join-Path $PSScriptRoot 'dist'
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null

    $winOut = Join-Path $distDir 'rx6700xt-installer-windows-amd64.exe'
    $linOut = Join-Path $distDir 'rx6700xt-installer-linux-amd64'

    Write-Host "`n[3/4] Cross-compiling windows/amd64 and linux/amd64 (CGO_ENABLED=0)..." -ForegroundColor Yellow
    $env:CGO_ENABLED = '0'
    $env:GOOS = 'windows'
    $env:GOARCH = 'amd64'
    go build -trimpath -ldflags='-s -w' -o $winOut .
    if ($LASTEXITCODE -ne 0) { throw "windows build failed (exit $LASTEXITCODE)" }

    $env:GOOS = 'linux'
    $env:GOARCH = 'amd64'
    go build -trimpath -ldflags='-s -w' -o $linOut .
    if ($LASTEXITCODE -ne 0) { throw "linux build failed (exit $LASTEXITCODE)" }

    Remove-Item Env:GOOS -ErrorAction SilentlyContinue
    Remove-Item Env:GOARCH -ErrorAction SilentlyContinue

    # Verify PE (MZ) and ELF (\x7fELF) magic bytes
    $winMagic = [System.IO.File]::ReadAllBytes($winOut)[0..1]
    if ($winMagic[0] -ne 0x4D -or $winMagic[1] -ne 0x5A) {
        throw "Unexpected header bytes in $winOut (expected MZ)"
    }
    $linMagic = [System.IO.File]::ReadAllBytes($linOut)[0..3]
    if ($linMagic[0] -ne 0x7F -or $linMagic[1] -ne 0x45 -or $linMagic[2] -ne 0x4C -or $linMagic[3] -ne 0x46) {
        throw "Unexpected header bytes in $linOut (expected ELF)"
    }

    Write-Host "`n[4/4] Writing SHA256SUMS.txt..." -ForegroundColor Yellow
    $sums = @()
    foreach ($f in @($winOut, $linOut)) {
        $item = Get-Item -LiteralPath $f
        $h = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant()
        $sums += "$h  $($item.Name)"
        Write-Host ("  {0,-40} | {1,10} bytes | {2}" -f $item.Name, $item.Length, $h) -ForegroundColor Green
    }
    $sumsPath = Join-Path $distDir 'SHA256SUMS.txt'
    [System.IO.File]::WriteAllText($sumsPath, ($sums -join "`n") + "`n", (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "`nBuild complete: $distDir" -ForegroundColor Cyan
} finally {
    Pop-Location
}
