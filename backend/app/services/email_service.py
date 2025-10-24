"""邮件发送服务"""

import os
import smtplib
import ssl
import asyncio
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union
import logging

from ..utils.helpers import validate_email

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送服务类"""

    def __init__(self):
        # 从环境变量获取SMTP配置
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.example.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.use_ssl = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
        self.use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"

    def get_credentials_from_email(self, email: str) -> tuple[str, str]:
        """根据邮箱地址从数据库获取真实的SMTP认证信息"""
        from ..models.database import SessionLocal, TempEmail

        username = email

        # 从数据库查询邮箱的真实密码
        db = SessionLocal()
        try:
            temp_email = db.query(TempEmail).filter(
                TempEmail.email == email,
                TempEmail.is_active == True
            ).first()

            if temp_email and temp_email.password:
                password = temp_email.password
                logger.info(f"从数据库获取到邮箱 {email} 的SMTP认证信息")
                return username, password
            else:
                logger.error(f"数据库中未找到邮箱 {email} 的有效SMTP密码")
                raise Exception(f"邮箱 {email} 未找到有效的SMTP认证信息")

        except Exception as e:
            logger.error(f"获取SMTP认证信息失败: {e}")
            raise Exception(f"无法获取邮箱 {email} 的SMTP认证信息: {e}")
        finally:
            db.close()

    def _resolve_credentials(self, from_email: str) -> Tuple[str, str]:
        """根据发件人解析SMTP凭据"""
        try:
            return self.get_credentials_from_email(from_email)
        except Exception as exc:
            raise ValueError(f"无法获取发件人 {from_email} 的SMTP凭据: {exc}")

    def _normalize_recipients(self, to_email: Union[str, Sequence[str]]) -> List[str]:
        """整理并验证收件人列表"""
        if isinstance(to_email, str):
            # 兼容逗号分隔和分号分隔
            candidates = [item.strip() for item in to_email.replace(';', ',').split(',') if item.strip()]
        else:
            candidates = [item.strip() for item in to_email if item and item.strip()]

        if not candidates:
            raise ValueError("收件人列表为空")

        invalid = [addr for addr in candidates if not validate_email(addr)]
        if invalid:
            raise ValueError(f"无效的收件人地址: {', '.join(invalid)}")

        return candidates

    def _clean_credentials(self, credential: str) -> str:
        """
        智能清理和编码凭据，处理特殊字符
        支持多种编码方式以适应不同的SMTP服务器要求
        """
        import urllib.parse

        if not credential:
            return credential

        try:
            # 方法1: 尝试直接ASCII编码（最常见的情况）
            return credential.encode('ascii').decode('ascii')
        except UnicodeEncodeError:
            try:
                # 方法2: URL编码 "@" 符号
                # 这在某些API和SMTP实现中是必需的
                url_encoded = credential.replace('@', '%40')
                return url_encoded.encode('ascii').decode('ascii')
            except UnicodeEncodeError:
                try:
                    # 方法3: 完整的URL编码
                    fully_encoded = urllib.parse.quote(credential, safe='')
                    logger.info(f"凭据使用了完整URL编码: {credential} -> {fully_encoded}")
                    return fully_encoded
                except Exception:
                    # 方法4: 移除特殊字符（最后的尝试）
                    cleaned = ''.join(c for c in credential if ord(c) < 128)
                    logger.info(f"凭据移除了特殊字符: {credential} -> {cleaned}")
                    return cleaned

    def _create_email_message(self, from_email: str, to_email: str, subject: str,
                            body: str, html_body: Optional[str] = None) -> MIMEMultipart:
        """创建邮件消息"""
        msg = MIMEMultipart('alternative')
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject

        # 添加纯文本版本
        if body:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 添加HTML版本（如果提供）
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        return msg

    def _send_email_sync(
        self,
        from_email: str,
        recipients: Iterable[str],
        subject: str,
        body: str,
        html_body: Optional[str],
        username: str,
        password: str,
    ) -> Dict:
        """同步发送邮件"""
        recipients_list = list(recipients)

        try:
            # 创建邮件消息
            msg = self._create_email_message(from_email, ', '.join(recipients_list), subject, body, html_body)

            # 根据配置选择连接方式
            if self.use_ssl and self.smtp_port == 465:
                # SSL连接（465端口）
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            elif self.use_tls and self.smtp_port == 587:
                # TLS连接（587端口）
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
            else:
                # 普通SMTP连接
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)

            # SMTP认证
            if username and password:
                username_clean = self._clean_credentials(username)
                password_clean = self._clean_credentials(password)
                server.login(username_clean, password_clean)

            # 发送邮件
            server.sendmail(from_email, recipients_list, msg.as_string())
            server.quit()

            logger.info(f"邮件发送成功: {from_email} -> {', '.join(recipients_list)}")

            return {
                "status": "success",
                "message": "邮件发送成功",
                "from": from_email,
                "to": recipients_list,
                "server": self.smtp_server,
                "port": self.smtp_port
            }

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP认证失败: {e}")
            raise Exception(f"SMTP认证失败: {e}")
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP连接失败: {e}")
            raise Exception(f"SMTP连接失败: {e}")
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            raise Exception(f"邮件发送失败: {e}")

    async def send_email(
        self,
        from_email: str,
        to_email: Union[str, Sequence[str]],
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> Dict:
        """异步发送邮件"""
        recipients = self._normalize_recipients(to_email)
        username, password = self._resolve_credentials(from_email)

        # 如果凭据对应的账号与请求的发件人不同，自动切换至凭据账号
        if username and from_email.lower() != username.lower():
            logger.warning(
                f"发件人地址 {from_email} 与凭据账号 {username} 不一致，实际发件人将使用凭据账号"
            )
            effective_from = username
        else:
            effective_from = from_email

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                self._send_email_sync,
                effective_from,
                recipients,
                subject,
                body,
                html_body,
                username,
                password,
            )
            result["from"] = effective_from
            result["requested_from"] = from_email
            result["to"] = recipients
            return result

    async def send_verification_email(
        self,
        to_email: str,
        verification_code: str,
        from_email: str,
    ) -> Dict:
        """发送验证码邮件"""
        subject = "验证码 - Mailu邮箱验证"
        body = f"""
亲爱的用户，

您的验证码是: {verification_code}

请在10分钟内使用此验证码完成验证。

此邮件由系统自动发送，请勿回复。

---
Mailu邮箱系统
        """.strip()

        html_body = f"""
<html>
<body>
    <h2>验证码邮件</h2>
    <p>亲爱的用户，</p>
    <p>您的验证码是: <strong style="font-size: 24px; color: #007bff;">{verification_code}</strong></p>
    <p>请在10分钟内使用此验证码完成验证。</p>
    <hr>
    <p style="color: #666; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
    <p style="color: #666; font-size: 12px;">---<br>Mailu邮箱系统</p>
</body>
</html>
        """.strip()

        return await self.send_email(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body
        )

    async def send_notification_email(
        self,
        to_email: str,
        title: str,
        message: str,
        from_email: str,
    ) -> Dict:
        """发送通知邮件"""
        subject = f"通知 - {title}"
        body = f"""
{title}

{message}

---
Mailu邮箱系统
        """.strip()

        return await self.send_email(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body
        )


# 全局邮件服务实例
email_service = EmailService()
