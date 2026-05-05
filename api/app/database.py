"""
Synchronous database management for FastAPI with local PostgreSQL.

This module provides:
- Synchronous SQLAlchemy engine with psycopg2 driver
- Connection pooling for local PostgreSQL
- Health check functionality with timeout protection
- Session management utilities
- Error handling and automatic recovery
- Environment-based configuration
"""

import logging
import re
import time
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Optional, Generator, Dict, Any

from sqlalchemy import create_engine, Engine, select, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DisconnectionError

from app.config import settings
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.league import (
    BalanceEntry,
    BalanceSheet,
    Fine,
    Honor,
    Season,
    Team,
    Transfer,
)

# Configure module logger
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for synchronous SQLAlchemy operations.

    Features:
    - Connection pooling with automatic recovery
    - Health checking with timeout protection
    - Thread-safe session management
    - Local PostgreSQL optimized configuration
    """

    def __init__(self):
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._is_initialized: bool = False
        self._lock = threading.RLock()
        self._last_health_check: float = 0
        self._health_check_interval: float = 30.0  # Cache health checks for 30 seconds

    def initialize(self) -> None:
        """
        Initialize the database engine and session factory.

        This method is thread-safe and can be called multiple times.
        Subsequent calls are no-ops if already initialized.
        """
        with self._lock:
            if self._is_initialized:
                logger.debug("Database already initialized")
                return

            try:
                logger.info("Initializing database connection...")
                self._create_engine()
                self._create_session_factory()
                self._test_connection()
                self._is_initialized = True
                logger.info("Database initialization successful")

            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                self._cleanup_resources()
                raise

    def _create_engine(self) -> None:
        """Create SQLAlchemy engine with standard settings."""

        # Build connection arguments for local PostgreSQL
        connect_args = self._build_connect_args()

        # Configure engine with standard settings
        engine_kwargs = {
            "url": settings.database_url,
            "poolclass": QueuePool,
            "echo": settings.database_echo,
            "connect_args": connect_args,
            "future": True,  # Use SQLAlchemy 2.0 style
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout,
            "pool_recycle": settings.database_pool_recycle,
            "pool_pre_ping": settings.database_pool_pre_ping,
            "pool_reset_on_return": settings.database_pool_reset_on_return,
        }

        self._engine = create_engine(**engine_kwargs)

        logger.info(f"Database engine created:")
        logger.info(f"  - Pool class: QueuePool")
        logger.info(f"  - Pool size: {settings.database_pool_size}")
        logger.info(f"  - Max overflow: {settings.database_max_overflow}")
        logger.info(f"  - Pool recycle: {settings.database_pool_recycle}s")
        logger.info(f"  - Pre-ping enabled: {settings.database_pool_pre_ping}")

    def _build_connect_args(self) -> Dict[str, Any]:
        """Build psycopg2-specific connection arguments."""
        connect_args = {
            "application_name": f"app-api-{settings.environment}",
            "connect_timeout": 10,  # Connection timeout in seconds
        }

        # Add keep-alive settings for stable connections
        connect_args.update(
            {
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 3,
            }
        )

        return connect_args

    def _create_session_factory(self) -> None:
        """Create thread-safe session factory."""
        if not self._engine:
            raise RuntimeError("Engine must be created before session factory")

        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,  # Explicit flushing for better control
            autocommit=False,  # Explicit transaction management
            expire_on_commit=False,  # Keep objects usable after commit
        )

        logger.debug("Session factory created")

    def _test_connection(self) -> None:
        """Test database connectivity with timeout protection."""
        if not self._engine:
            raise RuntimeError("Engine not initialized")

        try:
            with self._engine.connect() as conn:
                # Simple connectivity test
                result = conn.execute(text("SELECT 1 as test_connection"))
                row = result.fetchone()

                if row is None or row[0] != 1:
                    raise RuntimeError("Database connection test failed")

                logger.debug("Database connection test passed")

        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            raise

    def health_check(self) -> bool:
        """
        Perform database health check with caching and timeout protection.

        Returns:
            bool: True if database is healthy, False otherwise
        """
        current_time = time.time()

        # Use cached result if recent
        if (current_time - self._last_health_check) < self._health_check_interval:
            logger.debug("Using cached health check result")
            return True

        if not self._is_initialized:
            logger.warning("Health check failed: Database not initialized")
            return False

        try:
            with self.get_session() as session:
                # Quick health check query
                result = session.execute(text("SELECT 1 as health_check"))
                row = result.fetchone()

                if row is not None and row[0] == 1:
                    self._last_health_check = current_time
                    logger.debug("Database health check passed")
                    return True
                else:
                    logger.warning("Database health check returned unexpected value")
                    return False

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed database status information for monitoring.

        Returns:
            Dict with connection pool status, health, and configuration info
        """
        status = {
            "initialized": self._is_initialized,
            "engine_created": self._engine is not None,
            "pool_class": (
                self._engine.pool.__class__.__name__ if self._engine else None
            ),
            "healthy": False,
            "last_health_check": self._last_health_check,
            "configuration": {
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_timeout": settings.database_pool_timeout,
                "pool_recycle": settings.database_pool_recycle,
                "environment": settings.environment,
            },
        }

        if self._engine and hasattr(self._engine.pool, "status"):
            try:
                # pool.status() returns a formatted string
                pool_status_str = self._engine.pool.status()

                # Access pool attributes directly (they're properties, not methods)
                pool_info = {
                    "status_string": pool_status_str,
                }

                status["pool_status"] = pool_info
            except Exception as e:
                logger.debug(f"Could not get pool status: {e}")
                status["pool_status"] = "unavailable"

        # Perform health check
        status["healthy"] = self.health_check()

        return status

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session with automatic error handling and cleanup.

        This context manager provides:
        - Automatic session creation and cleanup
        - Connection error recovery
        - Transaction rollback on exceptions
        - Thread-safe operation

        Yields:
            Session: SQLAlchemy database session

        Raises:
            RuntimeError: If database is not initialized
            SQLAlchemyError: For database-related errors
        """
        if not self._is_initialized or not self._session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        session = self._session_factory()

        try:
            yield session

        except (DisconnectionError, OperationalError) as e:
            logger.error(f"Database connection error: {e}")
            session.rollback()

            # Attempt to recover by invalidating the connection
            try:
                session.connection().invalidate()
            except Exception as recovery_error:
                logger.debug(f"Connection invalidation failed: {recovery_error}")

            raise

        except SQLAlchemyError as e:
            logger.error(f"Database error: {e}")
            session.rollback()
            raise

        except Exception as e:
            logger.error(f"Unexpected error in database session: {e}")
            session.rollback()
            raise

        finally:
            try:
                session.close()
            except Exception as e:
                logger.debug(f"Error closing session: {e}")

    def create_all_tables(self) -> None:
        """
        Create all database tables defined in models.

        This method is safe to call multiple times.
        """
        if not self._engine:
            raise RuntimeError("Database engine not initialized")

        try:
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=self._engine)
            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    def close(self) -> None:
        """
        Cleanup database resources.

        This method is thread-safe and can be called multiple times.
        """
        with self._lock:
            if not self._is_initialized:
                return

            try:
                self._cleanup_resources()
                logger.info("Database connection closed successfully")

            except Exception as e:
                logger.error(f"Error during database cleanup: {e}")

    def _cleanup_resources(self) -> None:
        """Internal method to cleanup database resources."""
        if self._engine:
            try:
                self._engine.dispose()
                logger.debug("Database engine disposed")
            except Exception as e:
                logger.debug(f"Error disposing engine: {e}")
            finally:
                self._engine = None

        self._session_factory = None
        self._is_initialized = False
        self._last_health_check = 0

    @property
    def is_initialized(self) -> bool:
        """Check if database is initialized and ready for use."""
        return self._is_initialized

    @property
    def engine(self) -> Optional[Engine]:
        """Get the SQLAlchemy engine (for advanced use cases)."""
        return self._engine


# Global database manager instance
database_manager = DatabaseManager()

DEFAULT_TEAM_PROFILES = [
    {
        "username": "squadra_1",
        "name": "Atletico Navigli",
        "manager_name": "Lorenzo Valli",
        "home_city": "Milano",
        "founded_year": 2017,
        "profile_bio": "Squadra tecnica e paziente, costruita su possesso palla, rotazioni corte e una forte attenzione alle plusvalenze.",
    },
    {
        "username": "squadra_2",
        "name": "Borgo Vittoria FC",
        "manager_name": "Matteo Ferraris",
        "home_city": "Torino",
        "founded_year": 2016,
        "profile_bio": "Rosa intensa e pragmatica: priorita alla solidita difensiva, bonus da panchina e gestione rigorosa del budget.",
    },
    {
        "username": "squadra_3",
        "name": "Calabra United",
        "manager_name": "Antonio Greco",
        "home_city": "Reggio Calabria",
        "founded_year": 2018,
        "profile_bio": "Club aggressivo sul mercato di riparazione, specializzato nel rilancio di scommesse offensive e scambi mirati.",
    },
    {
        "username": "squadra_4",
        "name": "Laguna Verde",
        "manager_name": "Filippo Trevisan",
        "home_city": "Venezia",
        "founded_year": 2019,
        "profile_bio": "Progetto giovane e creativo, con impostazione analitica, grande attenzione ai calendari e ricerca costante di titolari low cost.",
    },
    {
        "username": "squadra_5",
        "name": "Leonessa Brescia",
        "manager_name": "Davide Rinaldi",
        "home_city": "Brescia",
        "founded_year": 2015,
        "profile_bio": "Identita da squadra di carattere: pochi fronzoli, titolarissimi affidabili e costruzione del punteggio sui dettagli.",
    },
    {
        "username": "squadra_6",
        "name": "Maremma Calcio",
        "manager_name": "Riccardo Bassi",
        "home_city": "Grosseto",
        "founded_year": 2020,
        "profile_bio": "Societa emergente che punta su valore e continuita, con una strategia orientata a sostenibilita e crescita progressiva.",
    },
    {
        "username": "squadra_7",
        "name": "Partenopei 94",
        "manager_name": "Gennaro Esposito",
        "home_city": "Napoli",
        "founded_year": 2014,
        "profile_bio": "Squadra ad alto tasso di bonus, costruita per attaccare sempre e massimizzare il potenziale dei reparti offensivi.",
    },
    {
        "username": "squadra_8",
        "name": "Porta Romana",
        "manager_name": "Simone Colombo",
        "home_city": "Milano",
        "founded_year": 2021,
        "profile_bio": "Roster moderno e molto flessibile, con focus su multi-ruolo, minutaggio e lettura settimanale delle partite chiave.",
    },
    {
        "username": "squadra_9",
        "name": "Riviera del Conero",
        "manager_name": "Marco Anselmi",
        "home_city": "Ancona",
        "founded_year": 2017,
        "profile_bio": "Club equilibrato che alterna gestione prudente e colpi improvvisi, particolarmente forte nella valorizzazione del centrocampo.",
    },
    {
        "username": "squadra_10",
        "name": "Stella Apuana",
        "manager_name": "Niccolo Marchetti",
        "home_city": "Massa",
        "founded_year": 2016,
        "profile_bio": "Storica outsider della lega: struttura ordinata, lettura tattica pulita e massima attenzione a disciplinari e sanzioni.",
    },
]


def _slugify_username(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "squadra"


def seed_default_teams() -> None:
    with database_manager.get_session() as session:
        existing_count = session.execute(select(Team)).scalars().first()
        if existing_count is not None:
            return

        for profile in DEFAULT_TEAM_PROFILES:
            session.add(
                Team(
                    name=profile["name"],
                    account_username=profile["username"],
                    password_hash=get_password_hash(settings.team_shared_password),
                    manager_name=profile["manager_name"],
                    profile_bio=profile["profile_bio"],
                    home_city=profile["home_city"],
                    founded_year=profile["founded_year"],
                    is_active=True,
                )
            )
        session.commit()
        logger.info("Seeded 10 default team profiles")


def seed_demo_team_activity() -> None:
    with database_manager.get_session() as session:
        team = session.execute(
            select(Team).where(Team.account_username == "squadra_1")
        ).scalar_one_or_none()
        if team is None:
            return

        seasons_payload = [
            {"name": "2023/24", "is_current": False},
            {"name": "2024/25", "is_current": False},
            {"name": "2025/26", "is_current": True},
        ]
        seasons_by_name: dict[str, Season] = {}
        for payload in seasons_payload:
            season = session.execute(
                select(Season).where(Season.name == payload["name"])
            ).scalar_one_or_none()
            if season is None:
                season = Season(name=payload["name"], is_current=payload["is_current"])
                session.add(season)
                session.flush()
            seasons_by_name[payload["name"]] = season
        current_season = seasons_by_name["2025/26"]
        for season in session.execute(select(Season)).scalars().all():
            season.is_current = season.id == current_season.id

        balances_payload = [
            {
                "season": "2023/24",
                "status": "submitted",
                "submitted_at": datetime(2024, 5, 26, 18, 30, tzinfo=timezone.utc),
                "total_ricavi": 122.0,
                "total_costi": 129.0,
                "total_ammortamenti": 6.5,
                "total_plus_minus": 4.0,
                "utile": -9.5,
                "sanction_level": "light",
                "sanction_points": 1,
                "sanction_notes": "Stagione chiusa in lieve perdita, recuperata solo in parte dal mercato estivo.",
                "entries": [
                    ("ricavi", "Premi piazzamento campionato", 44.0),
                    ("ricavi", "Premi coppa", 18.0),
                    ("ricavi", "Bonus giornata", 22.0),
                    ("costi", "Asta estiva", 76.0),
                    ("costi", "Mercato di gennaio", 25.0),
                    ("costi", "Penali e commissioni", 8.0),
                    ("ammortamenti", "Valorizzazione giovani", 6.5),
                    ("plus_minus", "Cessione Holm", 4.0),
                ],
            },
            {
                "season": "2024/25",
                "status": "submitted",
                "submitted_at": datetime(2025, 5, 25, 19, 15, tzinfo=timezone.utc),
                "total_ricavi": 156.0,
                "total_costi": 137.5,
                "total_ammortamenti": 8.0,
                "total_plus_minus": 11.0,
                "utile": 21.5,
                "sanction_level": "none",
                "sanction_points": 0,
                "sanction_notes": "Bilancio molto solido grazie a premi ricorrenti e ottima gestione del mercato invernale.",
                "entries": [
                    ("ricavi", "Premio secondo posto", 52.0),
                    ("ricavi", "Premio fair play", 11.0),
                    ("ricavi", "Bonus gol e assist", 29.0),
                    ("costi", "Asta iniziale", 79.0),
                    ("costi", "Acquisti di riparazione", 19.5),
                    ("costi", "Rinnovi e fee", 7.0),
                    ("ammortamenti", "Progetto cantera", 8.0),
                    ("plus_minus", "Cessione Orsolini", 11.0),
                ],
            },
            {
                "season": "2025/26",
                "status": "submitted",
                "submitted_at": datetime(2026, 4, 22, 21, 0, tzinfo=timezone.utc),
                "total_ricavi": 148.0,
                "total_costi": 132.0,
                "total_ammortamenti": 9.5,
                "total_plus_minus": 6.0,
                "utile": 12.5,
                "sanction_level": "none",
                "sanction_points": 0,
                "sanction_notes": "Bilancio in regola: margine positivo e struttura costi sotto controllo.",
                "entries": [
                    ("ricavi", "Premio giornata 12", 18.0),
                    ("ricavi", "Premio classifica parziale", 32.0),
                    ("ricavi", "Bonus coppa di lega", 14.0),
                    ("ricavi", "Sponsor tecnico di lega", 16.0),
                    ("costi", "Aste iniziali", 74.0),
                    ("costi", "Mercato di riparazione", 21.0),
                    ("costi", "Commissioni scambi", 6.0),
                    ("costi", "Premi staff e consulenza", 5.0),
                    ("ammortamenti", "Quota rosa primavera", 9.5),
                    ("plus_minus", "Plusvalenza cessione Raspadori", 6.0),
                ],
            },
        ]
        for payload in balances_payload:
            season = seasons_by_name[payload["season"]]
            balance = session.execute(
                select(BalanceSheet).where(
                    BalanceSheet.team_id == team.id,
                    BalanceSheet.season_id == season.id,
                )
            ).scalar_one_or_none()
            if balance is None:
                balance = BalanceSheet(team_id=team.id, season_id=season.id)
                session.add(balance)
                session.flush()
            balance.status = payload["status"]
            balance.submitted_at = payload["submitted_at"]
            balance.total_ricavi = payload["total_ricavi"]
            balance.total_costi = payload["total_costi"]
            balance.total_ammortamenti = payload["total_ammortamenti"]
            balance.total_plus_minus = payload["total_plus_minus"]
            balance.utile = payload["utile"]
            balance.sanction_level = payload["sanction_level"]
            balance.sanction_points = payload["sanction_points"]
            balance.sanction_notes = payload["sanction_notes"]
            balance.file_url = None
            existing_entries = (
                session.execute(
                    select(BalanceEntry).where(
                        BalanceEntry.balance_sheet_id == balance.id
                    )
                )
                .scalars()
                .all()
            )
            if not existing_entries:
                for section, label, amount in payload["entries"]:
                    session.add(
                        BalanceEntry(
                            balance_sheet_id=balance.id,
                            section=section,
                            label=label,
                            amount=amount,
                        )
                    )

        fines_payload = [
            {
                "season": "2023/24",
                "reason": "Ritardo consegna formazione alla 4a giornata",
                "amount": 5.0,
                "paid": True,
                "fine_date": date(2023, 10, 1),
            },
            {
                "season": "2024/25",
                "reason": "Cambio modulo comunicato oltre la scadenza",
                "amount": 3.0,
                "paid": True,
                "fine_date": date(2024, 12, 15),
            },
            {
                "season": "2025/26",
                "reason": "Referto incompleto nel mercato di gennaio",
                "amount": 7.0,
                "paid": False,
                "fine_date": date(2026, 1, 21),
            },
            {
                "season": "2025/26",
                "reason": "Consegna tardiva distinta primavera",
                "amount": 2.0,
                "paid": True,
                "fine_date": date(2026, 2, 3),
            },
        ]
        for payload in fines_payload:
            season = seasons_by_name[payload["season"]]
            fine = session.execute(
                select(Fine).where(
                    Fine.team_id == team.id,
                    Fine.season_id == season.id,
                    Fine.reason == payload["reason"],
                )
            ).scalar_one_or_none()
            if fine is None:
                session.add(
                    Fine(
                        season_id=season.id,
                        team_id=team.id,
                        reason=payload["reason"],
                        amount=payload["amount"],
                        paid=payload["paid"],
                        fine_date=payload["fine_date"],
                    )
                )

        honors_payload = [
            {
                "season": "2023/24",
                "trophy": "Coppa Manager",
                "position": 2,
                "notes": "Finalista con il miglior punteggio cumulato nelle semifinali.",
            },
            {
                "season": "2024/25",
                "trophy": "Coppa d'autunno",
                "position": 1,
                "notes": "Miglior rendimento nelle prime 10 giornate.",
            },
            {
                "season": "2024/25",
                "trophy": "Campionato Mantra",
                "position": 2,
                "notes": "Secondo posto deciso all'ultima giornata.",
            },
            {
                "season": "2025/26",
                "trophy": "Supercoppa di lega",
                "position": 1,
                "notes": "Successo ai rigori nella finale di apertura stagione.",
            },
        ]
        for payload in honors_payload:
            season = seasons_by_name[payload["season"]]
            honor = session.execute(
                select(Honor).where(
                    Honor.team_id == team.id,
                    Honor.season_id == season.id,
                    Honor.trophy == payload["trophy"],
                )
            ).scalar_one_or_none()
            if honor is None:
                session.add(
                    Honor(
                        season_id=season.id,
                        team_id=team.id,
                        trophy=payload["trophy"],
                        position=payload["position"],
                        notes=payload["notes"],
                    )
                )

        transfers_payload = [
            {
                "season": "2023/24",
                "direction": "in",
                "player_name": "Albert Gudmundsson",
                "fee": 24.0,
                "type": "acquisto",
                "transfer_date": date(2023, 9, 2),
                "notes": "Colpo chiave di inizio stagione per alzare il numero di bonus offensivi.",
            },
            {
                "season": "2023/24",
                "direction": "out",
                "player_name": "Andrea Pinamonti",
                "fee": 17.0,
                "type": "cessione",
                "transfer_date": date(2024, 1, 14),
                "notes": "Operazione usata per riequilibrare budget e slot in attacco.",
            },
            {
                "season": "2024/25",
                "direction": "in",
                "player_name": "Joshua Zirkzee",
                "fee": 31.0,
                "type": "acquisto",
                "transfer_date": date(2024, 8, 30),
                "notes": "Innesto premium scelto come riferimento centrale del reparto offensivo.",
            },
            {
                "season": "2024/25",
                "direction": "out",
                "player_name": "Riccardo Orsolini",
                "fee": 22.0,
                "type": "cessione",
                "transfer_date": date(2025, 1, 10),
                "notes": "Vendita strategica per finanziare due acquisti mirati in mediana.",
            },
            {
                "season": "2024/25",
                "direction": "in",
                "player_name": "Teun Koopmeiners",
                "fee": 28.0,
                "type": "acquisto",
                "transfer_date": date(2025, 1, 12),
                "notes": "Acquisto di equilibrio per alzare rendimento e calci piazzati.",
            },
            {
                "season": "2025/26",
                "direction": "in",
                "player_name": "Matias Soule",
                "fee": 27.0,
                "type": "acquisto",
                "transfer_date": date(2025, 8, 29),
                "notes": "Inserito per aumentare il potenziale bonus sugli esterni.",
            },
            {
                "season": "2025/26",
                "direction": "out",
                "player_name": "Andrea Colpani",
                "fee": 19.0,
                "type": "cessione",
                "transfer_date": date(2026, 1, 18),
                "notes": "Operazione chiusa per liberare budget e finanziare il mercato di gennaio.",
            },
            {
                "season": "2025/26",
                "direction": "in",
                "player_name": "Matteo Politano",
                "fee": 16.0,
                "type": "scambio",
                "transfer_date": date(2026, 1, 20),
                "notes": "Scambio a due per aggiungere esperienza e affidabilita sulle fasce.",
            },
        ]
        for payload in transfers_payload:
            season = seasons_by_name[payload["season"]]
            transfer = session.execute(
                select(Transfer).where(
                    Transfer.season_id == season.id,
                    Transfer.player_name == payload["player_name"],
                    Transfer.type == payload["type"],
                )
            ).scalar_one_or_none()
            if transfer is None:
                session.add(
                    Transfer(
                        season_id=season.id,
                        from_team_id=team.id if payload["direction"] == "out" else None,
                        to_team_id=team.id if payload["direction"] == "in" else None,
                        player_name=payload["player_name"],
                        fee=payload["fee"],
                        type=payload["type"],
                        transfer_date=payload["transfer_date"],
                        notes=payload["notes"],
                    )
                )

        session.commit()
        logger.info("Seeded demo activity for squadra_1")


def init_db() -> None:
    """
    Initialize database connection and create tables.

    This function is called during application startup.
    It's safe to call multiple times.
    """
    try:
        logger.info("Initializing database system...")

        # Initialize connection
        database_manager.initialize()

        # Create tables if they don't exist
        database_manager.create_all_tables()

        logger.info("Database system initialized successfully")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

        # In development mode, we want to continue even if DB fails
        if settings.is_development:
            logger.warning("Continuing in development mode despite database errors")
            return

        # In production, database failure should stop the application
        raise


def close_db() -> None:
    """
    Close database connections and cleanup resources.

    This function is called during application shutdown.
    It's safe to call multiple times.
    """
    try:
        logger.info("Closing database connections...")
        database_manager.close()
        logger.info("Database connections closed successfully")

    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    This function provides database sessions to FastAPI route handlers
    with automatic cleanup and error handling.

    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    Yields:
        Session: SQLAlchemy database session
    """
    with database_manager.get_session() as session:
        yield session


