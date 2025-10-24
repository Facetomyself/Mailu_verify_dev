"""辅助工具函数"""

import random
import string
import secrets
from datetime import datetime, timedelta
import hashlib
import re

def generate_random_email(domain: str = "example.com") -> str:
    """生成随机邮箱地址"""
    # 生成8位随机字符串
    random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{random_string}@{domain}"

def generate_secure_password(length: int = 16) -> str:
    """生成安全密码"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def extract_verification_codes(text: str) -> list:
    """从文本中提取验证码"""
    patterns = [
        r'\b\d{4,8}\b',  # 4-8位数字
        r'验证码[：:]\s*(\d{4,8})',  # 中文验证码
        r'verification code[：:]\s*(\d{4,8})',  # 英文验证码
        r'code[：:]\s*(\d{4,8})',  # 简单code
        r'OTP[：:]\s*(\d{4,8})',  # OTP
        r'PIN[：:]\s*(\d{4,8})',  # PIN
    ]

    codes = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        codes.extend(matches)

    # 去重并验证
    unique_codes = list(set(codes))
    return [code for code in unique_codes if 4 <= len(code) <= 8 and code.isdigit()]

def hash_password(password: str) -> str:
    """密码哈希（用于额外安全层）"""
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_expiry_date(hours: int = 24) -> datetime:
    """计算过期时间"""
    return datetime.utcnow() + timedelta(hours=hours)

def format_datetime(dt: datetime) -> str:
    """格式化日期时间"""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """清理输入文本"""
    if not text:
        return ""
    # 移除潜在的恶意字符
    text = re.sub(r'[<>]', '', text)
    return text[:max_length]

def generate_api_key() -> str:
    """生成API密钥"""
    return secrets.token_urlsafe(32)

def is_expired(expiry_time: datetime) -> bool:
    """检查是否过期"""
    return datetime.utcnow() > expiry_time

def get_time_remaining(expiry_time: datetime) -> str:
    """获取剩余时间"""
    if is_expired(expiry_time):
        return "已过期"

    remaining = expiry_time - datetime.utcnow()
    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    elif minutes > 0:
        return f"{minutes}分钟{seconds}秒"
    else:
        return f"{seconds}秒"
