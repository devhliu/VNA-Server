.PHONY: test test-unit test-integration test-e2e test-main test-dicom test-bids setup

# ---------------------------------------------------------------------------
# Test targets
# ---------------------------------------------------------------------------

test: test-unit

test-unit:
	rm -f .pytest-vna-main-*.db vna_main_test.db vna_main.db
	pip install -q -r vna-main-server/requirements.txt
	PYTHONPATH=vna-main-server pytest tests/test_main_server.py -v --tb=short -q
	cd vna-dicom-sdk && pip install -q -e . && pytest tests/ -v --tb=short -q
	cd vna-bids-sdk && pip install -q -e '.[dev]' && pytest tests/ -v --tb=short -q

test-integration:
	docker compose up -d --quiet-pull
	bash scripts/wait-for-http.sh --host localhost --port 8000 --timeout 60 --path / -- echo "Main server ready"
	bash scripts/wait-for-http.sh --host localhost --port 8042 --timeout 60 --path /system -- echo "Orthanc ready"
	ORTHANC_URL=http://localhost:8042 \
	MAIN_SERVER_URL=http://localhost:8000 \
	BIDS_SERVER_URL=http://localhost:8080 \
	pytest tests/test_e2e.py -v -m integration --tb=short
	docker compose down

test-main:
	cd vna-main-server && pytest tests/ -v --tb=short -q

test-dicom:
	cd vna-dicom-sdk && pytest tests/ -v --tb=short -q

test-bids:
	cd vna-bids-sdk && pytest tests/ -v --tb=short -q

test-e2e:
	docker compose up -d
	bash scripts/wait-for-http.sh --host localhost --port 18000 --timeout 60 --path /v1/internal/status -- echo "Main server ready"
	bash scripts/wait-for-http.sh --host localhost --port 18042 --timeout 60 --path /system -- echo "Orthanc ready"
	bash scripts/wait-for-http.sh --host localhost --port 18080 --timeout 60 --path /health -- echo "BIDS server ready"
	ORTHANC_URL=http://localhost:18042 \
	MAIN_SERVER_URL=http://localhost:18000 \
	BIDS_SERVER_URL=http://localhost:18080 \
	pytest tests/test_e2e.py -v --tb=short
	docker compose down

test-all:
	$(MAKE) test-unit
	$(MAKE) test-integration

# ---------------------------------------------------------------------------
# Dev helpers
# ---------------------------------------------------------------------------

setup:
	pip install -r vna-main-server/requirements.txt
	pip install -e vna-dicom-sdk
	pip install -e 'vna-bids-sdk[dev]'
	pip install pytest pytest-asyncio httpx aiosqlite

lint:
	cd vna-main-server && ruff check .
	cd vna-bids-server && ruff check .
	cd vna-dicom-sdk && ruff check .
	cd vna-bids-sdk && ruff check .

fmt:
	cd vna-main-server && ruff format .
	cd vna-bids-server && ruff format .
	cd vna-dicom-sdk && ruff format .
	cd vna-bids-sdk && ruff format .

# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v

docker-logs:
	docker compose logs -f

docker-restart: docker-down docker-up
