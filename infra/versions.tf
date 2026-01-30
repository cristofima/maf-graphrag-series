# =========================================================================
# MAF GraphRAG Series - Terraform Version Constraints
# Following Azure Verified Modules (AVM) specifications
# =========================================================================

terraform {
  required_version = "~> 1.9"

  # Remote State Backend - Azure Blob Storage
  # Setup: Run bootstrap configuration first
  # 1. cd infra/bootstrap
  # 2. terraform init && terraform apply
  # 3. terraform output -raw backend_hcl_content > ../backend.hcl
  # 4. cd .. && terraform init -backend-config=backend.hcl
  backend "azurerm" {
    # Values provided via -backend-config=backend.hcl
    # Required backend.hcl contents:
    #   subscription_id      = "your-subscription-id"
    #   resource_group_name  = "maf-graphrag-dev-tfstate-rg"
    #   storage_account_name = "mafgrdevtfstateXXXXXXXX"
    #   container_name       = "tfstate"
    #   key                  = "dev.terraform.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}
