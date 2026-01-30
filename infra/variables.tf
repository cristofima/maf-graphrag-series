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
  default     = "westus"
}

variable "openai_location" {
  description = <<-EOT
    The Azure region for OpenAI resources (may differ from storage region for model availability).
    Regions with GPT-4o and text-embedding-3-small: eastus, eastus2, westus, canadaeast, australiaeast, japaneast, switzerlandnorth
  EOT
  type        = string
  default     = "westus"
}

variable "openai_chat_deployment_name" {
  description = "The name for the chat model deployment (GPT-4o)"
  type        = string
  default     = "gpt-4o"
}

variable "openai_embedding_deployment_name" {
  description = "The name for the embedding model deployment"
  type        = string
  default     = "text-embedding-3-small"
}

variable "openai_capacity" {
  description = "OpenAI deployment capacity in thousands of tokens per minute (TPM). Default: 30K TPM"
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
