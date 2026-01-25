# LangSmith Thread Analyzer - Makefile
# =====================================
# Hybrid Local-Cloud QA Pipeline

# Load .env file if it exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: help install install-dev lint format typecheck test test-unit test-integration build deploy-dev deploy-staging deploy-prod local-api clean package publish publish-test

# Python environment
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest

# SAM settings
SAM := sam
SAM_DIR := cloud
STACK_NAME_DEV := geniable-dev
STACK_NAME_STAGING := geniable-staging
STACK_NAME_PROD := geniable-prod

# Default target
help:
	@echo "LangSmith Thread Analyzer - Hybrid Local-Cloud QA Pipeline"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Quality:"
	@echo "  lint             Run linting (ruff)"
	@echo "  format           Format code (black + isort)"
	@echo "  typecheck        Run type checking (mypy)"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests only"
	@echo "  test-integration Run integration tests"
	@echo "  test-cov         Run tests with coverage report"
	@echo ""
	@echo "Build & Deploy (Cloud):"
	@echo "  build            Build SAM application"
	@echo "  validate         Validate SAM template"
	@echo "  deploy-dev       Deploy to dev environment"
	@echo "  deploy-staging   Deploy to staging environment"
	@echo "  deploy-prod      Deploy to production environment"
	@echo "  local-api        Start local API for testing"
	@echo ""
	@echo "Build & Deploy (PyPI):"
	@echo "  package          Build Python package for PyPI"
	@echo "  publish-test     Publish to TestPyPI"
	@echo "  publish          Publish to PyPI (production)"
	@echo ""
	@echo "CLI:"
	@echo "  cli-configure    Show CLI configuration"
	@echo "  cli-status       Show system status"
	@echo "  cli-discover     Discover evaluation tools"
	@echo "  cli-run          Run analysis (dry-run mode)"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean            Clean build artifacts"
	@echo ""
	@echo "Utilities:"
	@echo "  outputs-dev      Show CloudFormation outputs (dev)"
	@echo "  logs-integration Tail Integration Service logs"
	@echo "  logs-evaluation  Tail Evaluation Service logs"

# =============================================================================
# Setup
# =============================================================================
install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"
	pre-commit install || true

# =============================================================================
# Quality
# =============================================================================
lint:
	ruff check cli agent shared tests

format:
	black cli agent shared tests cloud
	isort cli agent shared tests cloud

typecheck:
	mypy cli agent shared

# =============================================================================
# Testing
# =============================================================================
test:
	$(PYTEST) tests/ -v

test-unit:
	$(PYTEST) tests/ -v -m "unit"

test-integration:
	$(PYTEST) tests/ -v -m "integration"

test-cov:
	$(PYTEST) tests/ -v --cov=cli --cov=agent --cov=shared --cov-report=html:reports/coverage --cov-report=term-missing

# =============================================================================
# Build & Deploy
# =============================================================================
validate:
	cd $(SAM_DIR) && $(SAM) validate --lint

build:
	cd $(SAM_DIR) && $(SAM) build

deploy-dev: validate build
	@if [ -z "$(LANGSMITH_API_KEY)" ]; then echo "Error: LANGSMITH_API_KEY not set"; exit 1; fi
	cd $(SAM_DIR) && $(SAM) deploy \
		--config-env dev \
		--parameter-overrides \
			LangSmithApiKey='$(LANGSMITH_API_KEY)' \
			LangSmithProject='$(LANGSMITH_PROJECT)' \
			LangSmithQueue='$(LANGSMITH_QUEUE)' \
			IssueProvider='$(ISSUE_PROVIDER)' \
			JiraBaseUrl='$(JIRA_BASE_URL)' \
			JiraEmail='$(JIRA_EMAIL)' \
			JiraApiToken='$(JIRA_API_TOKEN)' \
			JiraProjectKey='$(JIRA_PROJECT_KEY)' \
			NotionApiKey='$(NOTION_API_KEY)' \
			NotionDatabaseId='$(NOTION_DATABASE_ID)'

