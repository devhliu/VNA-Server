# Contributing to VNA

## Development Setup

1. Fork the repository
2. Install dependencies: `pip install -r vna-main-server/requirements.txt -r vna-bids-server/requirements.txt`
3. Copy `.env.example` to `.env` and configure
4. Run tests: `python -m pytest -v`

## Coding Standards

- Python 3.11+
- Type hints required for all public functions
- Use `from __future__ import annotations` in all modules
- Follow existing import ordering: stdlib → third-party → local
- Specific exception types in `except` blocks (never bare `except Exception`)
- Structured logging via `logging.getLogger(__name__)`
- No bare `pass` statements — use `logger.debug()` or raise

## Testing

- All new endpoints need tests
- Use `client` fixture (AsyncClient with SQLite in-memory)
- Mark async tests with `@pytest.mark.asyncio`
- Run: `python -m pytest -v --cov`

## Commit Messages

- Use conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- Example: `feat(projects): add project CRUD endpoints`

## Pull Request Process

1. Create feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `python -m pytest -v`
4. Update documentation if needed
5. Submit PR with clear description
