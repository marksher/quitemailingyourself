# Terraform management for Quitemailingyourself
# Usage: make plan ENV=dev or make apply ENV=prod

ENV ?= dev
TFVARS_FILE = environments/$(ENV)/terraform.tfvars

.PHONY: help init plan apply destroy output clean validate format

help: ## Show this help message
	@echo "Terraform commands for Quitemailingyourself infrastructure"
	@echo ""
	@echo "Usage: make [command] ENV=[dev|prod]"
	@echo ""
	@echo "Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make plan ENV=dev     # Plan development deployment"
	@echo "  make apply ENV=prod   # Deploy to production"
	@echo "  make output ENV=dev   # Show outputs"

init: ## Initialize Terraform
	terraform init

validate: ## Validate Terraform configuration
	terraform validate

format: ## Format Terraform files
	terraform fmt -recursive

plan: ## Plan Terraform deployment
	@if [ ! -f $(TFVARS_FILE) ]; then \
		echo "❌ File $(TFVARS_FILE) not found!"; \
		echo "   Copy from $(TFVARS_FILE).example and edit it"; \
		exit 1; \
	fi
	terraform plan -var-file="$(TFVARS_FILE)"

apply: ## Apply Terraform changes
	@if [ ! -f $(TFVARS_FILE) ]; then \
		echo "❌ File $(TFVARS_FILE) not found!"; \
		echo "   Copy from $(TFVARS_FILE).example and edit it"; \
		exit 1; \
	fi
	terraform apply -var-file="$(TFVARS_FILE)"

output: ## Show Terraform outputs
	terraform output

refresh: ## Refresh Terraform state
	terraform refresh -var-file="$(TFVARS_FILE)"

destroy: ## Destroy infrastructure (⚠️ DANGEROUS!)
	@echo "⚠️  WARNING: This will destroy all infrastructure!"
	@echo "   Environment: $(ENV)"
	@echo "   Continue? (yes/no)"
	@read confirm && [ "$$confirm" = "yes" ]
	terraform destroy -var-file="$(TFVARS_FILE)"

clean: ## Clean Terraform cache
	rm -rf .terraform
	rm -f .terraform.lock.hcl

ssh: ## SSH to the instance
	@echo "Connecting to $(ENV) instance..."
	@$(shell terraform output -raw ssh_command)

health: ## Check application health
	@echo "Checking application health on $(ENV)..."
	@curl -s http://$(shell terraform output -raw instance_public_ip):8000/health | jq .

logs: ## Show PM2 logs (requires SSH)
	@echo "To view logs, SSH to the instance and run: pm2 logs"
	@echo "SSH command: $(shell terraform output -raw ssh_command)"

# Development shortcuts
dev-plan: ## Plan development deployment
	@$(MAKE) plan ENV=dev

dev-apply: ## Apply development deployment  
	@$(MAKE) apply ENV=dev

dev-destroy: ## Destroy development infrastructure
	@$(MAKE) destroy ENV=dev

# Production shortcuts  
prod-plan: ## Plan production deployment
	@$(MAKE) plan ENV=prod

prod-apply: ## Apply production deployment
	@$(MAKE) apply ENV=prod