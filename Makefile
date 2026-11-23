ifeq ($(OS),Windows_NT)
  SHELL := cmd.exe
  ifneq ($(shell where.exe py 2>NUL),)
    PYTHON ?= py -3.11
  else ifneq ($(shell where.exe uv 2>NUL),)
    PYTHON ?= uv run --no-project --python 3.11 -- python
  else
    PYTHON ?= python
  endif
  VENV_PYTHON := .venv/Scripts/python.exe
else
  PYTHON ?= python3.11
  VENV_PYTHON := .venv/bin/python
endif

.DEFAULT_GOAL := setup
.PHONY: setup test lint demo sandbox-image

sandbox-image:
	docker build -t codeharness-sandbox ./sandbox

$(VENV_PYTHON):
	$(PYTHON) -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 'Python 3.11 is required')"
	$(PYTHON) -m venv .venv

setup: $(VENV_PYTHON)
	$(VENV_PYTHON) -m pip install -e ".[dev]"

test:
	$(VENV_PYTHON) -m pytest

lint:
	$(VENV_PYTHON) -m ruff check .
	$(VENV_PYTHON) -m ruff format --check .

demo:
	@echo Demo repositories are available in demo_repos. The runnable agent demo arrives in milestone 1.5.