def get_db_status() -> Dict[str, Any]:
    """
    Get comprehensive database status information.

    Returns:
        Dict containing database health, configuration, and pool status
    """
    return database_manager.get_detailed_status()


# Utility functions for common database operations


def execute_raw_sql(sql: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
    """
    Execute raw SQL with parameter binding.

    Args:
        sql: SQL query string
        parameters: Optional parameters for the query

    Returns:
        Query result

    Raises:
        RuntimeError: If database is not initialized
        SQLAlchemyError: For database errors
    """
    with database_manager.get_session() as session:
        if parameters:
            result = session.execute(text(sql), parameters)
        else:
            result = session.execute(text(sql))

        if not sql.strip().upper().startswith(("SELECT", "SHOW", "EXPLAIN")):
            session.commit()
        return result


def test_database_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        return database_manager.health_check()
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


# Context manager for manual transaction management
@contextmanager
def database_transaction() -> Generator[Session, None, None]:
    """
    Context manager for explicit transaction handling.

    Usage:
        with database_transaction() as session:
            user = User(name="John")
            session.add(user)
            # Transaction automatically committed on success
            # or rolled back on exception

    Yields:
        Session: Database session with explicit transaction control
    """
    with database_manager.get_session() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# Export commonly used items
__all__ = [
    "database_manager",
    "init_db",
    "close_db",
    "get_db",
    "get_db_status",
    "execute_raw_sql",
    "test_database_connection",
    "database_transaction",
    "DatabaseManager",
]
