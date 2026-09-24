from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "crypto-trading-bot"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    FRONTEND_ORIGINS: str = (
        "http://127.0.0.1:3000,http://localhost:3000"
    )
    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""
    BYBIT_DEMO: bool = True
    BOT_CONTROL_TOKEN: str = "demo-bot-control-token"
    WS_LIVE_TOKEN: str = "demo-bot-control-token"
    BOT_POLL_INTERVAL_SECONDS: float = 15.0
    SIGNAL_MAX_AGE_SECONDS: float = 900.0
    RECONCILIATION_MAX_AGE_SECONDS: float = 120.0
    RISK_PER_TRADE_PCT: str = "1"
    DAILY_LOSS_LIMIT_PCT: str = "3"
    MINIMUM_RR: str = "2"
    DEFAULT_LEVERAGE: str = "3"
    MAX_LEVERAGE: str = "10"
    MAX_ACTIVE_POSITIONS: int = 3
    MAX_OPEN_RISK_PCT: str = "3"
    FEE_BUFFER_PCT: str = "0.20"
    SLIPPAGE_BUFFER_PCT: str = "0.10"
    STRUCTURE_LOOKBACK: int = 5
    STRUCTURE_BUFFER_PCT: str = "0.10"
    EXECUTION_ENABLED: bool = True
    WS_PUBLISH_INTERVAL_SECONDS: float = 5.0
    DATABASE_PATH: str = "data/trading_bot.sqlite3"
    DATABASE_URL: str = ""
    SCANNER_MIN_TURNOVER_24H: str = "10000000"
    SCANNER_MAX_SPREAD_PCT: str = "0.10"
    SCANNER_DYNAMIC_LIMIT: int = 12
    SCANNER_COOLDOWN_MINUTES: int = 60
    # Execution candidates are selected by the scanner watchlist by default.
    # Set STATIC to use EXECUTION_SYMBOL_ALLOWLIST instead.
    EXECUTION_SELECTION_MODE: str = "SCANNER"
    EXECUTION_SYMBOL_ALLOWLIST: str = "BTCUSDT"
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    AI_MODEL: str = "qwen/qwen3.8-27b"
    AI_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_TIMEOUT_SECONDS: float = 30.0
    AI_MAX_OUTPUT_TOKENS: int = 800


    @property
    def execution_symbol_allowlist(self) -> set[str]:
        return {symbol.strip().upper() for symbol in self.EXECUTION_SYMBOL_ALLOWLIST.split(",") if symbol.strip()}

    @property
    def execution_selection_mode(self) -> str:
        mode = self.EXECUTION_SELECTION_MODE.strip().upper()
        return mode if mode in {"SCANNER", "STATIC"} else "SCANNER"

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.FRONTEND_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
