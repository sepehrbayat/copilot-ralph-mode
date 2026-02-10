# Copilot Ralph Mode - Makefile
# ==============================
#
# Quick commands for development and usage
#
# Usage:
#   make install    - Install Ralph Mode
#   make test       - Run all tests
#   make help       - Show all commands
#

.PHONY: help install install-dev test test-fast test-coverage lint format clean build publish typecheck

# Default target
help:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════╗"
	@echo "║   🔄 Copilot Ralph Mode - Available Commands              ║"
	@echo "╚═══════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  Installation:"
	@echo "    make install        Install Ralph Mode (no dependencies needed)"
	@echo "    make install-dev    Install with development dependencies"
	@echo ""
	@echo "  Testing:"
	@echo "    make test           Run all tests"
	@echo "    make test-fast      Run tests without property-based (faster)"
	@echo "    make test-coverage  Run tests with coverage report"
	@echo ""
	@echo "  Code Quality:"
	@echo "    make lint           Check code quality"
	@echo "    make format         Format code with black"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make clean          Remove temporary files"
	@echo ""
	@echo "  Ralph Mode Commands:"
	@echo "    python ralph_mode.py enable \"Your task\" --max-iterations 20"
	@echo "    python ralph_mode.py status"
	@echo "    python ralph_mode.py disable"
	@echo ""

# Installation
install:
	pip install -e .
	@echo ""
	@echo "✅ Ralph Mode installed!"
	@echo "Run: ralph-mode enable \"Your task\""

install-dev:
	@echo "Installing development dependencies..."
	pip install -e ".[dev]"
	@echo "✅ Development environment ready"

# Testing
test:
	python -m pytest tests/ -v --tb=short

test-fast:
	python -m pytest tests/test_ralph_mode.py tests/test_cross_platform.py -v --tb=short

test-coverage:
	python -m pytest tests/ --cov=ralph_mode --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report: htmlcov/index.html"

test-advanced:
	python -m pytest tests/test_advanced.py -v --tb=short

# Code Quality
lint:
	@echo "Running flake8..."
	-flake8 ralph_mode/ --max-line-length=120 --statistics
	@echo ""
	@echo "Running mypy..."
	-mypy ralph_mode/ --ignore-missing-imports

format:
	@echo "Formatting with black..."
	black ralph_mode/ tests/ ralph_mode.py
	@echo ""
	@echo "Sorting imports with isort..."
	isort ralph_mode/ tests/ ralph_mode.py

format-check:
	black --check ralph_mode/ tests/ ralph_mode.py
	isort --check-only ralph_mode/ tests/ ralph_mode.py

# Maintenance
clean:
	@echo "Cleaning temporary files..."
	rm -rf __pycache__ .pytest_cache .mypy_cache .coverage htmlcov
	rm -rf *.egg-info build dist
	rm -rf .ralph-mode
	rm -rf .hypothesis/tmp
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "✅ Clean"

# Quick start commands
enable:
	@echo "Usage: python ralph_mode.py enable \"Your task description\""
	@echo ""
	@echo "Options:"
	@echo "  --max-iterations N     Set max iterations (0=unlimited)"
	@echo "  --completion-promise T  Text to match for completion"
	@echo "  --auto-agents          Enable dynamic agent creation"

status:
	python ralph_mode.py status

disable:
	python ralph_mode.py disable

# Development
dev-setup: install-dev
	@echo "Setting up pre-commit hooks..."
	@echo "✅ Development environment ready"

# Docker (for CI testing)
docker-test:
	docker run --rm -v "$$(pwd):/app" -w /app python:3.11 python -m pytest tests/ -v

# Build & Publish
build: clean
	python -m build
	@echo "✅ Build artifacts in dist/"

publish: build
	python -m twine upload dist/*

publish-test: build
	python -m twine upload --repository testpypi dist/*

# Type checking
typecheck:
	mypy ralph_mode/ --strict --ignore-missing-imports
