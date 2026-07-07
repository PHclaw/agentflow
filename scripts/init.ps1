# AgentFlow 一键初始化脚本 (Windows)
# 用法: .\scripts\init.ps1

$Green = "`e[0;32m"
$Red = "`e[0;31m"
$Yellow = "`e[1;33m"
$NC = "`e[0m"

Write-Host "${Green}========================================${NC}"
Write-Host "${Green}  AgentFlow 初始化脚本 (Windows)${NC}"
Write-Host "${Green}========================================${NC}"
Write-Host ""

# 检查 Docker
try {
    docker --version | Out-Null
    Write-Host "${Green}✓${NC} Docker 已安装"
} catch {
    Write-Host "${Red}✗ Docker 未安装，请先安装 Docker Desktop${NC}"
    Write-Host "  下载: https://www.docker.com/products/docker-desktop/"
    exit 1
}

# 检查 Docker Compose
try {
    docker compose version | Out-Null
    Write-Host "${Green}✓${NC} Docker Compose 已安装"
} catch {
    Write-Host "${Red}✗ Docker Compose 未安装${NC}"
    exit 1
}
Write-Host ""

# 创建 .env
if (-not (Test-Path .env)) {
    if (-not (Test-Path .env.example)) {
        Write-Host "${Red}✗ .env.example 不存在${NC}"
        exit 1
    }
    Copy-Item .env.example .env
    Write-Host "${Green}✓${NC} 已创建 .env（请编辑填入 API Keys）"
} else {
    Write-Host "${Yellow}•${NC} .env 已存在，跳过创建"
}
Write-Host ""

# 提示用户编辑 .env
Write-Host "${Yellow}请确认 .env 配置：${NC}"
Write-Host "  必填项："
Write-Host "    - OPENAI_API_KEY 或 ANTHROPIC_API_KEY 或 DEEPSEEK_API_KEY"
Write-Host "    - JWT_SECRET_KEY（生产环境务必更换）"
Write-Host "    - DATABASE_URL（如使用外部数据库）"
Write-Host ""
Read-Host "按 Enter 继续，或 Ctrl+C 退出编辑 .env"
Write-Host ""

# 启动 Docker 服务
Write-Host "${Green}正在启动 Docker 服务...${NC}"
docker compose up -d
Write-Host "${Green}✓${NC} Docker 服务已启动"
Write-Host ""

# 等待数据库就绪
Write-Host "等待数据库就绪..."
Start-Sleep -Seconds 5

# 完成
Write-Host "${Green}========================================${NC}"
Write-Host "${Green}  🎉 AgentFlow 初始化完成！${NC}"
Write-Host "${Green}========================================${NC}"
Write-Host ""
Write-Host "  访问地址："
Write-Host "    - 前端:    http://localhost:3000"
Write-Host "    - 后端 API: http://localhost:8001"
Write-Host "    - API 文档: http://localhost:8001/docs"
Write-Host ""
Write-Host "  查看日志："
Write-Host "    docker compose logs -f [service]"
Write-Host ""
Write-Host "  停止服务："
Write-Host "    docker compose down"
Write-Host ""
Write-Host "${Yellow}提示：首次使用请注册账号，第一个注册的用户自动成为管理员${NC}"
