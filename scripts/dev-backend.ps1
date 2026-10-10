# AgentFlow 后端本地启动脚本 (Windows / SQLite 轻量模式)
#
# 无需 Docker、PostgreSQL、Redis，使用 SQLite 文件库直接启动后端。
#
# 用法:
#   .\scripts\dev-backend.ps1                 # 启动在 8001
#   .\scripts\dev-backend.ps1 -Port 8002      # 指定端口
#   .\scripts\dev-backend.ps1 -Reinstall      # 强制重装依赖
#   .\scripts\dev-backend.ps1 -SkipServe      # 只准备环境，不启动服务

param(
    [int]$Port = 8001,
    [switch]$Reinstall,
    [switch]$SkipServe
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
$ReqFile = Join-Path $BackendDir "requirements-lite.txt"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgentFlow 后端启动 (SQLite 轻量模式)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---------------------------------------------------------------- 1. Python
Write-Step "检查 Python (>= 3.11)"

# 注意：Windows 上 `python` 可能解析到 WindowsApps 的存根（无输出），
# 因此逐个候选命令实测版本号，取第一个真正可用的。
$PythonCmd = $null
$pyVersion = $null
foreach ($cand in @("python", "python3", "py")) {
    if (-not (Get-Command $cand -ErrorAction SilentlyContinue)) { continue }
    $out = & $cand -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($out -and $out -match "^\d+\.\d+$") {
        $PythonCmd = $cand
        $pyVersion = $out
        break
    }
}
if (-not $PythonCmd) {
    Write-Err "未找到可用的 python，请先安装 Python 3.11+"
    exit 1
}
$pyMajor, $pyMinor = $pyVersion.Split(".") | ForEach-Object { [int]$_ }
if ($pyMajor -lt 3 -or ($pyMajor -eq 3 -and $pyMinor -lt 11)) {
    Write-Err "Python 版本过低: $pyVersion（需要 3.11+）"
    exit 1
}
Write-Ok "$PythonCmd ($pyVersion)"

# ---------------------------------------------------------------- 2. venv
Write-Step "准备虚拟环境"

if ((Test-Path $VenvPy) -and -not $Reinstall) {
    Write-Ok "已存在: $VenvDir"
} else {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        Write-Host "    使用 uv 创建虚拟环境..."
        & uv venv $VenvDir --python "$pyMajor.$pyMinor"
    } else {
        Write-Host "    使用 venv 创建虚拟环境..."
        & $PythonCmd -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0) { Write-Err "虚拟环境创建失败"; exit 1 }
    Write-Ok "已创建: $VenvDir"
}

# ---------------------------------------------------------------- 3. deps
Write-Step "安装依赖 (requirements-lite.txt)"

$needInstall = $Reinstall -or -not (Test-Path (Join-Path $VenvDir "Lib\site-packages\fastapi"))
if (-not $needInstall) {
    Write-Ok "依赖已安装，跳过（如需重装请加 -Reinstall）"
} else {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & uv pip install --python $VenvPy -r $ReqFile
    } else {
        & $VenvPy -m pip install -r $ReqFile
    }
    if ($LASTEXITCODE -ne 0) { Write-Err "依赖安装失败"; exit 1 }
    Write-Ok "依赖安装完成"
}

# ---------------------------------------------------------------- 4. .env
Write-Step "检查 .env"

$envFile = Join-Path $BackendDir ".env"
if (-not (Test-Path $envFile)) {
    $example = Join-Path $BackendDir ".env.example"
    if (Test-Path $example) {
        Copy-Item $example $envFile
        Write-Ok "已从 .env.example 创建 .env（默认 DATABASE_URL 为 SQLite）"
    } else {
        Write-Host "    无 .env，使用默认配置（SQLite）" -ForegroundColor Yellow
    }
} else {
    Write-Ok ".env 已存在"
}

if ($SkipServe) {
    Write-Host "`n环境准备完成（已跳过启动）。" -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------- 5. serve
Write-Step "启动 uvicorn (http://127.0.0.1:$Port)"

Write-Host ""
Write-Host "  API 文档: http://127.0.0.1:$Port/docs" -ForegroundColor Yellow
Write-Host "  按 Ctrl+C 停止" -ForegroundColor Yellow
Write-Host ""

Set-Location $BackendDir
& $VenvPy -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
