-- MySQL数据库初始化脚本
-- 为mailu_codes数据库创建用户和权限

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS mailu_codes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE mailu_codes;

-- 创建用户（如果不存在）
CREATE USER IF NOT EXISTS 'mailu_user'@'%' IDENTIFIED BY 'mailu_password';

-- 授予权限
GRANT ALL PRIVILEGES ON mailu_codes.* TO 'mailu_user'@'%';

-- 刷新权限
FLUSH PRIVILEGES;

-- 创建初始表结构（SQLAlchemy会处理，但这里可以添加一些基础配置）
-- 注意：实际的表创建由SQLAlchemy处理，这里只是为了完整性
