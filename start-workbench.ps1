param([string]$MySqlExe)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$runtime = Join-Path $PSScriptRoot '.runtime'
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath 'dist/index.html')) {
    throw '请先按 README 安装后端依赖，并运行 npm run build。'
}

function Test-LocalPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $client.Connect('127.0.0.1', $Port)
        return $true
    } catch [Net.Sockets.SocketException] {
        return $false
    } finally {
        $client.Dispose()
    }
}

$ini = Join-Path $runtime 'mysql.ini'
if (Test-Path -LiteralPath $ini) {
    $port = Select-String -LiteralPath $ini -Pattern '^\s*port\s*=\s*(\d+)\s*$' | Select-Object -First 1
    if ($port -and -not (Test-LocalPort ([int]$port.Matches[0].Groups[1].Value))) {
        if (-not $MySqlExe) {
            $basedir = Select-String -LiteralPath $ini -Pattern '^\s*basedir\s*=\s*(.+?)\s*$' | Select-Object -First 1
            if ($basedir) {
                $MySqlExe = Join-Path ($basedir.Matches[0].Groups[1].Value.Trim('"')) 'bin/mysqld.exe'
            }
        }
        if (-not $MySqlExe -or -not (Test-Path -LiteralPath $MySqlExe)) {
            throw '本项目的 MySQL 尚未启动。请启动 MySQL，或通过 -MySqlExe 提供 mysqld.exe 路径。'
        }
        Start-Process -FilePath $MySqlExe -ArgumentList ('--defaults-file="' + $ini + '"') -WindowStyle Hidden
    }
}

if (-not (Test-LocalPort 8000)) {
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    Start-Process -FilePath $python -ArgumentList '-m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8000' `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtime 'fastapi.stdout.log') `
        -RedirectStandardError (Join-Path $runtime 'fastapi.stderr.log')
}

$deadline = [DateTime]::UtcNow.AddSeconds(25)
do {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2
        if ($health.status -eq 'ok' -and $health.database -in 'mysql', 'sqlite') {
            Write-Output '小学科学 AI 教师工作台已就绪：http://127.0.0.1:8000/'
            return
        }
    } catch {
        Start-Sleep -Milliseconds 400
    }
} while ([DateTime]::UtcNow -lt $deadline)
throw '工作台健康检查未通过，请检查 MySQL 和 .runtime/fastapi.stderr.log。'
