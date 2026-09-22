PY ?= python3

.PHONY: check lint dry agent report serve clean

check: lint
	$(PY) test/run_tests.py
	$(PY) -m unittest discover -s test -p 'test_*.py'

lint:
	$(PY) cli/envelope.py check examples/*.json > /dev/null && echo "envelopes ok"
	$(PY) -m py_compile contracts/retainer.py scripts/*.py cli/*.py agent/*.py && echo "python compiles"

# Rehearse the four scenarios against the local stub. Not a measurement.
dry:
	$(PY) scripts/dry_run.py

# Appraise every open brief without staking anything.
agent:
	$(PY) agent/retainer_agent.py --address $(CONTRACT) --dry

# Rebuild the published report from collected receipts. build_report refuses
# placeholder hashes, refuses an empty collection, and refuses to overwrite a
# receipt-backed report with anything weaker, so make stops rather than
# publishing a fixture as a measurement.
report:
	$(PY) scripts/collect_receipts.py runs/bradbury.jsonl --address $(CONTRACT) --out runs/records.jsonl
	$(PY) scripts/build_report.py --records runs/records.jsonl --contract $(CONTRACT) --out web/report.json

serve:
	@echo "http://localhost:8080"
	@cd web && $(PY) -m http.server 8080

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
