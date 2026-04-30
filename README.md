# CENA MASKIA CHAMPIONSHIP

Applicazione web full-stack per la gestione di una lega privata di Fantacalcio Mantra.

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Frontend | Angular 17+ (standalone components, signals, Tailwind CSS v4) |
| Backend | FastAPI (Python) — architettura a strati routes → services → repositories |
| Database | PostgreSQL 16 |
| Containerizzazione | Docker Compose |

## Avvio rapido (Docker)

```bash
docker compose up -d --build
```

| Servizio | URL |
|---------|-----|
| Frontend | http://localhost:4200 |
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Adminer (DB UI) | http://localhost:8080 |

## Sviluppo locale

### Backend

```bash
cd api
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

alembic upgrade head                              # Applica le migrazioni
alembic revision --autogenerate -m "descrizione"  # Crea una migrazione
pytest                                            # Esegui i test
baml-cli generate                                 # Rigenera il client BAML
```

### Frontend

```bash
cd frontend
npm install
ng serve       # http://localhost:4200
ng test
```

## Architettura backend (`api/`)

```
app/
├── api/v1/          # Route HTTP (prefix /api/v1)
│   ├── league.py    # Squadre, stagioni, classifiche, albo d'oro
│   ├── players.py   # Rosa e gestione giocatori
│   ├── trades.py    # Mercato: proposte, accettazione, rifiuto, cestino
│   ├── chatbot.py   # Assistente AI (BAML)
│   └── router.py    # Aggregazione router
├── services/        # Logica di dominio
│   ├── balance_service.py          # Validazione e calcolo bilanci Excel
│   ├── balance_guided_service.py   # Bilancio guidato (form step-by-step)
│   ├── balance_calc_service.py     # Calcoli finanziari
│   ├── trade_service.py            # Workflow trattative
│   ├── league_calendar_service.py  # Calendario e classifica
│   ├── chatbot_service.py          # Integrazione LLM
│   └── player_finance_rules.py     # Regole contratti/ingaggi
├── repositories/    # Accesso dati (BaseRepository con CRUD generico)
├── models/          # SQLAlchemy ORM (BaseModel con UUID + timestamp)
├── schemas/         # Pydantic (Create / Update / Response per entità)
├── middleware/      # Sicurezza, logging, rate limiting
├── core/            # Auth (admin token, team JWT)
└── config.py        # Settings da env (Pydantic Settings v2)
```

## Architettura frontend (`frontend/src/app/`)

```
pages/
├── home/              # Landing con accesso squadra / admin
├── profilo-squadra/   # Profilo team + dashboard personale
├── rose/              # Gestione rosa e giocatori
├── mercato/           # Trattative, cestino, ratifica admin
├── bilanci/           # Upload e compilazione guidata bilancio
├── calendario/        # Calendario partite e classifica
├── admin/             # Pannello amministratore
├── bacheca/           # Comunicazioni pubbliche
├── albo-doro/         # Storico vincitori
├── regolamento/       # Regolamento lega (da Markdown)
└── cassa/             # Cassa comune della lega
shared/
├── layout/            # Shell con sidebar e header
└── sidebar/           # Navigazione adattiva (pubblico / squadra / admin)
services/
├── league.api.ts      # Client HTTP verso il backend
├── team-session.service.ts   # Sessione squadra (JWT in localStorage)
└── admin-token.service.ts    # Token admin (localStorage)
```

## Autenticazione

| Ruolo | Meccanismo |
|-------|-----------|
| Admin | Header `X-Admin-Token: admin` |
| Squadra | Bearer JWT (ottenuto da `/api/v1/auth/team-login`) |

## Docker Compose

| Servizio | Porta | Descrizione |
|---------|-------|-------------|
| `db` | 5433:5432 | PostgreSQL 16 |
| `api` | 8000:8000 | FastAPI con hot reload |
| `frontend` | 4200:80 | Angular + nginx (proxy `/api/` → backend) |
| `adminer` | 8080:8080 | Interfaccia DB web |

## Variabili d'ambiente principali (`api/.env`)

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/app_db
ADMIN_TOKEN=admin
ANTHROPIC_API_KEY=sk-...   # Per il chatbot BAML
```

## License

MIT
