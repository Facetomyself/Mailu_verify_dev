"""Celery异步任务"""

import logging
import re
import os
from datetime import datetime, timedelta
from typing import List, Dict

from backend.app.celery import celery_app
from backend.app.services.mailu_client import MailuClient
from backend.app.services.redis_cache import cache
from backend.app.models.database import SessionLocal, TempEmail, VerificationCode

logger = logging.getLogger(__name__)

# 验证码提取正则表达式
CODE_PATTERNS = [
    r'\b\d{4,8}\b',  # 4-8位数字
    r'验证码[：:]\s*(\d{4,8})',  # 中文验证码
    r'verification code[：:]\s*(\d{4,8})',  # 英文验证码
    r'code[：:]\s*(\d{4,8})',  # 简单code
    r'OTP[：:]\s*(\d{4,8})',  # OTP
    r'PIN[：:]\s*(\d{4,8})',  # PIN
]

@celery_app.task(bind=True)
def check_emails(self):
    """检查所有活跃临时邮箱的新邮件"""
    try:
        logger.info("开始检查邮件任务")

        # 获取所有活跃的临时邮箱
        db = SessionLocal()
        try:
            active_emails = db.query(TempEmail).filter(
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).all()

            for temp_email in active_emails:
                # 检查邮件任务
                check_single_email.delay(temp_email.email)

        finally:
            db.close()

        logger.info(f"邮件检查任务完成，处理了 {len(active_emails)} 个邮箱")
        return {"processed": len(active_emails)}

    except Exception as e:
        logger.error(f"邮件检查任务失败: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)

@celery_app.task(bind=True)
def check_single_email(self, email_addr: str):
    """检查单个邮箱的邮件"""
    try:
        logger.info(f"检查邮箱: {email_addr}")

        # 从数据库获取邮箱信息
        db = SessionLocal()
        try:
            temp_email = db.query(TempEmail).filter(TempEmail.email == email_addr).first()
            if not temp_email:
                logger.warning(f"邮箱不存在: {email_addr}")
                return {"email": email_addr, "checked": False, "error": "邮箱不存在"}

            # 检查邮件
            emails_data = check_imap_emails(email_addr, temp_email.password)

            for email_data in emails_data:
                # 提取验证码
                extract_codes.delay(email_addr, email_data)

            return {"email": email_addr, "checked": True, "emails_found": len(emails_data)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"检查邮箱 {email_addr} 失败: {str(e)}")
        raise self.retry(countdown=30, max_retries=5)

@celery_app.task(bind=True)
def extract_codes(self, email_addr: str, email_data: Dict):
    """从邮件中提取验证码"""
    try:
        subject = email_data.get('subject', '')
        content = email_data.get('content', '')
        sender = email_data.get('sender', '')

        # 合并主题和内容进行匹配
        text_to_search = f"{subject} {content}"

        extracted_codes = []
        for pattern in CODE_PATTERNS:
            matches = re.findall(pattern, text_to_search, re.IGNORECASE)
            extracted_codes.extend(matches)

        # 去重并验证
        unique_codes = list(set(extracted_codes))
        valid_codes = [code for code in unique_codes if 4 <= len(code) <= 8 and code.isdigit()]

        if valid_codes:
            # 选择最长的验证码
            latest_code = max(valid_codes, key=len)

            # 保存到数据库
            db = SessionLocal()
            try:
                temp_email = db.query(TempEmail).filter(TempEmail.email == email_addr).first()
                if temp_email:
                    verification_code = VerificationCode(
                        temp_email_id=temp_email.id,
                        code=latest_code,
                        sender=sender,
                        subject=subject,
                        content=content
                    )
                    db.add(verification_code)
                    db.commit()

                    # 同时更新Redis缓存（同步方式）
                    import redis
                    import os

                    try:
                        redis_host = os.getenv("REDIS_HOST", "redis")
                        redis_port = int(os.getenv("REDIS_PORT", "6379"))
                        redis_password = os.getenv("REDIS_PASSWORD")

                        # 创建同步Redis连接
                        redis_client = redis.Redis(
                            host=redis_host,
                            port=redis_port,
                            password=redis_password,
                            decode_responses=True
                        )

                        # 缓存验证码（1小时过期）
                        key = f"code:{email_addr}"
                        redis_client.setex(key, 3600, latest_code)
                        logger.info(f"同步缓存验证码: {email_addr} -> {latest_code}")
                    except Exception as cache_error:
                        logger.warning(f"Redis缓存更新失败: {cache_error}")
                        # 不影响主要功能，只是缓存失败

                    logger.info(f"提取验证码成功: {email_addr} -> {latest_code}")
            finally:
                db.close()

        return {
            "email": email_addr,
            "codes_found": len(valid_codes),
            "latest_code": valid_codes[0] if valid_codes else None
        }

    except Exception as e:
        logger.error(f"提取验证码失败 {email_addr}: {str(e)}")
        raise self.retry(countdown=10, max_retries=3)

@celery_app.task(bind=True)
def cleanup_expired(self):
    """清理过期数据"""
    try:
        logger.info("开始清理过期数据")

        db = SessionLocal()
        try:
            # 清理过期邮箱
            expired_emails = db.query(TempEmail).filter(
                TempEmail.expires_at < datetime.utcnow()
            ).all()

            expired_count = 0
            for email in expired_emails:
                # 删除数据库记录
                db.delete(email)
                expired_count += 1

            db.commit()
            logger.info(f"清理了 {expired_count} 个过期邮箱")

            # 更新统计数据
            update_stats_cache(db)

        finally:
            db.close()

        return {"expired_cleaned": expired_count}

    except Exception as e:
        logger.error(f"清理任务失败: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)

@celery_app.task(bind=True)
def create_temp_email_task(self, email: str, password: str, domain: str, expire_hours: int = 24):
    """创建临时邮箱任务"""
    try:
        logger.info(f"创建临时邮箱: {email}")

        # 创建新的异步函数来处理异步操作
        async def create_email_async():
            async with MailuClient() as client:
                return await client.create_user(
                    email,
                    password,
                    comment=f"临时邮箱 - {datetime.utcnow().isoformat()}",
                    enable_imap=True,
                    enable_pop=True
                )

        # 在新的事件循环中运行异步代码
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            user_data = loop.run_until_complete(create_email_async())
        finally:
            loop.close()

        # 保存到数据库
        db = SessionLocal()
        try:
            expires_at = datetime.utcnow() + timedelta(hours=expire_hours)
            temp_email = TempEmail(
                email=email,
                domain=domain,
                password=password,
                expires_at=expires_at
            )
            db.add(temp_email)
            db.commit()

            logger.info(f"临时邮箱创建成功: {email}")
            return {"email": email, "created": True}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"创建临时邮箱失败 {email}: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)

@celery_app.task(bind=True)
def sync_mailu_data(self):
    """定期同步Mailu数据任务"""
    try:
        logger.info("开始定期同步Mailu数据任务")

        # 使用新的事件循环来运行异步代码
        import asyncio

        # 创建新的异步函数来处理异步操作
        async def async_sync():
            db = SessionLocal()
            try:
                # 执行数据同步
                sync_result = await sync_with_mailu_async(db)

                # 更新统计缓存
                await update_stats_cache_async(db)

                return sync_result

            finally:
                db.close()

        # 在新的事件循环中运行异步代码
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_sync())
            logger.info(f"Mailu数据同步任务完成: {result}")
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Mailu数据同步任务失败: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)  # 5分钟后重试


