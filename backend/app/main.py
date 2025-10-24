"""FastAPI主应用"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
import logging
import os
from datetime import datetime

from backend.app.models.database import SessionLocal, TempEmail, VerificationCode, SystemStats
from backend.app.services.mailu_client import MailuClient
from backend.app.services.redis_cache import cache
from backend.app.utils.helpers import (
    generate_random_email, generate_secure_password,
    validate_email, extract_verification_codes,
    calculate_expiry_date, format_datetime, get_time_remaining
)
from backend.app.celery.tasks import create_temp_email_task, update_stats_cache

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Mailu验证码平台",
    description="基于Mailu的高性能验证码接收平台",
    version="1.0.0"
)

# 配置模板引擎
templates = Jinja2Templates(directory="/app/frontend/templates")

# 配置静态文件
app.mount("/frontend/static", StaticFiles(directory="/app/frontend/static"), name="frontend_static")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class CreateEmailRequest(BaseModel):
    domain: Optional[str] = None
    expire_hours: Optional[int] = 24

class SendEmailRequest(BaseModel):
    from_email: str
    to_email: str
    subject: str
    body: str
    html_body: Optional[str] = None

class EmailResponse(BaseModel):
    email: str
    password: str
    expires_at: str
    time_remaining: str
    created_at: str

class CodeResponse(BaseModel):
    email: str
    code: Optional[str]
    found: bool
    last_checked: Optional[str]
    time_remaining: str

class StatsResponse(BaseModel):
    total_emails: int
    active_emails: int
    total_codes: int
    server_status: str
    last_sync: Optional[Dict] = None

# 依赖注入
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API路由
@app.get("/")
async def root(request: Request):
    """主页仪表板"""
    return templates.TemplateResponse("dashboard.html", {"request": request})
@app.post("/api/emails", response_model=EmailResponse)
async def create_email(request: CreateEmailRequest, background_tasks: BackgroundTasks):
    """创建临时邮箱"""
    try:
        # 如果没有指定域名，使用默认域名
        domain = request.domain or os.getenv("DEFAULT_DOMAIN", "example.com")

        # 生成随机邮箱
        email = generate_random_email(domain)
        password = generate_secure_password()

        # 异步创建邮箱
        background_tasks.add_task(
            create_temp_email_task.delay,
            email, password, domain, request.expire_hours
        )

        expires_at = calculate_expiry_date(request.expire_hours)

        return EmailResponse(
            email=email,
            password=password,
            expires_at=format_datetime(expires_at),
            time_remaining=get_time_remaining(expires_at),
            created_at=format_datetime(datetime.utcnow())
        )

    except Exception as e:
        logger.error(f"创建邮箱失败: {str(e)}")
        raise HTTPException(status_code=500, detail="创建邮箱失败")

@app.get("/api/emails/{email}/code", response_model=CodeResponse)
async def get_verification_code(email: str):
    """获取邮箱的验证码"""
    try:
        # 验证邮箱格式
        if not validate_email(email):
            raise HTTPException(status_code=400, detail="无效的邮箱格式")

        # 从缓存获取验证码
        code = await cache.get_verification_code(email)

        # 从数据库获取邮箱信息
        db = SessionLocal()
        try:
            temp_email = db.query(TempEmail).filter(TempEmail.email == email).first()
            if not temp_email:
                raise HTTPException(status_code=404, detail="邮箱不存在")

            if temp_email.is_active and not temp_email.expires_at < datetime.utcnow():
                time_remaining = get_time_remaining(temp_email.expires_at)
            else:
                time_remaining = "已过期"

        finally:
            db.close()

        return CodeResponse(
            email=email,
            code=code,
            found=code is not None,
            last_checked=format_datetime(datetime.utcnow()),
            time_remaining=time_remaining
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取验证码失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取验证码失败")

@app.get("/api/emails/{email}/verifications")
async def get_email_verifications(email: str):
    """获取邮箱的所有验证码记录"""
    try:
        # 验证邮箱格式
        if not validate_email(email):
            raise HTTPException(status_code=400, detail="无效的邮箱格式")

        db = SessionLocal()
        try:
            # 获取临时邮箱记录
            temp_email = db.query(TempEmail).filter(TempEmail.email == email).first()
            if not temp_email:
                raise HTTPException(status_code=404, detail="邮箱不存在")

            # 获取所有验证码记录，按时间倒序
            verifications = db.query(VerificationCode).filter(
                VerificationCode.temp_email_id == temp_email.id
            ).order_by(VerificationCode.received_at.desc()).all()

            # 格式化结果
            result = {
                "email": email,
                "verifications": [
                    {
                        "id": v.id,
                        "code": v.code,
                        "subject": v.subject,
                        "sender": v.sender,
                        "content": v.content[:200] + "..." if v.content and len(v.content) > 200 else v.content,
                        "received_at": v.received_at.isoformat(),
                        "is_read": v.is_read
                    } for v in verifications
                ],
                "last_updated": datetime.utcnow().isoformat()
            }

            return [result]

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮箱验证码记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取验证码记录失败")

@app.get("/api/verifications")
async def get_all_verifications():
    """获取所有邮箱的验证码记录"""
    try:
        db = SessionLocal()
        try:
            # 获取所有活跃的临时邮箱
            temp_emails = db.query(TempEmail).filter(
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).all()

            results = []
            for temp_email in temp_emails:
                # 获取每个邮箱的验证码记录
                verifications = db.query(VerificationCode).filter(
                    VerificationCode.temp_email_id == temp_email.id
                ).order_by(VerificationCode.received_at.desc()).limit(5).all()  # 每个邮箱最多显示5个最新验证码

                if verifications:
                    result = {
                        "email": temp_email.email,
                        "verifications": [
                            {
                                "id": v.id,
                                "code": v.code,
                                "subject": v.subject,
                                "sender": v.sender,
                                "content": v.content[:200] + "..." if v.content and len(v.content) > 200 else v.content,
                                "received_at": v.received_at.isoformat(),
                                "is_read": v.is_read
                            } for v in verifications
                        ],
                        "last_updated": datetime.utcnow().isoformat()
                    }
                    results.append(result)

            return results

        finally:
            db.close()

    except Exception as e:
        logger.error(f"获取所有验证码记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取验证码记录失败")

@app.put("/api/emails/{email}/verifications/{verification_id}/read")
async def mark_verification_as_read(email: str, verification_id: int):
    """标记验证码为已读"""
    try:
        # 验证邮箱格式
        if not validate_email(email):
            raise HTTPException(status_code=400, detail="无效的邮箱格式")

        db = SessionLocal()
        try:
            # 获取临时邮箱记录
            temp_email = db.query(TempEmail).filter(TempEmail.email == email).first()
            if not temp_email:
                raise HTTPException(status_code=404, detail="邮箱不存在")

            # 获取验证码记录
            verification = db.query(VerificationCode).filter(
                VerificationCode.id == verification_id,
                VerificationCode.temp_email_id == temp_email.id
            ).first()

            if not verification:
                raise HTTPException(status_code=404, detail="验证码记录不存在")

            # 标记为已读
            verification.is_read = True
            db.commit()

            return {"message": "验证码已标记为已读", "email": email, "verification_id": verification_id}

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"标记验证码已读失败: {str(e)}")
        raise HTTPException(status_code=500, detail="标记已读失败")

@app.post("/api/send-email")
async def send_email(request: SendEmailRequest):
    """发送邮件"""
    try:
        # 验证发件人邮箱
        # 对于动态SMTP认证，我们需要更灵活的验证逻辑
        db = SessionLocal()
        try:
            # 首先检查是否是临时邮箱
            temp_email = db.query(TempEmail).filter(
                TempEmail.email == request.from_email,
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).first()

            if temp_email:
                logger.info(f"使用临时邮箱: {request.from_email}")
            else:
                # 如果不是临时邮箱，验证邮箱格式和域名
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, request.from_email):
                    raise HTTPException(status_code=400, detail="邮箱格式不正确")

                # 检查域名是否在允许列表中
                domain = request.from_email.split('@')[1]
                allowed_domains = os.getenv("ALLOWED_DOMAINS", "zhangxuemin.work").split(',')
                if domain not in [d.strip() for d in allowed_domains]:
                    raise HTTPException(status_code=400, detail=f"域名 {domain} 不被允许")

                logger.info(f"使用动态认证邮箱: {request.from_email}")

        finally:
            db.close()

        # 发送邮件（使用SMTP）
        async with MailuClient() as client:
            try:
                # 记录原始发件人地址
                original_from_email = request.from_email
                logger.info(f"API请求发件人: {original_from_email}, 收件人: {request.to_email}")

                result = await client.send_email_smtp(
                    from_email=request.from_email,
                    to_email=request.to_email,
                    subject=request.subject,
                    body=request.body
                )

                # 如果实际使用的发件人地址与请求的不同，在响应中说明
                if result.get('from') != original_from_email:
                    logger.info(f"发件人地址已调整: {original_from_email} -> {result.get('from')}")
                    result['original_from'] = original_from_email
                    result['adjusted_from'] = result.get('from')

                logger.info(f"邮件发送成功: {result.get('from')} -> {request.to_email}")
                return {
                    "message": "邮件发送成功",
                    "from": result.get('from'),  # 使用实际发送的发件人地址
                    "to": result.get('to'),
                    "subject": request.subject,
                    "result": result
                }

            except ValueError as e:
                logger.error(f"发送邮件请求参数错误: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"发送邮件失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"发送邮件失败: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"发送邮件接口错误: {str(e)}")
        raise HTTPException(status_code=500, detail="发送邮件失败")

@app.get("/api/stats", response_model=StatsResponse)
async def get_system_stats():
    """获取系统统计信息"""
    try:
        # 尝试从缓存获取
        stats = await cache.get_stats()
        if stats:
            # 确保缓存中的数据包含server_status
            if "server_status" not in stats:
                stats["server_status"] = "正常"
            # 从stats中提取last_sync信息
            last_sync = stats.pop("last_sync", None)
            return StatsResponse(**stats, last_sync=last_sync)

        # 从数据库获取
        db = SessionLocal()
        try:
            total_emails = db.query(TempEmail).count()
            active_emails = db.query(TempEmail).filter(
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).count()
            total_codes = db.query(VerificationCode).count()

            # 执行Mailu数据同步（使用同步方式避免事件循环冲突）
            try:
                import requests
                import os

                api_url = os.getenv("API_URL", "https://mail.zhangxuemin.work/api/v1/")
                token = os.getenv("API_TOKEN", "f80dae1387106ff8995d6049e42934c3")
                headers = {"Authorization": f"Bearer {token}"}

                response = requests.get(f"{api_url}/user", headers=headers, timeout=30.0)
                response.raise_for_status()
                mailu_users = response.json()
                mailu_users_count = len(mailu_users)

                sync_result = {
                    "sync_status": "success",
                    "local_emails": total_emails,
                    "mailu_users": mailu_users_count,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "同步完成"
                }

            except Exception as e:
                logger.warning(f"同步Mailu数据失败: {str(e)}")
                sync_result = {
                    "sync_status": "error",
                    "local_emails": total_emails,
                    "mailu_users": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e)
                }

            stats = {
                "total_emails": total_emails,
                "active_emails": active_emails,
                "total_codes": total_codes,
                "server_status": "正常"
            }

            # 缓存统计数据（包含同步信息）
            stats_with_sync = {**stats, "last_sync": sync_result}
            await cache.cache_stats(stats_with_sync)

            return StatsResponse(**stats, last_sync=sync_result)

        finally:
            db.close()

    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return StatsResponse(
            total_emails=0,
            active_emails=0,
            total_codes=0,
            server_status="异常"
        )

@app.delete("/api/emails/{email}")
async def delete_email(email: str):
    """删除临时邮箱"""
    try:
        # 验证邮箱格式
        if not validate_email(email):
            raise HTTPException(status_code=400, detail="无效的邮箱格式")

        db = SessionLocal()
        try:
            temp_email = db.query(TempEmail).filter(TempEmail.email == email).first()
            if not temp_email:
                raise HTTPException(status_code=404, detail="邮箱不存在")

            # 标记为非活跃
            temp_email.is_active = False
            db.commit()

            # 清理缓存
            await cache.delete_temp_email(email)
            await cache.delete_verification_code(email)
            await cache.clear_email_queue(email)

            # 删除Mailu用户
            async with MailuClient() as client:
                try:
                    await client.delete_user(email)
                except Exception as e:
                    logger.warning(f"删除Mailu用户失败: {str(e)}")

            return {"message": "邮箱已删除", "email": email}

        finally:
            db.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除邮箱失败: {str(e)}")
        raise HTTPException(status_code=500, detail="删除邮箱失败")

@app.get("/api/emails", response_model=List[Dict])
async def list_emails():
    """列出所有活跃邮箱"""
    try:
        db = SessionLocal()
        try:
            emails = db.query(TempEmail).filter(
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).all()

            result = []
            for email in emails:
                result.append({
                    "email": email.email,
                    "domain": email.domain,
                    "created_at": format_datetime(email.created_at),
                    "expires_at": format_datetime(email.expires_at),
                    "time_remaining": get_time_remaining(email.expires_at)
                })

            return result

        finally:
            db.close()

    except Exception as e:
        logger.error(f"获取邮箱列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail="获取邮箱列表失败")

# 前端页面路由
@app.get("/verification")
async def verification_page(request: Request):
    """验证码查看页面"""
    return templates.TemplateResponse("verification.html", {"request": request})

@app.get("/emails")
async def emails_page(request: Request):
    """邮箱管理页面"""
    return templates.TemplateResponse("emails.html", {"request": request})

@app.get("/send")
async def send_page(request: Request):
    """发送邮件页面"""
    return templates.TemplateResponse("send.html", {"request": request, "current_page": "send"})

@app.get("/test")
async def test_page(request: Request):
    """测试页面"""
    return templates.TemplateResponse("test.html", {"request": request})

@app.get("/stats")
async def stats_page(request: Request):
    """系统统计页面"""
    return templates.TemplateResponse("stats.html", {"request": request})

# 健康检查
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("Mailu验证码平台启动中...")

    # 创建数据库表
    from backend.app.models.database import create_tables
    try:
        create_tables()
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"数据库表创建失败: {str(e)}")

    # 初始化缓存连接
    await cache.connect()

    logger.info("应用启动完成")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("正在关闭应用...")

    # 关闭缓存连接
    await cache.close()

    logger.info("应用已关闭")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
