/**
 * Mailu验证码平台前端主脚本
 */

// 全局工具函数
class AppUtils {
    static copyToClipboard(text) {
        return navigator.clipboard.writeText(text).then(() => {
            this.showNotification('已复制到剪贴板', 'success');
        }).catch(() => {
            // 兼容性处理
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification('已复制到剪贴板', 'success');
        });
    }

    static showNotification(message, type = 'info', duration = 3000) {
        // 移除现有的通知
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notification => notification.remove());

        // 创建新的通知
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;

        const colors = {
            success: '#48bb78',
            error: '#f56565',
            warning: '#ed8936',
            info: '#4299e1'
        };

        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            background: ${colors[type]};
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transform: translateX(400px);
            opacity: 0;
            transition: all 0.3s ease;
            max-width: 350px;
            word-wrap: break-word;
        `;

        notification.textContent = message;
        document.body.appendChild(notification);

        // 显示动画
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);

        // 自动消失
        setTimeout(() => {
            notification.style.transform = 'translateX(400px)';
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, duration);
    }

    static formatDateTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    static formatRelativeTime(dateString) {
        const now = new Date();
        const date = new Date(dateString);
        const diff = now - date;

        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return '刚刚';
        if (minutes < 60) return `${minutes}分钟前`;
        if (hours < 24) return `${hours}小时前`;
        return `${days}天前`;
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }
}

// API 客户端
class APIClient {
    constructor(baseURL = '') {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: '请求失败' }));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API请求失败: ${endpoint}`, error);
            throw error;
        }
    }

    // 邮箱相关API
    async getEmails() {
        return this.request('/api/emails');
    }

    async createEmail(data) {
        return this.request('/api/emails', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async deleteEmail(email) {
        return this.request(`/api/emails/${email}`, {
            method: 'DELETE'
        });
    }

    async getEmailVerifications(email) {
        // 对邮箱地址进行URL编码
        const encodedEmail = encodeURIComponent(email);
        return this.request(`/api/emails/${encodedEmail}/verifications`);
    }

    async getAllVerifications() {
        return this.request('/api/verifications');
    }

    async markVerificationAsRead(email, verificationId) {
        // 对邮箱地址进行URL编码
        const encodedEmail = encodeURIComponent(email);
        return this.request(`/api/emails/${encodedEmail}/verifications/${verificationId}/read`, {
            method: 'PUT'
        });
    }

    async getStats() {
        return this.request('/api/stats');
    }
}

// 全局状态管理
class AppState {
    constructor() {
        this.currentEmail = null;
        this.isLoading = false;
        this.api = new APIClient();
    }

    setCurrentEmail(email) {
        this.currentEmail = email;
        localStorage.setItem('currentEmail', email);
    }

    getCurrentEmail() {
        return this.currentEmail || localStorage.getItem('currentEmail');
    }

    setLoading(loading) {
        this.isLoading = loading;
        // 可以在这里更新全局加载状态
    }

    getLoading() {
        return this.isLoading;
    }
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化全局状态
    window.appState = new AppState();
    window.appUtils = AppUtils;

    // 添加全局错误处理
    window.addEventListener('error', function(e) {
        console.error('全局错误:', e.error);
        AppUtils.showNotification('发生错误，请刷新页面重试', 'error');
    });

    window.addEventListener('unhandledrejection', function(e) {
        console.error('未处理的Promise错误:', e.reason);
        AppUtils.showNotification('网络请求失败', 'error');
    });

    // 添加页面可见性变化处理
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            // 页面重新变为可见时，可以在这里刷新数据
            console.log('页面重新变为可见');
        }
    });

    console.log('Mailu验证码平台初始化完成');
});

// 导出全局对象
window.AppUtils = AppUtils;
window.APIClient = APIClient;
window.AppState = AppState;