@celery_app.task(bind=True)
def update_stats_cache(self, db=None):
    """更新统计数据缓存"""
    try:
        if db is None:
            db = SessionLocal()
            close_db = True
        else:
            close_db = False

        try:
            # 先同步Mailu数据
            sync_result = sync_with_mailu(db)

            # 获取统计数据
            total_emails = db.query(TempEmail).count()
            active_emails = db.query(TempEmail).filter(
                TempEmail.is_active == True,
                TempEmail.expires_at > datetime.utcnow()
            ).count()
            total_codes = db.query(VerificationCode).count()

            stats = {
                "total_emails": total_emails,
                "active_emails": active_emails,
                "total_codes": total_codes,
                "updated_at": datetime.utcnow().isoformat(),
                "last_sync": sync_result
            }

            logger.info(f"统计数据已更新: {stats}")
            return stats

        finally:
            if close_db:
                db.close()

    except Exception as e:
        logger.error(f"更新统计数据失败: {str(e)}")
        raise


async def update_stats_cache_async(db):
    """更新统计数据缓存（异步版本）"""
    try:
        # 先同步Mailu数据
        sync_result = await sync_with_mailu_async(db)

        # 获取统计数据
        total_emails = db.query(TempEmail).count()
        active_emails = db.query(TempEmail).filter(
            TempEmail.is_active == True,
            TempEmail.expires_at > datetime.utcnow()
        ).count()
        total_codes = db.query(VerificationCode).count()

        stats = {
            "total_emails": total_emails,
            "active_emails": active_emails,
            "total_codes": total_codes,
            "updated_at": datetime.utcnow().isoformat(),
            "last_sync": sync_result
        }

        logger.info(f"统计数据已更新（异步）: {stats}")
        return stats

    except Exception as e:
        logger.error(f"更新统计数据失败（异步）: {str(e)}")
        raise

