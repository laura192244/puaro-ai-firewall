.PHONY: install dev test demo eval clean

install:
	python -m pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q

demo:
	python scripts/run_demo.py

eval:
	python scripts/eval.py

clean:
	rm -f data/puaro.db data/puaro.db-wal data/puaro.db-shm
