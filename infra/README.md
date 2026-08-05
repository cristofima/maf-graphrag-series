# 🏗️ MAF GraphRAG Series - Infrastructure

Terraform configuration for provisioning Azure OpenAI and Storage Account for the GraphRAG project.

## 📋 Resources Created

| Resource                      | Purpose                                 | SKU/Capacity                      |
| ----------------------------- | --------------------------------------- | --------------------------------- |
| **Azure OpenAI**              | Entity extraction, query, eval, safety  | S0 (Pay-as-you-go)                |
| - GPT-4.1 app deployment      | Main chat and GraphRAG query workload   | DataZoneStandard, 10K TPM default |
| - GPT-4.1 eval deployment     | Evaluation judge workload               | DataZoneStandard, 10K TPM default |
| - GPT-4.1 red-team deployment | Red-team target workload                | DataZoneStandard, 10K TPM default |
| - GPT-4o deployment           | Legacy compatibility (optional)         | Standard, 30K TPM default         |
| - text-embedding-3-small      | Document embeddings                     | Standard, 30K TPM default         |
| **Azure Storage Account**     | GraphRAG output storage                 | Standard tier, LRS replication    |
| - output container            | Parquet files (entities, relationships) | -                                 |
| - cache container             | GraphRAG cache                          | -                                 |
| - input container             | Optional: Document storage              | -                                 |

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

| Variable                              | Description                           | Default                 |
| ------------------------------------- | ------------------------------------- | ----------------------- |
| `subscription_id`                     | Azure Subscription ID                 | _Required_              |
| `project_name`                        | Project name for resources            | `maf-graphrag`          |
| `environment`                         | Environment (dev/staging/prod)        | `dev`                   |
| `location`                            | Primary Azure region                  | `eastus2`               |
| `openai_location`                     | Azure OpenAI region                   | `eastus2`               |
| `openai_chat_deployment_name`         | Legacy GPT-4o deployment name         | `gpt-4o`                |
| `openai_main_chat_deployment_name`    | App chat deployment name              | `graphrag-main-chat`    |
| `openai_eval_chat_deployment_name`    | Eval deployment name                  | `graphrag-main-eval`    |
| `openai_redteam_chat_deployment_name` | Red-team deployment name              | `graphrag-main-redteam` |
| `openai_app_model_name`               | Model family for app/eval/red-team    | `gpt-4.1`               |
| `openai_app_model_version`            | Model version for app/eval/red-team   | `2025-04-14`            |
| `openai_app_deployment_sku_name`      | SKU for app/eval/red-team deployments | `DataZoneStandard`      |
| `openai_router_deployment_name`       | Existing model-router deployment name | `model-router`          |
| `enable_legacy_chat_deployment`       | Keep existing GPT-4o deployment       | `true`                  |
| `openai_capacity`                     | Legacy GPT-4o TPM (thousands)         | `30`                    |
| `openai_main_chat_capacity`           | App TPM (thousands)                   | `10`                    |
| `openai_eval_chat_capacity`           | Eval TPM (thousands)                  | `10`                    |
| `openai_redteam_chat_capacity`        | Red-team TPM (thousands)              | `10`                    |
| `storage_sku`                         | Storage replication                   | `LRS`                   |
| `enable_foundry`                      | Create New Foundry Project            | `true`                  |

## 💰 Cost Estimation

### Azure OpenAI Service

This stack now separates chat, evaluation, and red-team workloads into independent deployments.
Actual monthly cost depends on:

- selected model family and SKU
- configured capacities (`openai_main_chat_capacity`, `openai_eval_chat_capacity`, `openai_redteam_chat_capacity`)
- run frequency of batch evaluation and red-team workflows

Use the Azure pricing calculator for your region and current model prices.

### Azure Storage Account

- Storage: ~$0.50/month (Standard LRS, < 1GB)
- Transactions: Negligible
- **Total**: < $1/month

Overall infrastructure cost is variable and depends on model SKU, capacity settings, and evaluation/red-team run cadence.

## 🧠 Azure AI Foundry & Evaluation Dashboard (Always On)

- **New Foundry Project** is provisioned automatically (`enable_foundry = true`).
- The `.env` file will always include the `AZURE_AI_PROJECT` variable with the Foundry project endpoint.
- The Evaluation Dashboard and advanced evaluation flows work out-of-the-box, with no manual steps required.
- If you want to disable Foundry (not recommended), set `enable_foundry = false` and re-apply.

**No manual changes are needed to use the Evaluation Dashboard: everything is ready after `terraform apply`.**

## Deployment Naming Convention

Terraform now provisions these deployment names by default:

- `graphrag-main-chat`
- `graphrag-main-eval`
- `graphrag-main-redteam`

Existing manual deployments that are only referenced by name stay unmanaged by this stack and aren't deleted by `terraform apply`, because Terraform only manages resources in its own state.

That currently applies to:

- `model-router`

Model router double-check:

- Microsoft Learn confirms `model-router` is a deployable Foundry model, available in East US 2 Global Standard.
- Microsoft Learn also confirms it can be deployed programmatically via management-plane REST/ARM.
- This stack still leaves it unmanaged on purpose for now, because the current repo relies on an existing manual deployment and the stack doesn't yet model router-specific settings such as routing mode/subset.
- The generated `.env` now includes `AZURE_OPENAI_ROUTER_DEPLOYMENT` so the application can keep using the manual router deployment cleanly.

If you want to retire the old Terraform-managed `gpt-4o` deployment later, first migrate callers and then set `enable_legacy_chat_deployment = false`.

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

| Feature                | Description                                       |
| ---------------------- | ------------------------------------------------- |
| **State Locking**      | Automatic - prevents concurrent modifications     |
| **State Protection**   | Versioning + 7-day soft delete                    |
| **Encryption**         | At rest (Azure managed) and in transit (TLS 1.2+) |
| **Team Collaboration** | Shared state accessible by team                   |

### Backend Configuration Files

| File                         | Purpose                     | Git Status  |
| ---------------------------- | --------------------------- | ----------- |
| `backend.hcl`                | Backend connection details  | Git-ignored |
| `bootstrap/terraform.tfvars` | Bootstrap subscription ID   | Git-ignored |
| `terraform.tfvars`           | Main config subscription ID | Git-ignored |

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
