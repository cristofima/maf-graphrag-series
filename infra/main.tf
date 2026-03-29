# =========================================================================
# MAF GraphRAG Series - Azure Infrastructure
# Terraform configuration for Azure OpenAI and Blob Storage
# =========================================================================

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------
provider "azurerm" {
  features {
    # Applies to both azurerm_cognitive_account and azurerm_ai_services
    # (both use the Microsoft.CognitiveServices API)
    cognitive_account {
      purge_soft_delete_on_destroy = true
    }
  }

  subscription_id = var.subscription_id
}

provider "azapi" {
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
# Azure AI Services (Foundry-native)
# Replaces azurerm_cognitive_account (kind=OpenAI) with the unified AI Services
# resource. Same azurerm_cognitive_deployment child resources work unchanged.
# Benefit: first-class Azure AI Foundry Hub integration — the Hub auto-discovers
# AI Services resources in the same resource group without extra wiring.
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/
# -----------------------------------------------------------------------------
resource "azurerm_ai_services" "openai" {
  name                  = "${var.project_name}-openai-${random_string.suffix.result}"
  location              = var.openai_location
  resource_group_name   = azurerm_resource_group.main.name
  sku_name              = "S0"
  custom_subdomain_name = "${var.project_name}-openai-${random_string.suffix.result}"

  public_network_access = "Enabled"

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    prevent_destroy = false # Set to true in production
  }
}

# Enable New Foundry project management on the existing AI Services account.
resource "azapi_update_resource" "openai_project_management" {
  type        = "Microsoft.CognitiveServices/accounts@2025-06-01"
  resource_id = azurerm_ai_services.openai.id

  body = {
    properties = {
      allowProjectManagement = true
    }
  }
}

# -----------------------------------------------------------------------------
# Azure OpenAI Model Deployment - GPT-4o (Chat)
# Used for entity extraction and relationship detection in GraphRAG
# Reference: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = var.openai_chat_deployment_name
  cognitive_account_id = azurerm_ai_services.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-11-20"
  }

  sku {
    name     = "Standard"
    capacity = var.openai_capacity
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
  cognitive_account_id = azurerm_ai_services.openai.id

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

# -----------------------------------------------------------------------------
# Log Analytics Workspace (required by Application Insights)
# Provides the backing data store for Application Insights telemetry
# Reference: https://learn.microsoft.com/en-us/azure/azure-monitor/logs/
# -----------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.project_name}-${var.environment}-law-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Application Insights (Part 5 - Monitoring & Evaluation)
# Collects OpenTelemetry traces from MAF agents and evaluation metrics
# Reference: https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview
# -----------------------------------------------------------------------------
resource "azurerm_application_insights" "main" {
  name                = "${var.project_name}-${var.environment}-ai-${random_string.suffix.result}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "other"

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# Azure AI Services Project (New Foundry)
# Creates a project directly under the AI Services account so it is visible in
# New Foundry and usable by SDKs expecting an /api/projects/{name} endpoint.
# Reference: https://learn.microsoft.com/azure/foundry/how-to/create-resource-terraform
# -----------------------------------------------------------------------------
resource "azurerm_cognitive_account_project" "main" {
  count = var.enable_foundry ? 1 : 0

  name                 = "${var.project_name}-project"
  cognitive_account_id = azurerm_ai_services.openai.id
  location             = azurerm_resource_group.main.location

  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags

  lifecycle {
    create_before_destroy = false
  }

  depends_on = [azapi_update_resource.openai_project_management]
}