deploy-staging: validate build
	@if [ -z "$(LANGSMITH_API_KEY)" ]; then echo "Error: LANGSMITH_API_KEY not set"; exit 1; fi
	cd $(SAM_DIR) && $(SAM) deploy \
		--config-env staging \
		--parameter-overrides \
			LangSmithApiKey='$(LANGSMITH_API_KEY)' \
			LangSmithProject='$(LANGSMITH_PROJECT)' \
			LangSmithQueue='$(LANGSMITH_QUEUE)' \
			IssueProvider='$(ISSUE_PROVIDER)' \
			JiraBaseUrl='$(JIRA_BASE_URL)' \
			JiraEmail='$(JIRA_EMAIL)' \
			JiraApiToken='$(JIRA_API_TOKEN)' \
			JiraProjectKey='$(JIRA_PROJECT_KEY)' \
			NotionApiKey='$(NOTION_API_KEY)' \
			NotionDatabaseId='$(NOTION_DATABASE_ID)'

deploy-prod: validate build
	@if [ -z "$(LANGSMITH_API_KEY)" ]; then echo "Error: LANGSMITH_API_KEY not set"; exit 1; fi
	@echo "Deploying to PRODUCTION. Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]
	cd $(SAM_DIR) && $(SAM) deploy \
		--config-env prod \
		--parameter-overrides \
			LangSmithApiKey='$(LANGSMITH_API_KEY)' \
			LangSmithProject='$(LANGSMITH_PROJECT)' \
			LangSmithQueue='$(LANGSMITH_QUEUE)' \
			IssueProvider='$(ISSUE_PROVIDER)' \
			JiraBaseUrl='$(JIRA_BASE_URL)' \
			JiraEmail='$(JIRA_EMAIL)' \
			JiraApiToken='$(JIRA_API_TOKEN)' \
			JiraProjectKey='$(JIRA_PROJECT_KEY)' \
			NotionApiKey='$(NOTION_API_KEY)' \
			NotionDatabaseId='$(NOTION_DATABASE_ID)'

local-api: build
	cd $(SAM_DIR) && $(SAM) local start-api --warm-containers EAGER

# =============================================================================
# PyPI Package
# =============================================================================
package: clean
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

publish-test: package
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine upload --repository testpypi dist/*

publish: package
	@echo "Publishing to PyPI (production). Are you sure? [y/N]" && read ans && [ $${ans:-N} = y ]
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine upload dist/*

# =============================================================================
# CLI Commands
# =============================================================================
cli-configure:
	$(PYTHON) -m cli configure --show

cli-status:
	$(PYTHON) -m cli status

cli-discover:
	$(PYTHON) -m cli discover

cli-run:
	$(PYTHON) -m cli run --dry-run --verbose

cli-version:
	$(PYTHON) -m cli version

# =============================================================================
# Cleanup
# =============================================================================
clean:
	rm -rf .aws-sam/
	rm -rf $(SAM_DIR)/.aws-sam/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf reports/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# =============================================================================
# AWS Utilities
# =============================================================================
delete-dev:
	aws cloudformation delete-stack --stack-name $(STACK_NAME_DEV)
	aws cloudformation wait stack-delete-complete --stack-name $(STACK_NAME_DEV)

get-api-key-dev:
	@echo "API Key for dev environment:"
	@aws apigateway get-api-key \
		--api-key $$(aws cloudformation describe-stack-resources \
			--stack-name $(STACK_NAME_DEV) \
			--query "StackResources[?LogicalResourceId=='ApiKey'].PhysicalResourceId" \
			--output text) \
		--include-value \
		--query "value" \
		--output text

outputs-dev:
	aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME_DEV) \
		--query "Stacks[0].Outputs" \
		--output table

logs-integration:
	$(SAM) logs -n IntegrationServiceFunction --stack-name $(STACK_NAME_DEV) --tail

logs-evaluation:
	$(SAM) logs -n EvaluationServiceFunction --stack-name $(STACK_NAME_DEV) --tail

# =============================================================================
# Invoke Lambda Functions
# =============================================================================
invoke-integration-threads:
	aws lambda invoke \
		--function-name langsmith-integration-service-dev \
		--payload '{"httpMethod":"GET","path":"/threads/annotated","queryStringParameters":{"limit":"10"}}' \
		--cli-binary-format raw-in-base64-out \
		/dev/stdout

invoke-evaluation-discovery:
	aws lambda invoke \
		--function-name langsmith-evaluation-service-dev \
		--payload '{"httpMethod":"GET","path":"/evaluations/discovery"}' \
		--cli-binary-format raw-in-base64-out \
		/dev/stdout
