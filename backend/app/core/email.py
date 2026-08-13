"""SMTP 邮件服务（QQ 邮箱 / 通用 SMTP）"""
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """发送 HTML 邮件（异步）

    返回 True=成功，False=失败（不抛异常，调用方决定是否提示）
    """
    if not settings.email_enabled:
        logger.warning("邮件未启用 (email_enabled=False)，跳过发送 to=%s", to_email)
        return False
    if not settings.email_username or not settings.email_password:
        logger.error("邮件配置缺失 (username/password)，无法发送")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_username}>"
    msg["To"] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.email_smtp_host,
            port=settings.email_smtp_port,
            username=settings.email_username,
            password=settings.email_password,
            use_tls=settings.email_smtp_port == 465,  # 465=SMTPS, 587=STARTTLS
        )
        logger.info("邮件发送成功 to=%s subject=%s", to_email, subject)
        return True
    except Exception as e:
        logger.exception("邮件发送失败 to=%s err=%s", to_email, e)
        return False


# ============== 模板 ==============

def render_reset_password_email(reset_url: str, username: str, ttl_min: int) -> str:
    """密码重置邮件 HTML"""
    return f"""
<div style="font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1e293b; font-size: 18px; margin: 0 0 16px;">重置密码</h2>
  <p style="color: #475569; font-size: 14px; line-height: 1.6;">
    您好 <strong>{username}</strong>，<br>
    我们收到了您的密码重置请求。点击下方按钮重置密码（{ttl_min} 分钟内有效）：
  </p>
  <div style="margin: 24px 0;">
    <a href="{reset_url}" style="display: inline-block; background: #2563eb; color: white;
       padding: 10px 24px; border-radius: 6px; text-decoration: none; font-size: 14px;">
      重置密码
    </a>
  </div>
  <p style="color: #94a3b8; font-size: 12px; line-height: 1.5;">
    如果按钮无法点击，请复制链接到浏览器：<br>
    <a href="{reset_url}" style="color: #2563eb; word-break: break-all;">{reset_url}</a>
  </p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
  <p style="color: #94a3b8; font-size: 11px;">
    如果您没有请求重置密码，请忽略此邮件。您的账户仍然安全。
  </p>
</div>
"""


def render_password_changed_email(username: str) -> str:
    """密码已修改通知"""
    return f"""
<div style="font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1e293b; font-size: 18px; margin: 0 0 16px;">密码已修改</h2>
  <p style="color: #475569; font-size: 14px; line-height: 1.6;">
    您好 <strong>{username}</strong>，<br>
    您的密码已于刚刚成功修改。如非您本人操作，请立即联系管理员。
  </p>
</div>
"""


def render_welcome_email(username: str, login_url: str) -> str:
    """新用户欢迎邮件"""
    return f"""
<div style="font-family: -apple-system, 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; padding: 24px;">
  <h2 style="color: #1e293b; font-size: 18px; margin: 0 0 16px;">欢迎使用 Fund Analyzer</h2>
  <p style="color: #475569; font-size: 14px; line-height: 1.6;">
    您好 <strong>{username}</strong>，<br>
    您的账户已创建成功，请点击下方链接登录：
  </p>
  <div style="margin: 24px 0;">
    <a href="{login_url}" style="display: inline-block; background: #2563eb; color: white;
       padding: 10px 24px; border-radius: 6px; text-decoration: none; font-size: 14px;">
      立即登录
    </a>
  </div>
</div>
"""
