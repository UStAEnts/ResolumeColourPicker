.PHONY: setup test run debug clean

PYTHON := .venv/bin/python
PIP := $(PYTHON) -m pip

pyproject.toml:
	touch pyproject.toml

.venv/pyvenv.cfg: 
	python3 -m venv .venv

.requirements-installed: pyproject.toml .venv/pyvenv.cfg
	$(PIP) install --upgrade pip
	$(PIP) install -e .
	touch .requirements-installed

setup: .requirements-installed

test: .requirements-installed
	$(PYTHON) -m unittest discover -s tests

run: .requirements-installed
	$(PYTHON) run.py

debug: .requirements-installed
	$(PYTHON) -X faulthandler run.py

clean:
	rm -rf .venv
	rm -f .requirements-installed
	find ./src ./tests -type f -name '*.egg-info' -exec rm {} +
	find ./src ./tests -type d -name '*.egg-info' -exec rm -r {} +
	find ./src ./tests -type d -name '__pycache__' -exec rm -r {} +