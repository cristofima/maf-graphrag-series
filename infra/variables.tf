# MAF GraphRAG Series - Terraform Variables

variable "subscription_id" {
  description = "The Azure subscription ID to deploy resources into"
  type        = string
}

variable "project_name" {
  description = "The name of the project, used for resource naming. Must be 2-20 chars, lowercase alphanumerics and hyphens."
  type        = string
  default     = "maf-graphrag"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,18}[a-z0-9]$", var.project_name)) && length(var.project_name) >= 2 && length(var.project_name) <= 20
    error_message = "Project name must be 2-20 lowercase characters, start with a letter, end with alphanumeric, and contain only letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "The environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod"
  }
}

variable "location" {
  description = "Azure region for resource group and storage (compute layer)"
  type        = string
  default     = "eastus2"
}

variable "openai_location" {
  description = <<-EOT
    The Azure region for OpenAI resources (may differ from storage region for model availability).
    For stable Step 3 + Step 4 evaluation and red teaming, prefer eastus2.
  EOT
  type        = string
  default     = "eastus2"
}

variable "openai_chat_deployment_name" {
  description = "The name for the chat model deployment (GPT-4o)"
  type        = string
  default     = "gpt-4o"
}

variable "enable_legacy_chat_deployment" {
  description = "Keep the existing GPT-4o chat deployment managed by Terraform. Disable only after migrating callers."
  type        = bool
  default     = true
}

variable "openai_main_chat_deployment_name" {
  description = "The name for the primary application chat deployment (recommended: GPT-4.1)"
  type        = string
  default     = "graphrag-main-chat"
}

variable "openai_eval_chat_deployment_name" {
  description = "The name for the evaluation judge deployment (recommended: GPT-4.1)"
  type        = string
  default     = "graphrag-main-eval"
}

variable "openai_redteam_chat_deployment_name" {
  description = "The name for the red-team target deployment (recommended: GPT-4.1)"
  type        = string
  default     = "graphrag-main-redteam"
}

variable "openai_app_model_name" {
  description = "Model family for the app, eval, and red-team chat deployments"
  type        = string
  default     = "gpt-4.1"
}

variable "openai_app_model_version" {
  description = "Model version for the app, eval, and red-team chat deployments"
  type        = string
  default     = "2025-04-14"
}

variable "openai_app_deployment_sku_name" {
  description = "SKU name for the app, eval, and red-team chat deployments"
  type        = string
  default     = "DataZoneStandard"

  validation {
    condition = contains([
      "Standard",
      "GlobalStandard",
      "DataZoneStandard",
    ], var.openai_app_deployment_sku_name)
    error_message = "openai_app_deployment_sku_name must be Standard, GlobalStandard, or DataZoneStandard"
  }
}

variable "openai_main_chat_capacity" {
  description = "Capacity for the primary app deployment in thousands of TPM"
  type        = number
  default     = 10

  validation {
    condition     = var.openai_main_chat_capacity >= 1 && var.openai_main_chat_capacity <= 450
    error_message = "openai_main_chat_capacity must be between 1 and 450"
  }
}

variable "openai_eval_chat_capacity" {
  description = "Capacity for the evaluation deployment in thousands of TPM"
  type        = number
  default     = 10

  validation {
    condition     = var.openai_eval_chat_capacity >= 1 && var.openai_eval_chat_capacity <= 450
    error_message = "openai_eval_chat_capacity must be between 1 and 450"
  }
}

variable "openai_redteam_chat_capacity" {
  description = "Capacity for the red-team deployment in thousands of TPM"
  type        = number
  default     = 10

  validation {
    condition     = var.openai_redteam_chat_capacity >= 1 && var.openai_redteam_chat_capacity <= 450
    error_message = "openai_redteam_chat_capacity must be between 1 and 450"
  }
}

variable "openai_embedding_deployment_name" {
  description = "The name for the embedding model deployment"
  type        = string
  default     = "text-embedding-3-small"
}

variable "openai_router_deployment_name" {
  description = "The name of the existing model-router deployment used by the agent router"
  type        = string
  default     = "model-router"
}

variable "openai_capacity" {
  description = "Legacy GPT-4o deployment capacity in thousands of TPM. Used only when enable_legacy_chat_deployment=true."
  type        = number
  default     = 30

  validation {
    condition     = var.openai_capacity >= 1 && var.openai_capacity <= 450
    error_message = "OpenAI capacity must be between 1 and 450 (default quota limit)"
  }
}

variable "storage_sku" {
  description = "Storage account replication type for GraphRAG output (LRS recommended for dev)"
  type        = string
  default     = "LRS"

  validation {
    condition     = contains(["LRS", "GRS", "ZRS", "RAGRS", "GZRS", "RAGZRS"], var.storage_sku)
    error_message = "Storage SKU must be LRS, GRS, ZRS, RAGRS, GZRS, or RAGZRS"
  }
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_foundry" {
  description = "Provision New Foundry project under Azure AI Services for evaluation dashboards and red team scans (Part 5)."
  type        = bool
  default     = true
}

variable "foundry_user_principal_ids" {
  description = <<-EOT
    Entra object IDs (users, groups, or service principals) granted the "Foundry User"
    role on the Foundry project scope. Required for local New Foundry evals publish
    (run_batch_evaluation.py --foundry) via DefaultAzureCredential.
  EOT
  type        = list(string)
  default     = []
}
