.PHONY: help up dev stop logs sandbox-up sandbox-logs deploy-challenges test build

COMPOSE := docker compose
SANDBOX_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.sandbox.yml

help:
	@echo "Project: companion_x"
	@echo "  make dev               — Start the lightweight API + Next dashboard (ports 8000/3000)"
	@echo "  make up                — Alias for make dev"
	@echo "  make stop              — Stop the default development stack"
	@echo "  make logs              — Tail API and dashboard logs"
	@echo "  make sandbox-up        — Start the opt-in LocalStack/security sandbox"
	@echo "  make sandbox-logs      — Tail sandbox logs"
	@echo "  make deploy-challenges — Deploy CFN templates into the running sandbox"
	@echo "  make test              — Run project tests"
	@echo "  make build             — Build API and dashboard images"

.env:
	cp -n .env.example .env 2>/dev/null || true

dev: .env
	$(COMPOSE) up -d --build

up: dev

stop:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs -f companion_x-api companion_x-next

sandbox-up: .env
	$(SANDBOX_COMPOSE) up -d --build

sandbox-logs:
	$(SANDBOX_COMPOSE) logs -f

deploy-challenges:
	$(SANDBOX_COMPOSE) exec -T awscli sh /challenges/iam-privesc/../../localstack/deploy_challenges.sh 2>/dev/null || \
	$(SANDBOX_COMPOSE) exec -T awscli sh -c "\
		aws cloudformation deploy --template-file /challenges/iam-privesc/template.yaml --stack-name iam-privesc --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset && \
		aws cloudformation deploy --template-file /challenges/ssrf-lambda/template.yaml --stack-name ssrf-lambda --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset && \
		aws cloudformation deploy --template-file /challenges/idor-warehouse/template.yaml --stack-name idor-warehouse --capabilities CAPABILITY_NAMED_IAM --no-fail-on-empty-changeset \
	"

test:
	uv run --project . pytest

build:
	$(COMPOSE) build companion_x-api companion_x-next
