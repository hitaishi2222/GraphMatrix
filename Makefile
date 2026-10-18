.PHONY: install test run build clean

install:
	python -m pip install -e ".[dev]"

test:
	QT_QPA_PLATFORM=offscreen python -m pytest -q

run:
	PYTHONPATH=src python -m graphmatrix

build:
	bash packaging/build.sh

clean:
	rm -rf build dist .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
