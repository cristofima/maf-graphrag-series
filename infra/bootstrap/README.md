# Terraform State Storage Bootstrap

This directory creates Azure Blob Storage for Terraform remote state.

## Why Remote State?

- **Team Collaboration**: Multiple developers work safely
- **State Locking**: Prevents concurrent modifications
- **State Protection**: Versioning and soft delete
- **Security**: Sensitive data stored securely

## Quick Start

### 1. Configure Variables

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars  # Add your subscription_id
```

### 2. Create State Storage

```powershell
terraform init
terraform plan
terraform apply
```

### 3. Configure Main Infrastructure Backend

```powershell
# Generate backend.hcl for main infrastructure
terraform output -raw backend_hcl_content > ../backend.hcl

# Initialize main infrastructure with remote state
cd ..
terraform init -backend-config=backend.hcl
```

## Created Resources

| Resource | Name Pattern | Purpose |
|----------|--------------|---------|
| Resource Group | `maf-graphrag-{env}-tfstate-rg` | Isolation for state storage |
| Storage Account | `mafgr{env}tfstate{random8}` | Blob storage for state files |
| Blob Container | `tfstate` | Container for state blobs |

## Security Features

- ✅ **Blob Versioning**: Recover previous state versions
- ✅ **Soft Delete**: 7-day retention
- ✅ **HTTPS Only**: TLS 1.2+
- ✅ **Private Access**: No public blob access
- ✅ **Standard Encryption**: Encrypted at rest

## Cost Estimate

- Storage Account: ~$0.50/month (Standard LRS)
- Blob Storage: Negligible (state files < 1MB)
- **Total**: < $1/month

## Production Recommendations

1. **Change to GRS replication** for geo-redundancy:
   ```hcl
   account_replication_type = "GRS"
   ```

2. **Enable `prevent_destroy`** after initial deployment:
   ```hcl
   lifecycle {
     prevent_destroy = true
   }
   ```

3. **Add network rules** to restrict access in production

## Troubleshooting

### "Storage account name already exists"

```powershell
# Force new random suffix
terraform taint random_string.suffix
terraform apply
```

### "Access denied" errors

```powershell
az login
az account set --subscription "your-subscription-id"
az account show
```
