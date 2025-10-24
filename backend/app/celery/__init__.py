"""Celery配置"""

from celery import Celery
import os

# 创建Celery实例
celery_app = Celery(
    "mailu_codes",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
    include=["backend.app.celery.tasks"]
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # 队列路由配置 - 按功能划分任务队列
    task_routes={
        "backend.app.celery.tasks.check_emails": {"queue": "email_check"},
        "backend.app.celery.tasks.extract_codes": {"queue": "code_extract"},
        "backend.app.celery.tasks.cleanup_expired": {"queue": "cleanup"},
    },
    beat_schedule={
        "check-emails-every-30-seconds": {
            "task": "backend.app.celery.tasks.check_emails",
            "schedule": 30.0,
        },
        "sync-mailu-data-every-5-minutes": {
            "task": "backend.app.celery.tasks.sync_mailu_data",
            "schedule": 300.0,  # 每5分钟
        },
        "cleanup-expired-daily": {
            "task": "backend.app.celery.tasks.cleanup_expired",
            "schedule": 86400.0,  # 每天
        },
    },
)
