# 🏗️ MAF GraphRAG Series - Infrastructure

Terraform configuration for provisioning Azure OpenAI and Storage Account for the GraphRAG project.

## 📋 Resources Created

| Resource | Purpose | SKU |
|----------|---------|-----|
| **Azure OpenAI** | Entity extraction, embeddings | S0 (Pay-as-you-go) |
| - GPT-4o deployment | Entity/relationship extraction | 30K TPM |
| - text-embedding-3-large | Document embeddings | 30K TPM |
| **Azure Storage Account** | GraphRAG output storage | Standard_LRS |
| - output container | Parquet files (entities, relationships) | - |
| - cache container | GraphRAG cache | - |
| - input container | Optional: Document storage | - |

## 🚀 Quick Start

### Prerequisites

1. **Azure CLI** - [Install Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Terraform** - [Install Terraform](https://developer.hashicorp.com/terraform/install) (~> 1.9)
3. **Azure Subscription** with Azure OpenAI access approved

### Step 1: Authenticate with Azure

```powershell
az login
az account set --subscription "your-subscription-id"
```

### Step 2: Bootstrap Remote State (First Time Only)

```powershell
cd infra/bootstrap

# Configure your subscription ID
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars  # Add your subscription_id

# Create state storage
terraform init
terraform apply

# Generate backend config for main infrastructure
terraform output -raw backend_hcl_content > ../backend.hcl
```

See [bootstrap/README.md](bootstrap/README.md) for details.

### Step 3: Configure Main Infrastructure

```powershell
cd ..  # Back to infra directory
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars  # Add your subscription_id
```

### Step 4: Initialize with Remote Backend

```powershell
terraform init -backend-config=backend.hcl
```

### Step 5: Review the Plan

```powershell
terraform plan
```

### Step 6: Apply the Configuration

```powershell
terraform apply
```

### Step 7: Generate .env

After successful deployment:

```powershell
terraform output -raw env_file_content > ../.env
```

> ⚠️ **Security Note:** The `.env` file contains sensitive keys. Never commit it to version control.

## 📤 Outputs

View outputs:

```powershell
# View all outputs
terraform output

# View specific output
terraform output openai_endpoint

# View sensitive output
terraform output -raw openai_primary_key
```

## 🔧 Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `subscription_id` | Azure Subscription ID | *Required* |
| `project_name` | Project name for resources | `maf-graphrag` |
| `environment` | Environment (dev/staging/prod) | `dev` |
| `location` | Primary Azure region | `southcentralus` |
| `openai_location` | Azure OpenAI region | `southcentralus` |
| `openai_capacity` | TPM capacity (thousands) | `30` |
| `storage_sku` | Storage replication | `Standard_LRS` |

## 💰 Cost Estimation

### Azure OpenAI Service

| Model | Price | Usage (GraphRAG indexing) |
|-------|-------|---------------------------|
| **GPT-4o** | $2.50 / 1M input tokens | ~$1-5 per indexing run |
| **GPT-4o** | $10 / 1M output tokens | ~$2-8 per indexing run |
| **text-embedding-3-large** | $0.13 / 1M tokens | ~$0.10-0.50 per indexing run |

**Estimated monthly cost** (5 indexing runs): **$15-70/month**

### Azure Storage Account

- Storage: ~$0.50/month (Standard LRS, < 1GB)
- Transactions: Negligible
- **Total**: < $1/month

**Total Infrastructure**: **$16-71/month**

## 🧹 Cleanup

To destroy all resources:

```powershell
terraform destroy
```

To also remove remote state storage:

```powershell
cd bootstrap
terraform destroy
```

## 🗄️ Remote State

This project uses Azure Blob Storage for Terraform remote state:

| Feature | Description |
|---------|-------------|
| **State Locking** | Automatic - prevents concurrent modifications |
| **State Protection** | Versioning + 7-day soft delete |
| **Encryption** | At rest (Azure managed) and in transit (TLS 1.2+) |
| **Team Collaboration** | Shared state accessible by team |

### Backend Configuration Files

| File | Purpose | Git Status |
|------|---------|------------|
| `backend.hcl` | Backend connection details | Git-ignored |
| `bootstrap/terraform.tfvars` | Bootstrap subscription ID | Git-ignored |
| `terraform.tfvars` | Main config subscription ID | Git-ignored |

Cost: ~$0.50/month

## 🔒 Security Best Practices

1. **Never commit `terraform.tfvars`** - Contains subscription ID
2. **Never commit `backend.hcl`** - Contains storage details
3. **Never commit `.env`** - Contains API keys
4. **Use Azure Key Vault** for production secrets
5. **Enable Private Endpoints** for production workloads
6. **Rotate keys regularly** using Azure portal or CLI

## 📚 Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag)
- [Terraform AzureRM Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Azure Verified Modules](https://azure.github.io/Azure-Verified-Modules/)
