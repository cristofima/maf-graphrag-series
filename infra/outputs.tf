# =========================================================================
# MAF GraphRAG Series - Terraform Outputs
# =========================================================================

output "resource_group_name" {
  description = "The name of the resource group"
  value       = azurerm_resource_group.main.name
}

# =========================================================================
# Azure OpenAI Outputs
# =========================================================================
output "openai_endpoint" {
  description = "The endpoint URL for Azure OpenAI"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "openai_primary_key" {
  description = "The primary access key for Azure OpenAI"
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}

output "openai_chat_deployment_name" {
  description = "The name of the GPT-4o deployment"
  value       = azurerm_cognitive_deployment.gpt4o.name
}

output "openai_embedding_deployment_name" {
  description = "The name of the text-embedding-3-large deployment"
  value       = azurerm_cognitive_deployment.embedding.name
}

output "openai_resource_name" {
  description = "The name of the Azure OpenAI resource"
  value       = azurerm_cognitive_account.openai.name
}

# =========================================================================
# Storage Account Outputs
# =========================================================================
output "storage_account_name" {
  description = "The name of the storage account"
  value       = azurerm_storage_account.graphrag.name
}

output "storage_primary_key" {
  description = "The primary access key for the storage account"
  value       = azurerm_storage_account.graphrag.primary_access_key
  sensitive   = true
}

output "storage_connection_string" {
  description = "The connection string for the storage account"
  value       = azurerm_storage_account.graphrag.primary_connection_string
  sensitive   = true
}

# =========================================================================
# Environment Variables Output
# Run: terraform output -raw env_file_content > ../.env
# =========================================================================
output "env_file_content" {
  description = "Content for .env file (run: terraform output -raw env_file_content > ../.env)"
  value       = <<-EOT
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT=${azurerm_cognitive_account.openai.endpoint}
    AZURE_OPENAI_API_KEY=${azurerm_cognitive_account.openai.primary_access_key}
    AZURE_OPENAI_CHAT_DEPLOYMENT=${azurerm_cognitive_deployment.gpt4o.name}
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT=${azurerm_cognitive_deployment.embedding.name}
    AZURE_OPENAI_API_VERSION=2024-08-01-preview

    # Azure Storage Configuration (optional - for Azure Blob output)
    AZURE_STORAGE_ACCOUNT_NAME=${azurerm_storage_account.graphrag.name}
    AZURE_STORAGE_ACCOUNT_KEY=${azurerm_storage_account.graphrag.primary_access_key}
    AZURE_STORAGE_CONNECTION_STRING=${azurerm_storage_account.graphrag.primary_connection_string}
  EOT
  sensitive   = true
}
