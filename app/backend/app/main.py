from collections.abc import AsyncIterator
from decimal import Decimal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.account import router as account_router
from app.api.routes.activity import router as activity_router
from app.api.routes.bot import router as bot_router
from app.api.routes.health import router as health_router
from app.api.routes.market import router as market_router
from app.api.routes.risk import router as risk_router
from app.api.routes.realtime import router as realtime_router
from app.api.routes.ai import router as ai_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.status import router as status_router
from app.api.routes.strategy import router as strategy_router
from app.account import AccountService
from app.bot.runtime import BotRuntime
from app.bot.leadership import RuntimeLeadership
from app.core.config import settings
from app.core.logging import configure_logging
from app.exchange.bybit import BybitDemoClient
from app.market_data import MarketDataService
from app.risk import RiskService
from app.execution import ExecutionService
from app.strategies import StrategyService
from app.repositories import ActivityRepository
from app.activity import ActivityService
from app.realtime import RealtimeHub
from app.realtime.publisher import LiveSnapshotPublisher
from app.persistence import PersistenceDatabase
from app.ai import AIAnalysisService
from app.api.routes.persistence import router as persistence_router

from app.scanner.engine import ScannerEngine
from app.reconciliation import ReconciliationEngine
from app.readiness import TradingReadinessService
from app.api.routes.readiness import router as readiness_router
from app.bot.block_tracker import BlockTracker
from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.strategy_lab import router as strategy_lab_router
from app.strategies.lab_service import StrategyLabService
from app.strategies.lab_workers import ICTWorker, SMCWorker, AMDWorker, LiquiditySweepWorker

configure_logging()

persistence_database = PersistenceDatabase(settings.DATABASE_PATH, database_url=settings.DATABASE_URL)
persistence_database.initialize()
exchange_client = BybitDemoClient(settings)
market_data_service = MarketDataService(exchange_client)
strategy_service = StrategyService(market_data_service)
scanner_engine = ScannerEngine(
    market_data_service,
    min_turnover=Decimal(str(settings.SCANNER_MIN_TURNOVER_24H)),
    max_spread_pct=Decimal(str(settings.SCANNER_MAX_SPREAD_PCT)),
    dynamic_limit=settings.SCANNER_DYNAMIC_LIMIT,
    cooldown_minutes=settings.SCANNER_COOLDOWN_MINUTES,
    execution_allowlist=settings.execution_symbol_allowlist,
    execution_selection_mode=settings.EXECUTION_SELECTION_MODE,
)
account_service = AccountService(exchange_client)
risk_service = RiskService(
    account_service,
    market_data_service,
    risk_per_trade_pct=Decimal(settings.RISK_PER_TRADE_PCT),
    daily_loss_limit_pct=Decimal(settings.DAILY_LOSS_LIMIT_PCT),
    minimum_rr=Decimal(settings.MINIMUM_RR),
    leverage=Decimal(settings.DEFAULT_LEVERAGE),
    max_leverage=Decimal(settings.MAX_LEVERAGE),
    max_active_positions=settings.MAX_ACTIVE_POSITIONS,
    max_open_risk_pct=Decimal(settings.MAX_OPEN_RISK_PCT),
    fee_buffer_pct=Decimal(settings.FEE_BUFFER_PCT),
    slippage_buffer_pct=Decimal(settings.SLIPPAGE_BUFFER_PCT),
    structure_lookback=settings.STRUCTURE_LOOKBACK,
    structure_buffer_pct=Decimal(settings.STRUCTURE_BUFFER_PCT),
    persistence=persistence_database,
)
execution_service = (
    ExecutionService(exchange_client, persistence_database)
    if settings.EXECUTION_ENABLED
    else None
)
activity_repository = ActivityRepository(persistence=persistence_database)
realtime_hub = RealtimeHub()
activity_service = ActivityService(exchange_client, activity_repository, persistence_database)
ai_analysis_service = AIAnalysisService(settings)

reconciliation_engine = ReconciliationEngine(
    account_service=account_service,
    exchange_client=exchange_client,
    persistence=persistence_database,
)

runtime_leadership = RuntimeLeadership(
    persistence_database.path.with_name(
        f"{persistence_database.path.name}.runtime.lock"
    )
)

block_tracker = BlockTracker()

trading_readiness_service = TradingReadinessService(
    account_service=account_service,
    reconciliation_engine=reconciliation_engine,
    persistence=persistence_database,
    runtime_leadership=runtime_leadership,
    max_signal_age_seconds=settings.SIGNAL_MAX_AGE_SECONDS,
    max_reconciliation_age_seconds=settings.RECONCILIATION_MAX_AGE_SECONDS,
)

bot_runtime = BotRuntime(
    strategy_service,
    scanner_engine=scanner_engine,
    risk_service=risk_service,
    execution_service=execution_service,
    activity_repository=activity_repository,
    activity_service=activity_service,
    realtime_hub=realtime_hub,
    persistence=persistence_database,
    reconciliation_engine=reconciliation_engine,
    trading_readiness_service=trading_readiness_service,
    runtime_leadership=runtime_leadership,
    block_tracker=block_tracker,
    poll_interval_seconds=settings.BOT_POLL_INTERVAL_SECONDS,
)
live_snapshot_publisher = LiveSnapshotPublisher(
    realtime_hub,
    market_data_service,
    account_service,
    bot_runtime,
    interval_seconds=settings.WS_PUBLISH_INTERVAL_SECONDS,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    persistence_database.initialize()
    await live_snapshot_publisher.start()
    await reconciliation_engine.reconcile()
    await block_tracker.start_daily_summary_loop()
    yield
    await live_snapshot_publisher.stop()
    await bot_runtime.shutdown()
    await block_tracker.stop()
    await exchange_client.disconnect()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.market_data_service = market_data_service
app.state.strategy_service = strategy_service
app.state.scanner_engine = scanner_engine
app.state.account_service = account_service
app.state.risk_service = risk_service
app.state.execution_service = execution_service
app.state.activity_service = activity_service
app.state.activity_repository = activity_repository
app.state.bot_runtime = bot_runtime
app.state.realtime_hub = realtime_hub
app.state.live_snapshot_publisher = live_snapshot_publisher
app.state.persistence_database = persistence_database
app.state.reconciliation_engine = reconciliation_engine
app.state.trading_readiness_service = trading_readiness_service
app.state.runtime_leadership = runtime_leadership
app.state.ai_analysis_service = ai_analysis_service
app.state.block_tracker = block_tracker

# Strategy Lab
strategy_lab_service = StrategyLabService([
    ICTWorker(market_data_service),
    SMCWorker(market_data_service),
    AMDWorker(market_data_service),
    LiquiditySweepWorker(market_data_service),
])
app.state.strategy_lab_service = strategy_lab_service

from app.api.routes.scanner import router as scanner_router

app.include_router(health_router)
app.include_router(persistence_router)
app.include_router(market_router)
app.include_router(status_router)
app.include_router(scanner_router)
app.include_router(strategy_router)
app.include_router(risk_router)
app.include_router(readiness_router)
app.include_router(realtime_router)
app.include_router(account_router)
app.include_router(activity_router)
app.include_router(bot_router)
app.include_router(integrations_router)
app.include_router(ai_router)
app.include_router(diagnostics_router)
