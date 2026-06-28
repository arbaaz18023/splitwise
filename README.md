# Splitwise Clone

A Splitwise-like expense sharing application built with FastAPI, SQLAlchemy, and async PostgreSQL/SQLite.

## Features

- User authentication (JWT + Google OAuth)
- Group management
- Expense tracking with split functionality
- Dashboard API
- Async database support

## Prerequisites

- Python 3.11+

## Setup

1. Clone the repository:
```bash
git clone <repo-url>
cd splitwise
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with required environment variables:
```env
DATABASE_URL=sqlite+aiosqlite:///./splitwise.db
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. Run database migrations:
```bash
alembic upgrade head
```

## Running the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
