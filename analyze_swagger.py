#!/usr/bin/env python3
"""
分析Mailu API swagger文档
检查权限问题和发件相关功能
"""

import json
import re
from collections import defaultdict

def analyze_swagger():
    """分析swagger.json文件"""
    print("🔍 分析Mailu API swagger文档")
    print("=" * 60)

    try:
        with open('swagger.json', 'r', encoding='utf-8') as f:
            swagger = json.load(f)
    except FileNotFoundError:
        print("❌ swagger.json文件不存在")
        return

    # 基本信息
    print("📋 API基本信息:")
    print(f"   版本: {swagger.get('info', {}).get('title', 'Unknown')}")
    print(f"   API版本: {swagger.get('info', {}).get('version', 'Unknown')}")
    print(f"   基础路径: {swagger.get('basePath', 'Unknown')}")
    print()

    # 分析API端点
    paths = swagger.get('paths', {})
    print("📊 API端点分析:")
    print(f"   总端点数: {len(paths)}")

    # 统计HTTP方法
    methods_count = defaultdict(int)
    auth_required = 0
    total_endpoints = 0

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                methods_count[method.upper()] += 1
                total_endpoints += 1

                # 检查是否需要认证
                if 'security' in details:
                    auth_required += 1

    print(f"   需要认证的端点: {auth_required}/{total_endpoints}")
    print("   HTTP方法分布:")
    for method, count in methods_count.items():
        print(f"     {method}: {count}")
    print()

    # 查找邮件发送相关端点
    print("📧 邮件发送相关端点:")
    send_related = []
    smtp_related = []
    mail_related = []

    for path in paths.keys():
        if 'send' in path.lower():
            send_related.append(path)
        if 'smtp' in path.lower():
            smtp_related.append(path)
        if 'mail' in path.lower():
            mail_related.append(path)

    if send_related:
        print(f"   发送相关端点: {len(send_related)}")
        for endpoint in send_related:
            print(f"     ✅ {endpoint}")
    else:
        print("   ❌ 没有找到发送邮件的端点")

    if smtp_related:
        print(f"   SMTP相关端点: {len(smtp_related)}")
        for endpoint in smtp_related:
            print(f"     📡 {endpoint}")

    if mail_related:
        print(f"   邮件相关端点: {len(mail_related)}")
        for endpoint in mail_related:
            print(f"     ✉️ {endpoint}")
    print()

    # 分析权限和错误码
    print("🔐 权限和错误分析:")

    error_codes = defaultdict(int)
    for path, methods in paths.items():
        for method, details in methods.items():
            if 'responses' in details:
                for code in details['responses'].keys():
                    if code in ['401', '403', '404', '500']:
                        error_codes[code] += 1

    print("   常见错误码统计:")
    error_descriptions = {
        '401': '未授权 - 需要认证',
        '403': '禁止访问 - 权限不足',
        '404': '未找到 - 端点不存在',
        '500': '服务器错误 - 内部错误'
    }

    for code in ['401', '403', '404', '500']:
        count = error_codes.get(code, 0)
        if count > 0:
            print(f"     {code}: {count}次 - {error_descriptions[code]}")
    print()

    # 分析用户相关功能
    print("👤 用户功能分析:")
    user_endpoints = []
    domain_endpoints = []
    alias_endpoints = []

    for path in paths.keys():
        if '/user' in path:
            user_endpoints.append(path)
        elif '/domain' in path:
            domain_endpoints.append(path)
        elif '/alias' in path:
            alias_endpoints.append(path)

    print(f"   用户管理端点: {len(user_endpoints)}")
    print(f"   域名管理端点: {len(domain_endpoints)}")
    print(f"   别名管理端点: {len(alias_endpoints)}")

    # 检查用户创建功能
    user_create_found = False
    for path, methods in paths.items():
        if '/user' in path and 'post' in methods:
            user_create_found = True
            print("   ✅ 支持用户创建")
            break

    if not user_create_found:
        print("   ❌ 未找到用户创建功能")

    # 检查用户权限设置
    user_permissions = []
    for path, methods in paths.items():
        if '/user' in path:
            for method, details in methods.items():
                if 'parameters' in details:
                    for param in details['parameters']:
                        if 'schema' in param and '$ref' in param['schema']:
                            if 'User' in param['schema']['$ref']:
                                user_permissions.append(f"{method.upper()} {path}")

    if user_permissions:
        print("   📋 用户权限相关操作:")
        for perm in user_permissions[:5]:  # 只显示前5个
            print(f"     • {perm}")
    print()

    # 分析认证机制
    print("🔑 认证机制分析:")
    security_defs = swagger.get('securityDefinitions', {})
    if security_defs:
        for name, sec_def in security_defs.items():
            print(f"   认证类型: {sec_def.get('type', 'Unknown')}")
            print(f"   认证位置: {sec_def.get('in', 'Unknown')}")
            print(f"   认证字段: {sec_def.get('name', 'Unknown')}")
    else:
        print("   ❌ 未找到认证定义")

    # 全局安全设置
    global_security = swagger.get('security', [])
    if global_security:
        print("   ✅ 全局需要认证")
    else:
        print("   ⚠️ 部分端点可能不需要认证")
    print()

    # 结论和建议
    print("🎯 结论和建议:")
    print("=" * 60)

    issues = []
    recommendations = []

    # 检查是否有发送邮件功能
    if not send_related:
        issues.append("❌ 缺少邮件发送API端点")
        recommendations.append("📧 建议使用SMTP直接发送邮件，而不是通过API")

    # 检查认证问题
    if auth_required < total_endpoints * 0.8:  # 如果少于80%的端点需要认证
        issues.append("⚠️ 部分API端点不需要认证")
        recommendations.append("🔐 确保所有敏感操作都需要适当的认证")

    # 检查权限问题
    if error_codes.get('403', 0) > 0:
        issues.append("🚫 存在权限拒绝错误")
        recommendations.append("👤 检查API token是否有足够的权限")

    # 基本问题
    issues.append("📡 Mailu API不支持直接发送邮件")
    recommendations.append("🔧 使用SMTP协议进行邮件发送")
    recommendations.append("🔑 确保SMTP服务器配置正确")
    recommendations.append("👤 检查发件人邮箱权限和状态")

    print("   发现的问题:")
    for issue in issues:
        print(f"     {issue}")

    print("\n   建议解决方案:")
    for rec in recommendations:
        print(f"     {rec}")

    print("\n" + "=" * 60)
    print("✅ 分析完成")

if __name__ == "__main__":
    analyze_swagger()
