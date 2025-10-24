# 邮件服务使用指南

## 概述

项目现在集成了完整的SMTP邮件发送服务，支持多种邮件类型和自动凭据处理。

## 文件结构

```
backend/app/services/
├── email_service.py      # 核心邮件服务
├── mailu_client.py       # Mailu API客户端（已更新）
├── email_example.py      # 使用示例
└── README_EMAIL.md       # 本文档
```

## 环境配置

确保 `.env` 文件包含以下SMTP配置：

```bash
# 邮件服务器配置
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USE_TLS=false
SMTP_USERNAME=demo@example.com
SMTP_PASSWORD=your_password
```

## 基本使用

### 1. 导入邮件服务

```python
from backend.app.services.email_service import email_service
```

### 2. 发送基本邮件

```python
result = await email_service.send_email(
    from_email="sender@domain.com",
    to_email="recipient@domain.com",
    subject="邮件标题",
    body="邮件正文内容"
)
```

### 3. 发送HTML邮件

```python
html_content = """
<html>
<body>
    <h1>HTML邮件</h1>
    <p>支持<strong>富文本</strong>格式</p>
</body>
</html>
"""

result = await email_service.send_email(
    from_email="sender@domain.com",
    to_email="recipient@domain.com",
    subject="HTML邮件",
    body="纯文本版本",
    html_body=html_content
)
```

### 4. 发送验证码邮件

```python
result = await email_service.send_verification_email(
    to_email="user@domain.com",
    verification_code="123456"
)
```

### 5. 发送通知邮件

```python
result = await email_service.send_notification_email(
    to_email="admin@domain.com",
    title="系统通知",
    message="系统维护完成"
)
```

## 通过MailuClient使用

```python
from backend.app.services.mailu_client import MailuClient

async with MailuClient() as client:
    # 发送邮件
    result = await client.send_email_smtp(
        from_email="sender@domain.com",
        to_email="recipient@domain.com",
        subject="测试邮件",
        body="邮件内容"
    )

    # 发送验证码
    result = await client.send_verification_email(
        to_email="user@domain.com",
        verification_code="789012"
    )
```

## 高级功能

### 凭据自动处理

邮件服务会自动处理特殊字符（包括`@`符号）的编码：

- **ASCII字符**：直接使用
- **@符号**：在需要时自动转换为`%40`
- **其他特殊字符**：自动进行URL编码

### 端口自动检测

根据配置自动选择最佳连接方式：

- **端口465**：使用SSL连接
- **端口587**：使用STARTTLS
- **端口25**：普通SMTP（不推荐用于客户端）

## 错误处理

所有方法都会抛出异常，需要适当处理：

```python
try:
    result = await email_service.send_email(...)
    print("发送成功:", result)
except Exception as e:
    print("发送失败:", e)
    # 处理错误
```

## 运行示例

查看完整的使用示例：

```bash
cd backend/app/services
python email_example.py
```

## 集成到FastAPI

在FastAPI路由中使用：

```python
from fastapi import APIRouter, HTTPException
from backend.app.services.email_service import email_service

router = APIRouter()

@router.post("/send-verification")
async def send_verification(email: str, code: str):
    try:
        result = await email_service.send_verification_email(email, code)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 注意事项

1. **异步操作**：所有邮件发送都是异步的，确保在async函数中调用
2. **错误处理**：建议在生产环境中添加适当的错误处理和重试机制
3. **邮件内容**：支持中英文混合，自动UTF-8编码
4. **安全**：密码等敏感信息通过环境变量配置，不要硬编码在代码中

## 故障排除

### 常见问题

1. **认证失败**
   - 检查SMTP_USERNAME和SMTP_PASSWORD配置
   - 确认账户有发送权限

2. **连接失败**
   - 检查SMTP_SERVER和SMTP_PORT配置
   - 确认网络连接正常

3. **编码问题**
   - 邮件服务会自动处理字符编码
   - 如有特殊需求可以手动处理

### 调试模式

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## 更新日志

- **v1.0.0**：初始版本，支持基本SMTP发送
- **v1.1.0**：添加HTML邮件支持、验证码邮件模板
- **v1.2.0**：智能凭据处理、多种编码方式支持
- **v1.3.0**：自动端口检测、错误处理优化