def check_imap_emails(email_addr: str, password: str) -> List[Dict]:
    """通过IMAP检查邮件 - 使用imaplib替代IMAPClient"""
    import imaplib
    import email
    from email.header import decode_header

    try:
        # 获取IMAP配置
        imap_server = os.getenv("IMAP_SERVER", "imap.example.com")
        imap_port = int(os.getenv("IMAP_PORT", "993"))
        use_ssl = os.getenv("IMAP_USE_SSL", "true").lower() == "true"

        logger.info(f"连接IMAP服务器: {imap_server}:{imap_port} (SSL: {use_ssl})")

        # 连接IMAP服务器
        if use_ssl:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        else:
            mail = imaplib.IMAP4(imap_server, imap_port)

        # 设置超时时间
        mail.socket().settimeout(30)

        try:
            # 登录
            mail.login(email_addr, password)
            logger.info(f"IMAP登录成功: {email_addr}")

            # 选择收件箱
            mail.select('INBOX')

            # 搜索未读邮件
            status, messages = mail.search(None, 'UNSEEN')
            logger.info(f"搜索未读邮件状态: {status}")

            emails_data = []

            if status == 'OK' and messages[0]:
                msg_ids = messages[0].split()
                logger.info(f"找到 {len(msg_ids)} 封未读邮件")

                # 获取最近的10封邮件
                messages_to_fetch = msg_ids[-10:] if len(msg_ids) > 10 else msg_ids

                for msg_id in messages_to_fetch:
                    try:
                        # 获取邮件
                        status, msg_data = mail.fetch(msg_id, '(RFC822)')
                        if status != 'OK':
                            continue

                        # 正确处理IMAP响应格式
                        if msg_data and len(msg_data) > 0:
                            if isinstance(msg_data[0], tuple) and len(msg_data[0]) > 1:
                                raw_email = msg_data[0][1]
                            else:
                                logger.warning(f"Unexpected IMAP response format: {msg_data}")
                                continue
                        else:
                            logger.warning(f"No data in IMAP response")
                            continue
                        email_message = email.message_from_bytes(raw_email)

                        # 提取发件人
                        from_header = email_message.get('From', '')
                        sender = from_header

                        # 提取主题
                        subject_header = email_message.get('Subject', '')
                        subject_parts = decode_header(subject_header)
                        subject = ''
                        for part, encoding in subject_parts:
                            if isinstance(part, bytes):
                                if encoding:
                                    subject += part.decode(encoding, errors='ignore')
                                else:
                                    subject += part.decode('utf-8', errors='ignore')
                            else:
                                subject += str(part)

                        # 提取邮件内容
                        content = ""
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                if part.get_content_type() == 'text/plain':
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        charset = part.get_content_charset() or 'utf-8'
                                        content = payload.decode(charset, errors='ignore')
                                    break
                        else:
                            payload = email_message.get_payload(decode=True)
                            if payload:
                                charset = email_message.get_content_charset() or 'utf-8'
                                content = payload.decode(charset, errors='ignore')

                        # 提取时间
                        date_header = email_message.get('Date', '')
                        received_at = datetime.utcnow()  # 简化处理

                        email_data = {
                            "sender": sender,
                            "subject": subject,
                            "content": content,
                            "received_at": received_at.isoformat(),
                            "message_id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)
                        }

                        emails_data.append(email_data)
                        logger.info(f"处理邮件: {subject[:50]}...")

                    except Exception as e:
                        logger.error(f"处理邮件 {msg_id} 失败: {str(e)}")
                        continue

            return emails_data

        finally:
            # 确保关闭连接
            try:
                mail.logout()
            except:
                pass

    except Exception as e:
        logger.error(f"IMAP邮件检查失败 {email_addr}: {str(e)}")
        return []


