Write-Host ">>> 创建 Python 虚拟环境..." -ForegroundColor Cyan
python -m venv .venv

Write-Host ">>> 安装后端依赖..." -ForegroundColor Cyan
.\.venv\Scripts\pip install -r backend/requirements.txt

Write-Host ">>> 安装前端依赖..." -ForegroundColor Cyan
Set-Location frontend
npm install
Set-Location ..

Write-Host ">>> 安装根目录依赖 (concurrently)..." -ForegroundColor Cyan
npm install

Write-Host ""
Write-Host "✅ 初始化完成！" -ForegroundColor Green
Write-Host "接下来：" -ForegroundColor Yellow
Write-Host "  1. 复制 .env.example 为 .env 并填写 API 密钥" -ForegroundColor Yellow
Write-Host "  2. 运行 npm run dev 启动前后端" -ForegroundColor Yellow
