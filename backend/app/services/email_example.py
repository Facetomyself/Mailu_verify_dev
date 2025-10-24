"""邮件服务使用示例"""

import asyncio
from email_service import email_service
from mailu_client import MailuClient


async def example_send_email():
    """基本邮件发送示例"""
    try:
        result = await email_service.send_email(
            from_email="wmhi0y8y@zhangxuemin.work",
            to_email="test@example.com",
            subject="测试邮件",
            body="这是一封测试邮件的内容"
        )
        print("邮件发送成功:", result)
    except Exception as e:
        print("邮件发送失败:", e)


async def example_send_verification_email():
    """验证码邮件发送示例"""
    try:
        result = await email_service.send_verification_email(
            from_email="wmhi0y8y@zhangxuemin.work",
            to_email="user@example.com",
            verification_code="123456"
        )
        print("验证码邮件发送成功:", result)
    except Exception as e:
        print("验证码邮件发送失败:", e)


async def example_send_notification_email():
    """通知邮件发送示例"""
    try:
        result = await email_service.send_notification_email(
            from_email="wmhi0y8y@zhangxuemin.work",
            to_email="admin@example.com",
            title="系统通知",
            message="系统维护完成，请检查服务状态。"
        )
        print("通知邮件发送成功:", result)
    except Exception as e:
        print("通知邮件发送失败:", e)


async def example_using_mailu_client():
    """通过MailuClient使用邮件服务示例"""
    try:
        async with MailuClient() as client:
            # 发送基本邮件
            result = await client.send_email_smtp(
                from_email="wmhi0y8y@zhangxuemin.work",
                to_email="test@example.com",
                subject="来自MailuClient的邮件",
                body="通过MailuClient发送的邮件内容"
            )
            print("通过MailuClient发送成功:", result)

            # 发送验证码邮件
            result = await client.send_verification_email(
                from_email="wmhi0y8y@zhangxuemin.work",
                to_email="user@example.com",
                verification_code="789012"
            )
            print("验证码邮件发送成功:", result)

    except Exception as e:
        print("MailuClient邮件发送失败:", e)


async def example_html_email():
    """HTML邮件发送示例"""
    try:
        html_content = """
        <html>
        <body>
            <h1>HTML邮件测试</h1>
            <p>这是一个<strong>HTML格式</strong>的邮件。</p>
            <ul>
                <li>支持HTML标签</li>
                <li>支持样式</li>
                <li>支持链接和图片</li>
            </ul>
            <p><a href="https://example.com">点击这里</a>访问网站</p>
        </body>
        </html>
        """

        result = await email_service.send_email(
            from_email="wmhi0y8y@zhangxuemin.work",
            to_email="test@example.com",
            subject="HTML邮件测试",
            body="您的邮件客户端不支持HTML，请查看HTML版本。",
            html_body=html_content
        )
        print("HTML邮件发送成功:", result)
    except Exception as e:
        print("HTML邮件发送失败:", e)


async def main():
    """主函数 - 运行所有示例"""
    print("=== 邮件服务使用示例 ===\n")

    print("1. 基本邮件发送:")
    await example_send_email()

    print("\n2. 验证码邮件:")
    await example_send_verification_email()

    print("\n3. 通知邮件:")
    await example_send_notification_email()

    print("\n4. 通过MailuClient发送:")
    await example_using_mailu_client()

    print("\n5. HTML邮件:")
    await example_html_email()

    print("\n=== 示例运行完成 ===")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