def extract_sender(envelope) -> str:
    """提取发件人信息"""
    try:
        if envelope.from_ and len(envelope.from_) > 0:
            from_addr = envelope.from_[0]
            if hasattr(from_addr, 'mailbox') and hasattr(from_addr, 'host'):
                return f"{from_addr.mailbox}@{from_addr.host}"
            return str(from_addr)
        return "unknown@sender.com"
    except Exception as e:
        logger.warning(f"提取发件人失败: {str(e)}")
        return "unknown@sender.com"


def extract_subject(envelope) -> str:
    """提取邮件主题"""
    try:
        if envelope.subject:
            # 处理编码
            subject_parts = email.header.decode_header(envelope.subject)
            subject = ""
            for part, encoding in subject_parts:
                if isinstance(part, bytes):
                    if encoding:
                        subject += part.decode(encoding)
                    else:
                        subject += part.decode('utf-8', errors='ignore')
                else:
                    subject += str(part)
            return subject
        return "No Subject"
    except Exception as e:
        logger.warning(f"提取主题失败: {str(e)}")
        return "No Subject"


def extract_content(email_message) -> str:
    """提取邮件内容"""
    try:
        content = ""

        if email_message.is_multipart():
            # 多部分邮件
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        content += payload.decode(charset, errors='ignore')
        else:
            # 单部分邮件
            payload = email_message.get_payload(decode=True)
            if payload:
                charset = email_message.get_content_charset() or 'utf-8'
                content = payload.decode(charset, errors='ignore')

        return content.strip()

    except Exception as e:
        logger.warning(f"提取邮件内容失败: {str(e)}")
        return ""


