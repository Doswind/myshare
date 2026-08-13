"""应用配置"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """应用配置（从 .env 读取）"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    db_path: str = str(DATA_DIR / "fund_analyzer.db")
    scheduler_db_path: str = str(DATA_DIR / "jobs.sqlite")

    default_min_scale: float = 5.0
    default_min_ret_1y: float = 5.0
    # is_main 标记上限：5亿/5% 通过的基金中只保留按近1年收益排序的前 N 只
    # 防止基金池过大时抓持仓被限流（>1500 几乎不可行）
    max_main_funds: int = 500

    crawl_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    crawl_proxy: str = ""

    crawl_fund_hour: int = 17
    crawl_fund_minute: int = 0
    crawl_quote_interval_minutes: int = 5

    # ============ Auth / JWT / Email ============
    # JWT secret：生产环境务必通过环境变量设置
    jwt_secret: str = "fund-analyzer-dev-secret-change-me-in-production"
    jwt_access_ttl_min: int = 60 * 12      # 12 小时（前端 SPA 长会话）
    jwt_refresh_ttl_days: int = 7

    # 邮件 (QQ 邮箱 SMTP 示例；如用其他服务改 host/port)
    email_enabled: bool = False
    email_smtp_host: str = "smtp.qq.com"
    email_smtp_port: int = 465
    email_username: str = ""               # 完整邮箱
    email_password: str = ""               # SMTP 授权码（非邮箱密码）
    email_from_name: str = "Fund Analyzer"
    email_reset_ttl_min: int = 30

    # 前端地址（邮件重置链接拼接用）
    frontend_base_url: str = "http://localhost:5173"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def scheduler_db_url(self) -> str:
        return f"sqlite:///{self.scheduler_db_path}"


settings = Settings()
