"""add team profiles and credentials

Revision ID: 0002_team_profiles
Revises: 0001_initial_league
Create Date: 2026-04-28
"""

from __future__ import annotations

import re
import uuid

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

revision = "0002_team_profiles"
down_revision = "0001_initial_league"
branch_labels = None
depends_on = None

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


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "squadra"


def upgrade() -> None:
    op.add_column(
        "teams", sa.Column("account_username", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "teams", sa.Column("password_hash", sa.String(length=255), nullable=True)
    )
    op.add_column("teams", sa.Column("profile_bio", sa.Text(), nullable=True))
    op.add_column("teams", sa.Column("home_city", sa.String(length=120), nullable=True))
    op.add_column(
        "teams",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "teams", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True)
    )

    bind = op.get_bind()
    teams = list(bind.execute(sa.text("SELECT id, name FROM teams ORDER BY name")))

    if not teams:
        for profile in DEFAULT_TEAM_PROFILES:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO teams (
                        id, name, account_username, password_hash, manager_name,
                        profile_bio, home_city, founded_year, is_active, created_at
                    ) VALUES (
                        :id, :name, :username, :password_hash, :manager_name,
                        :profile_bio, :home_city, :founded_year, true, now()
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "name": profile["name"],
                    "username": profile["username"],
                    "password_hash": pwd_context.hash("utente"),
                    "manager_name": profile["manager_name"],
                    "profile_bio": profile["profile_bio"],
                    "home_city": profile["home_city"],
                    "founded_year": profile["founded_year"],
                },
            )
    else:
        profiles_by_username = {
            profile["username"]: profile for profile in DEFAULT_TEAM_PROFILES
        }
        for index, team in enumerate(teams, start=1):
            username = f"squadra_{index}"
            profile = profiles_by_username.get(username)
            if profile is None:
                continue
            bind.execute(
                sa.text(
                    """
                    UPDATE teams
                    SET name = :name,
                        account_username = :username,
                        password_hash = :password_hash,
                        manager_name = :manager_name,
                        profile_bio = :profile_bio,
                        home_city = :home_city,
                        founded_year = :founded_year,
                        is_active = COALESCE(is_active, true)
                    WHERE id = :id
                    """
                ),
                {
                    "id": str(team.id),
                    "name": profile["name"],
                    "username": username,
                    "password_hash": pwd_context.hash("utente"),
                    "manager_name": profile["manager_name"],
                    "profile_bio": profile["profile_bio"],
                    "home_city": profile["home_city"],
                    "founded_year": profile["founded_year"],
                },
            )

    op.alter_column("teams", "account_username", nullable=False)
    op.alter_column("teams", "password_hash", nullable=False)
    op.create_unique_constraint(
        "uq_teams_account_username", "teams", ["account_username"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_teams_account_username", "teams", type_="unique")
    op.drop_column("teams", "last_login")
    op.drop_column("teams", "is_active")
    op.drop_column("teams", "home_city")
    op.drop_column("teams", "profile_bio")
    op.drop_column("teams", "password_hash")
    op.drop_column("teams", "account_username")
