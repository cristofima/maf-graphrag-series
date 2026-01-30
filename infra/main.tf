# =========================================================================
# MAF GraphRAG Series - Azure Infrastructure
# Terraform configuration for Azure OpenAI and Blob Storage
# =========================================================================

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------
provider "azurerm" {
  features {
    cognitive_account {
      purge_soft_delete_on_destroy = true
    }
  }

  subscription_id = var.subscription_id
}

# -----------------------------------------------------------------------------
# Random Suffix - Ensures globally unique resource names
# -----------------------------------------------------------------------------
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# -----------------------------------------------------------------------------
# Local Variables
# -----------------------------------------------------------------------------
locals {
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "maf-graphrag-series"
    },
    var.tags
  )
}

# -----------------------------------------------------------------------------
# Resource Group
# -----------------------------------------------------------------------------
resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location

  tags = local.common_tags

  lifecycle {
    prevent_destroy = false # Set to true in production
  }
}

# -----------------------------------------------------------------------------
# Azure OpenAI Service
# Provides GPT-4o (entity extraction) and text-embedding-3-large (embeddings)
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/openai/
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_account" "openai" {
  name                  = "${var.project_name}-openai-${random_string.suffix.result}"
  location              = var.openai_location
  resource_group_name   = azurerm_resource_group.main.name
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = "${var.project_name}-openai-${random_string.suffix.result}"

  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = false # Set to true in production
  }
}

# -----------------------------------------------------------------------------
# Azure OpenAI Model Deployment - GPT-4o (Chat)
# Used for entity extraction and relationship detection in GraphRAG
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = var.openai_chat_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-08-06"
  }

  sku {
    name     = "Standard"
    capacity = var.openai_capacity
  }

  lifecycle {
    ignore_changes = [model[0].version]
  }
}

# -----------------------------------------------------------------------------
# Azure OpenAI Model Deployment - text-embedding-3-small
# Used for document and entity embeddings in GraphRAG
# Note: 5x cheaper than ada-002 with 40% better performance (MIRACL benchmark)
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.openai_embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-3-small"
    version = "1"
  }

  sku {
    name     = "Standard"
    capacity = var.openai_capacity
  }

  lifecycle {
    ignore_changes = [model[0].version]
  }
}

# -----------------------------------------------------------------------------
# Azure Storage Account
# Stores GraphRAG output (parquet files, cache, etc.)
# Reference: https://learn.microsoft.com/en-us/azure/storage/
# -----------------------------------------------------------------------------
resource "azurerm_storage_account" "graphrag" {
  name                = "${replace(var.project_name, "-", "")}${var.environment}st${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  account_tier             = "Standard"
  account_replication_type = var.storage_sku

  account_kind                    = "StorageV2"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Storage Containers for GraphRAG
# -----------------------------------------------------------------------------
resource "azurerm_storage_container" "output" {
  name                  = "output"
  storage_account_id    = azurerm_storage_account.graphrag.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "cache" {
  name                  = "cache"
  storage_account_id    = azurerm_storage_account.graphrag.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "input" {
  name                  = "input"
  storage_account_id    = azurerm_storage_account.graphrag.id
  container_access_type = "private"
}
