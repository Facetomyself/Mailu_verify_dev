#!/bin/bash

# Mailu验证码平台启动脚本

echo "🚀 启动Mailu验证码平台..."

# 检查Docker和Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 检查环境文件
if [ ! -f ".env" ]; then
    echo "📝 复制环境配置文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件配置你的Mailu服务器信息"
    echo "   API_URL 和 API_TOKEN 是必需的"
    exit 1
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p logs
mkdir -p nginx/ssl

# 停止可能存在的旧容器
echo "🛑 停止旧容器..."
docker-compose down

# 构建和启动服务
echo "🏗️  构建和启动服务..."
docker-compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
docker-compose ps

# 显示访问信息
echo ""
echo "🎉 服务启动完成！"
echo "📱 主界面: http://localhost:30001"
echo "📚 API文档: http://localhost:30001/docs"
echo "💚 健康检查: http://localhost:30001/health"
echo ""
echo "📊 查看日志: docker-compose logs -f"
echo "🛑 停止服务: docker-compose down"
echo ""
echo "⚠️  记得配置你的Mailu服务器信息在 .env 文件中"
