"""Redis缓存服务"""

import redis.asyncio as redis
import json
import logging
from typing import Any, Optional, List
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RedisCache:
    """Redis缓存管理器"""

    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.db = int(os.getenv("REDIS_DB", 0))
        self.password = os.getenv("REDIS_PASSWORD")
        self.client = None

    async def connect(self):
        """连接Redis"""
        if self.client is None:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
        return self.client

    async def close(self):
        """关闭连接"""
        if self.client:
            await self.client.close()

    async def _get_client(self):
        """获取Redis客户端"""
        if self.client is None:
            await self.connect()
        return self.client

    # 验证码缓存
    async def cache_verification_code(self, email: str, code: str, expire_seconds: int = 3600):
        """缓存验证码"""
        client = await self._get_client()
        key = f"code:{email}"
        await client.setex(key, expire_seconds, code)
        logger.info(f"缓存验证码: {email} -> {code}")

    async def get_verification_code(self, email: str) -> Optional[str]:
        """获取验证码"""
        client = await self._get_client()
        key = f"code:{email}"
        code = await client.get(key)
        return code

    async def delete_verification_code(self, email: str):
        """删除验证码"""
        client = await self._get_client()
        key = f"code:{email}"
        await client.delete(key)

    # 临时邮箱缓存
    async def cache_temp_email(self, email: str, data: dict, expire_seconds: int = 86400):
        """缓存临时邮箱信息"""
        client = await self._get_client()
        key = f"email:{email}"
        await client.setex(key, expire_seconds, json.dumps(data))
        logger.info(f"缓存临时邮箱: {email}")

    async def get_temp_email(self, email: str) -> Optional[dict]:
        """获取临时邮箱信息"""
        client = await self._get_client()
        key = f"email:{email}"
        data = await client.get(key)
        return json.loads(data) if data else None

    async def delete_temp_email(self, email: str):
        """删除临时邮箱缓存"""
        client = await self._get_client()
        key = f"email:{email}"
        await client.delete(key)

    # 邮件检查锁
    async def acquire_check_lock(self, email: str, expire_seconds: int = 30) -> bool:
        """获取邮件检查锁"""
        client = await self._get_client()
        key = f"lock:check:{email}"
        return await client.set(key, "1", ex=expire_seconds, nx=True)

    async def release_check_lock(self, email: str):
        """释放邮件检查锁"""
        client = await self._get_client()
        key = f"lock:check:{email}"
        await client.delete(key)

    # 统计数据缓存
    async def cache_stats(self, stats: dict):
        """缓存统计数据"""
        client = await self._get_client()
        key = "stats:system"
        await client.setex(key, 300, json.dumps(stats))  # 5分钟过期

    async def get_stats(self) -> Optional[dict]:
        """获取统计数据"""
        client = await self._get_client()
        key = "stats:system"
        data = await client.get(key)
        return json.loads(data) if data else None

    # 邮箱使用计数
    async def increment_email_usage(self, email: str):
        """增加邮箱使用计数"""
        client = await self._get_client()
        key = f"usage:{email}"
        await client.incr(key)

    async def get_email_usage(self, email: str) -> int:
        """获取邮箱使用计数"""
        client = await self._get_client()
        key = f"usage:{email}"
        count = await client.get(key)
        return int(count) if count else 0

    # 批量操作
    async def get_multiple_codes(self, emails: List[str]) -> dict:
        """批量获取验证码"""
        client = await self._get_client()
        keys = [f"code:{email}" for email in emails]
        values = await client.mget(keys)
        result = {}
        for email, value in zip(emails, values):
            if value:
                result[email] = value
        return result

    async def clear_expired_codes(self):
        """清理过期验证码（通过TTL自动过期）"""
        # Redis会自动清理过期键，这里只是记录日志
        logger.info("Redis自动清理过期验证码")

    # 邮件队列
    async def add_email_to_queue(self, email: str, message: dict):
        """添加邮件到队列"""
        client = await self._get_client()
        key = f"queue:emails:{email}"
        await client.rpush(key, json.dumps(message))
        # 设置队列过期时间（24小时）
        await client.expire(key, 86400)

    async def get_emails_from_queue(self, email: str, count: int = 10) -> List[dict]:
        """从队列获取邮件"""
        client = await self._get_client()
        key = f"queue:emails:{email}"
        messages = await client.lrange(key, 0, count - 1)
        return [json.loads(msg) for msg in messages]

    async def clear_email_queue(self, email: str):
        """清空邮件队列"""
        client = await self._get_client()
        key = f"queue:emails:{email}"
        await client.delete(key)

# 全局缓存实例
cache = RedisCache()
