.PHONY: all setup lint check clean

VENV = venv
PIP = $(VENV)/bin/pip
RUFF = $(VENV)/bin/ruff
MYPY = $(VENV)/bin/mypy

all: lint check

# venv oluşturur ve SADECE linter/checker araçlarını kurar
# Bağımlılıklar (requirements.txt) hata verse bile araçlar kurulur
setup:
	@echo "🔧 Setting up linting environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install ruff mypy

lint: setup
	@echo "🧹 Running linter and formatter (Ruff)..."
	@if [ -f $(RUFF) ]; then \
		$(RUFF) check app/; \
		$(RUFF) format app/; \
	else \
		echo "❌ Ruff not found. Run 'make setup' first."; \
		exit 1; \
	fi

check: setup
	@echo "🔍 Static type checking (Mypy)..."
	@if [ -f $(MYPY) ]; then \
		$(MYPY) app/; \
	else \
		echo "❌ Mypy not found. Run 'make setup' first."; \
		exit 1; \
	fi

clean:
	@echo "🗑️ Cleaning cache..."
	rm -rf .ruff_cache .mypy_cache .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +

full-clean: clean
	@echo "🗑️ Removing virtual environment..."
	rm -rf $(VENV)