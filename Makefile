.PHONY: contract contract-test contract-check contract-frontend contract-fixtures contract-all

## Run all backend contract tests
contract-test:
	PYTHONPATH=. pytest backend/tests/contract/ -v

## Check for schema drift between Pydantic model and committed snapshot
contract-check:
	python scripts/check_contract_drift.py

## Run frontend typecheck
contract-frontend:
	cd frontend && npm run typecheck

## Validate all valid contract fixtures
contract-fixtures:
	@for f in backend/tests/contract/fixtures/edge_report_valid_*.json; do \
		echo "Validating $$f ..."; \
		python scripts/validate_contract.py "$$f"; \
	done

## Re-export JSON Schema from Pydantic model
contract-export:
	python scripts/export_contract_schema.py

## Run full contract suite (backend + drift + frontend + fixtures)
contract-all: contract-test contract-check contract-frontend contract-fixtures
	@echo "All contract checks passed."
