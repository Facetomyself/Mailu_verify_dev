"""Mailu API客户端"""

import httpx
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import os
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MailuClient:
    """Mailu API客户端"""

    def __init__(self):
        self.base_url = os.getenv("API_URL", "https://mail.zhangxuemin.work/api/v1/")
        self.token = os.getenv("API_TOKEN", "f80dae1387106ff8995d6049e42934c3")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """统一的请求方法"""
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP错误: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"请求错误: {str(e)}")
            raise

    # 用户管理
    async def create_user(self, email: str, password: str, **kwargs) -> Dict:
        """创建用户"""
        data = {
            "email": email,
            "raw_password": password,
            **kwargs
        }
        return await self._request("POST", "/user", json=data)

    async def get_user(self, email: str) -> Dict:
        """获取用户信息"""
        return await self._request("GET", f"/user/{email}")

    async def update_user(self, email: str, **kwargs) -> Dict:
        """更新用户信息"""
        return await self._request("PATCH", f"/user/{email}", json=kwargs)

    async def delete_user(self, email: str) -> Dict:
        """删除用户"""
        return await self._request("DELETE", f"/user/{email}")

    async def list_users(self) -> List[Dict]:
        """列出所有用户"""
        return await self._request("GET", "/user")

    # 域名管理
    async def create_domain(self, name: str, **kwargs) -> Dict:
        """创建域名"""
        data = {"name": name, **kwargs}
        return await self._request("POST", "/domain", json=data)

    async def get_domain(self, domain: str) -> Dict:
        """获取域名信息"""
        return await self._request("GET", f"/domain/{domain}")

    async def update_domain(self, domain: str, **kwargs) -> Dict:
        """更新域名"""
        return await self._request("PATCH", f"/domain/{domain}", json=kwargs)

    async def delete_domain(self, domain: str) -> Dict:
        """删除域名"""
        return await self._request("DELETE", f"/domain/{domain}")

    async def list_domains(self) -> List[Dict]:
        """列出所有域名"""
        return await self._request("GET", "/domain")

    # 别名管理
    async def create_alias(self, email: str, destination: List[str], **kwargs) -> Dict:
        """创建别名"""
        data = {
            "email": email,
            "destination": destination,
            **kwargs
        }
        return await self._request("POST", "/alias", json=data)

    async def get_alias(self, alias: str) -> Dict:
        """获取别名"""
        return await self._request("GET", f"/alias/{alias}")

    async def update_alias(self, alias: str, **kwargs) -> Dict:
        """更新别名"""
        return await self._request("PATCH", f"/alias/{alias}", json=kwargs)

    async def delete_alias(self, alias: str) -> Dict:
        """删除别名"""
        return await self._request("DELETE", f"/alias/{alias}")

    async def list_aliases(self) -> List[Dict]:
        """列出所有别名"""
        return await self._request("GET", "/alias")

    # Token管理
    async def create_token(self, email: str, **kwargs) -> Dict:
        """创建Token"""
        data = {"email": email, **kwargs}
        return await self._request("POST", "/token", json=data)

    async def get_tokens(self, email: str) -> List[Dict]:
        """获取用户的Token"""
        return await self._request("GET", f"/tokenuser/{email}")

    async def list_tokens(self) -> List[Dict]:
        """列出所有Token"""
        return await self._request("GET", "/token")

    async def delete_token(self, token_id: str) -> Dict:
        """删除Token"""
        return await self._request("DELETE", f"/token/{token_id}")

    # 邮件发送（使用SMTP）
    async def send_email_smtp(self, from_email: str, to_email: str, subject: str, body: str, **kwargs) -> Dict:
        """通过SMTP发送邮件（兼容性方法，使用新的邮件服务）"""
        from .email_service import email_service

        # 支持HTML内容
        html_body = kwargs.get('html_body')

        return await email_service.send_email(
            from_email=from_email,
            to_email=to_email,
            subject=subject,
            body=body,
            html_body=html_body
        )

    async def send_verification_email(self, from_email: str, to_email: str, verification_code: str) -> Dict:
        """发送验证码邮件"""
        from .email_service import email_service
        return await email_service.send_verification_email(
            to_email=to_email,
            verification_code=verification_code,
            from_email=from_email
        )

    async def send_notification_email(self, from_email: str, to_email: str, title: str, message: str) -> Dict:
        """发送通知邮件"""
        from .email_service import email_service
        return await email_service.send_notification_email(
            to_email=to_email,
            title=title,
            message=message,
            from_email=from_email
        )

    async def get_email_logs(self, **kwargs) -> List[Dict]:
        """获取邮件日志"""
        params = {k: v for k, v in kwargs.items() if v is not None}
        return await self._request("GET", "/logs", params=params)

# 响应模型
class UserCreate(BaseModel):
    email: str
    raw_password: str
    comment: Optional[str] = None
    quota_bytes: Optional[int] = None
    global_admin: Optional[bool] = False
    enabled: Optional[bool] = True
    change_pw_next_login: Optional[bool] = False
    enable_imap: Optional[bool] = True
    enable_pop: Optional[bool] = True
    allow_spoofing: Optional[bool] = False
    forward_enabled: Optional[bool] = False
    forward_destination: Optional[List[str]] = None
    forward_keep: Optional[bool] = False
    reply_enabled: Optional[bool] = False
    reply_subject: Optional[str] = None
    reply_body: Optional[str] = None
    reply_startdate: Optional[str] = None
    reply_enddate: Optional[str] = None
    displayed_name: Optional[str] = None
    spam_enabled: Optional[bool] = True
    spam_mark_as_read: Optional[bool] = False
    spam_threshold: Optional[int] = 80

class DomainCreate(BaseModel):
    name: str
    comment: Optional[str] = None
    max_users: Optional[int] = -1
    max_aliases: Optional[int] = -1
    max_quota_bytes: Optional[int] = 0
    signup_enabled: Optional[bool] = False
    alternatives: Optional[List[str]] = None
