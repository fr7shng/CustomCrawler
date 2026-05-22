.PHONY: help setup lint format clean test docker

help:
	@echo "Usage: make <target>"
	@echo "Targets: setup lint format clean test docker scrape generate admin daemon stats"

setup:
	pip install -r requirements.txt
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache *.egg-info build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log

test:
	pytest tests/ -v

docker:
	docker build -t github-trending-scraper .

scrape:
	python main.py --scrape

generate:
	python main.py --generate

admin:
	python main.py --admin

daemon:
	python main.py --daemon

stats:
	python main.py --stats