def sync_with_mailu(db):
    """与Mailu服务端同步用户数据（同步版本，用于FastAPI中调用）"""
    try:
        logger.info("开始与Mailu服务端同步数据")

        # 获取本地所有临时邮箱
        local_emails = {email.email: email for email in db.query(TempEmail).all()}
        logger.info(f"本地数据库中有 {len(local_emails)} 个邮箱")

        # 获取Mailu服务端的所有用户（使用同步方式）
        try:
            import requests
            import os

            api_url = os.getenv("API_URL")
            token = os.getenv("API_TOKEN")

            if not api_url or not token:
                raise ValueError("Mailu API配置缺失")

            base_url = api_url if api_url.endswith('/') else f"{api_url}/"
            headers = {"Authorization": f"Bearer {token}"}

            response = requests.get(f"{base_url}user", headers=headers, timeout=30.0)
            response.raise_for_status()
            mailu_users = response.json()
            mailu_emails = {user['email']: user for user in mailu_users}
            logger.info(f"Mailu服务端有 {len(mailu_emails)} 个用户")

        except Exception as e:
            logger.warning(f"获取Mailu用户列表失败: {str(e)}")
            return {"sync_status": "failed", "error": str(e), "timestamp": datetime.utcnow().isoformat()}

        # 找出需要同步的邮箱
        to_deactivate = []  # 需要在本地标记为非活跃的邮箱
        to_remove = []      # 需要从本地删除的邮箱

        for local_email, local_record in local_emails.items():
            if local_email not in mailu_emails:
                # 本地有但Mailu没有 - 可能是被管理员删除了
                if local_record.is_active:
                    to_deactivate.append(local_email)
                    logger.warning(f"邮箱 {local_email} 在Mailu中不存在，将标记为非活跃")
                else:
                    to_remove.append(local_email)
                    logger.info(f"邮箱 {local_email} 已非活跃且在Mailu中不存在，将删除")

        # 执行同步操作
        deactivated_count = 0
        removed_count = 0

        # 标记为非活跃
        for email in to_deactivate:
            db.query(TempEmail).filter(TempEmail.email == email).update({"is_active": False})
            deactivated_count += 1

        # 删除记录
        for email in to_remove:
            db.query(TempEmail).filter(TempEmail.email == email).delete()
            removed_count += 1

        if deactivated_count > 0 or removed_count > 0:
            db.commit()
            logger.info(f"同步完成: 标记非活跃 {deactivated_count} 个，删除 {removed_count} 个")

        return {
            "sync_status": "success",
            "local_emails": len(local_emails),
            "mailu_users": len(mailu_emails),
            "deactivated": deactivated_count,
            "removed": removed_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Mailu数据同步失败: {str(e)}")
        return {"sync_status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}


async def sync_with_mailu_async(db):
    """与Mailu服务端同步用户数据（异步版本，用于Celery任务）"""
    try:
        logger.info("开始与Mailu服务端同步数据（异步）")

        # 获取本地所有临时邮箱
        local_emails = {email.email: email for email in db.query(TempEmail).all()}
        logger.info(f"本地数据库中有 {len(local_emails)} 个邮箱")

        # 获取Mailu服务端的所有用户（使用异步HTTP客户端）
        try:
            async with MailuClient() as client:
                mailu_users = await client.list_users()
                mailu_emails = {user['email']: user for user in mailu_users}
                logger.info(f"Mailu服务端有 {len(mailu_emails)} 个用户")

        except Exception as e:
            logger.warning(f"获取Mailu用户列表失败: {str(e)}")
            return {"sync_status": "failed", "error": str(e), "timestamp": datetime.utcnow().isoformat()}

        # 找出需要同步的邮箱
        to_deactivate = []  # 需要在本地标记为非活跃的邮箱
        to_remove = []      # 需要从本地删除的邮箱

        for local_email, local_record in local_emails.items():
            if local_email not in mailu_emails:
                # 本地有但Mailu没有 - 可能是被管理员删除了
                if local_record.is_active:
                    to_deactivate.append(local_email)
                    logger.warning(f"邮箱 {local_email} 在Mailu中不存在，将标记为非活跃")
                else:
                    to_remove.append(local_email)
                    logger.info(f"邮箱 {local_email} 已非活跃且在Mailu中不存在，将删除")

        # 执行同步操作
        deactivated_count = 0
        removed_count = 0

        # 标记为非活跃
        for email in to_deactivate:
            db.query(TempEmail).filter(TempEmail.email == email).update({"is_active": False})
            deactivated_count += 1

        # 删除记录
        for email in to_remove:
            db.query(TempEmail).filter(TempEmail.email == email).delete()
            removed_count += 1

        if deactivated_count > 0 or removed_count > 0:
            db.commit()
            logger.info(f"同步完成: 标记非活跃 {deactivated_count} 个，删除 {removed_count} 个")

        return {
            "sync_status": "success",
            "local_emails": len(local_emails),
            "mailu_users": len(mailu_emails),
            "deactivated": deactivated_count,
            "removed": removed_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Mailu数据同步失败: {str(e)}")
        return {"sync_status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
