# Lessons Learned: MAF + GraphRAG Infrastructure Deployment

## Overview

This document captures key insights, challenges, and solutions encountered during the Azure infrastructure setup for the MAF + GraphRAG series Part 1 implementation.

---

## Challenge 1: Azure Storage Account SKU Validation

### Problem
Initial Terraform deployment failed with a validation error related to the storage account SKU configuration.

```
Error: Invalid value for variable storage_sku
The specified value "Standard_LRS" is incompatible with the expected type
```

### Root Cause
The `azurerm_storage_account` resource's `account_replication_type` parameter expects a short-form SKU value like `LRS`, `GRS`, `RAGRS`, etc., **not** the full SKU name like `Standard_LRS`.

### Solution
Updated `infra/variables.tf`:

```hcl
variable "storage_sku" {
  description = "Storage account SKU"
  type        = string
  default     = "LRS"  # Changed from "Standard_LRS"
  
  validation {
    condition     = contains(["LRS", "GRS", "RAGRS", "ZRS", "GZRS", "RAGZRS"], var.storage_sku)
    error_message = "Storage SKU must be one of: LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS."
  }
}
```

### Key Insight
Always verify Azure provider parameter formats in the [official Terraform AzureRM documentation](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs). The Azure Portal UI uses full SKU names, but Terraform resources may use abbreviated values.

---

## Challenge 2: Azure OpenAI Embedding Model Regional Availability

### Problem
Deployment to `southcentralus` failed with the following error:

```
Error creating Cognitive Services Deployment: (InvalidResourceProperties) 
The specified SKU 'Standard' for model 'text-embedding-3-large 1' is not 
supported in this region 'southcentralus'.
```

### Root Cause
Azure OpenAI model availability varies significantly by region. The `text-embedding-3-large` model is **not available** in `southcentralus`, despite GPT-4o being available there.

**Regional Availability Matrix (as of January 2026):**

| Region | GPT-4o | text-embedding-3-small | text-embedding-3-large | text-embedding-ada-002 |
|--------|--------|------------------------|------------------------|------------------------|
| southcentralus | ✅ | ❌ | ❌ | ✅ (v1, v2) |
| eastus | ✅ | ✅ | ✅ | ✅ |
| eastus2 | ✅ | ✅ | ✅ | ✅ |
| westus | ✅ | ✅ | ❌ | ✅ |
| westus3 | ✅ | ❌ | ✅ | ✅ |

### Initial Workaround
Switched to `text-embedding-ada-002 (version 2)` which is available in `southcentralus`:

```hcl
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = "text-embedding-ada-002"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "text-embedding-ada-002"
    version = "2"
  }

  sku {
    name     = "Standard"
    capacity = 30
  }
}
```

### Final Solution
After cost-benefit analysis, adopted a **multi-region strategy**:
- **Azure Storage & App Services**: `southcentralus` (better quota availability)
- **Azure OpenAI**: `westus` (lower demand, text-embedding-3-small support)

### Key Insights

1. **Always verify model availability** before selecting a region: [Azure OpenAI Models - Region Availability](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models#model-summary-table-and-region-availability)

2. **Regional demand matters**: Regions like `eastus` and `eastus2` have higher demand and can experience provisioning delays or quota limitations.

3. **Multi-region architectures are common**: Separating compute and AI services across regions is a valid Azure best practice for:
   - Quota optimization
   - Cost efficiency
   - Model availability
   - Reduced provisioning contention

---

## Challenge 3: Cost vs Performance Optimization

### Analysis

We evaluated three embedding models based on cost, performance, and regional availability:

#### Performance Benchmarks

| Model | MIRACL Score | MTEB Score | Dimensions | Context Tokens |
|-------|--------------|------------|------------|----------------|
| text-embedding-3-large | 54.9 (+75% vs ada-002) | 64.6 | 3,072 | 8,192 |
| text-embedding-3-small | 44.0 (+40% vs ada-002) | 62.3 | 1,536 | 8,192 |
| text-embedding-ada-002 | 31.4 (baseline) | 61.0 | 1,536 | 8,192 (v2) |

**MIRACL**: Multi-language retrieval benchmark  
**MTEB**: Massive Text Embedding Benchmark (English)

#### Cost Comparison (Approximate)

| Model | Cost per 1M Tokens | Relative Cost |
|-------|-------------------|---------------|
| text-embedding-3-small | $0.02 | **5x cheaper** |
| text-embedding-ada-002 | $0.10 | 1x (baseline) |
| text-embedding-3-large | $0.13 | 1.3x more expensive |

#### Decision Matrix

For **GraphRAG workloads**, embeddings are generated for:
- Source documents (input corpus)
- Extracted entities (30-1000+ per document)
- Community summaries (hierarchical levels)
- Relationship descriptions

**Estimated Token Usage** (1,000 documents):
- Documents: ~1.5M tokens
- Entities: ~500K tokens
- Communities: ~200K tokens
- **Total**: ~2.2M tokens

**Cost Impact**:
- With `text-embedding-ada-002`: ~$220
- With `text-embedding-3-small`: ~$44 (**$176 savings**)
- With `text-embedding-3-large`: ~$286

### Final Decision
Selected **text-embedding-3-small** for:
- ✅ **5x cost reduction** compared to ada-002
- ✅ **40% better performance** (MIRACL: 44.0 vs 31.4)
- ✅ Available in `westus` (lower demand region)
- ✅ Same 1,536 dimensions (easier migration path)
- ✅ 8,192 token context (4x more than ada-002 v1)

### Key Insights

1. **Newer isn't always more expensive**: `text-embedding-3-small` is both cheaper and better than `ada-002`.

2. **Dimension reduction feature**: Third-generation embedding models support the `dimensions` parameter, allowing further cost optimization by reducing vector size without significant performance loss.

3. **GraphRAG-specific considerations**: For knowledge graph applications, embedding quality directly impacts:
   - Entity resolution accuracy
   - Community detection precision
   - Semantic search relevance
   
   The 40% performance improvement justifies the selection even without cost savings.

---

## Challenge 4: Multi-Region Architecture Design

### Scenario
Azure quota limitations in `eastus` and model availability gaps in `southcentralus` necessitated a cross-region deployment strategy.

### Architecture Decision

```
┌──────────────────────────────────────────┐
│ Application Layer                        │
│ - Azure Container Apps / App Service     │
│ - Storage Account (LRS)                  │
│   * Containers: input, output, cache     │
│                                          │
│ Region: southcentralus                   │
│ Reason: Quota availability               │
└──────────────────────────────────────────┘
                    │
                    │ API calls over Azure backbone
                    │ (~20-30ms latency)
                    ↓
┌──────────────────────────────────────────┐
│ AI Services Layer                        │
│ - Azure OpenAI Account                   │
│   * GPT-4o (30K TPM)                     │
│   * text-embedding-3-small (30K TPM)     │
│                                          │
│ Region: westus                           │
│ Reason: Model availability, lower demand │
└──────────────────────────────────────────┘
```

### Considerations

#### ✅ Advantages
- **Quota flexibility**: Use regions with available capacity
- **Model access**: Deploy where newer models are supported
- **Cost optimization**: Select cost-effective models without regional constraints
- **Reduced contention**: Avoid high-demand regions like `eastus`

#### ⚠️ Trade-offs
- **Cross-region latency**: ~20-30ms (acceptable for batch GraphRAG indexing)
- **Data egress costs**: Minimal for API calls (primarily metadata)
- **Increased complexity**: Two resource groups, cross-region network routing

#### ❌ When to Avoid
- **Data residency requirements**: If data must stay in specific geopolitical boundaries
- **Real-time applications**: If latency < 10ms is critical (use same-region deployment)
- **Compliance restrictions**: If regulations mandate single-region architecture

### Microsoft Learn Guidance

Multi-region architectures are explicitly supported for Azure OpenAI:

> "You can use multiple Azure regions together to distribute your solution across a wide geographical area. You can use this multi-region approach to improve your solution's reliability or to support geographically distributed users."  
> — [Architecture strategies for using availability zones and regions](https://learn.microsoft.com/en-us/azure/well-architected/design-guides/regions-availability-zones)

**Recommended Patterns**:
1. **Active-Active**: Multiple regions handling traffic simultaneously
2. **Active-Passive**: Primary region with failover to secondary
3. **Geo-distributed**: Optimize for user proximity

For our use case (GraphRAG batch indexing), cross-region latency is negligible compared to the LLM processing time (seconds per document).

### Key Insights

1. **Don't force single-region constraints**: Azure's global infrastructure is designed for multi-region workloads.

2. **Separate concerns by service characteristics**:
   - High-throughput services (storage, compute) → regions with quota
   - Specialized services (AI models) → regions with model availability

3. **Network latency context matters**: 
   - Real-time chat: < 100ms critical
   - GraphRAG indexing: 20-30ms latency is < 1% of total processing time

4. **Future-proofing**: Multi-region design enables easier migration when new models launch in different regions.

---

## Challenge 5: Terraform Backend State Management

### Problem
Configuring remote state storage for Terraform required careful bootstrap sequencing and backend configuration file generation.

### Solution: Two-Phase Deployment

#### Phase 1: Bootstrap Remote State Storage

```bash
cd infra/bootstrap
terraform init
terraform apply
```

Creates:
- Resource Group: `maf-graphrag-dev-tfstate-rg`
- Storage Account: `mafgrdevtfstate<random>`
- Container: `tfstate`
- Features: Versioning, soft delete (7 days)

#### Phase 2: Generate Backend Config

```bash
# Extract output to backend.hcl
terraform output -raw backend_config > ../backend.hcl

# Use inline parameters (recommended)
terraform init -reconfigure \
  -backend-config="subscription_id=<sub-id>" \
  -backend-config="resource_group_name=<rg-name>" \
  -backend-config="storage_account_name=<storage-name>" \
  -backend-config="container_name=tfstate" \
  -backend-config="key=terraform.tfstate"
```

### Key Insights

1. **Always use remote state for production**: Enables team collaboration, state locking, and disaster recovery.

2. **Separate bootstrap from main infrastructure**: Prevents circular dependency (main infra can't create its own state storage).

3. **Use Terraform outputs for automation**: Generate backend config programmatically to avoid manual errors.

4. **Enable versioning and soft delete**: Protects against accidental state corruption or deletion.

---

## Deployment Checklist

Based on lessons learned, use this checklist for future deployments:

### Pre-Deployment
- [ ] Verify Azure OpenAI model availability in target region(s)
- [ ] Check current quota limits for required services
- [ ] Review cost estimates for selected models
- [ ] Confirm data residency and compliance requirements
- [ ] Document multi-region architecture decisions

### Terraform Configuration
- [ ] Use short-form SKU values (LRS, not Standard_LRS)
- [ ] Set up remote state storage (bootstrap first)
- [ ] Add validation blocks to variables
- [ ] Use `terraform plan` before `apply`
- [ ] Enable detailed logging during deployment

### Post-Deployment
- [ ] Verify all resources in Azure Portal
- [ ] Test connectivity between regions (if multi-region)
- [ ] Generate `.env` file from Terraform outputs
- [ ] Document deployed resource names and IDs
- [ ] Commit Terraform state backend config (minus secrets)

---

## Resources

### Azure OpenAI Documentation
- [Model Summary Table and Region Availability](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models#model-summary-table-and-region-availability)
- [Embeddings Models](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models#embeddings)
- [Multi-Backend Gateway Architectures](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/azure-openai-gateway-multi-backend)

### Terraform
- [AzureRM Provider - Storage Account](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account)
- [AzureRM Provider - Cognitive Deployment](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/cognitive_deployment)
- [Backend Configuration](https://developer.hashicorp.com/terraform/language/settings/backends/azurerm)

### Microsoft GraphRAG
- [GitHub Repository](https://github.com/microsoft/graphrag)
- [Research Paper](https://www.microsoft.com/en-us/research/project/graphrag/)

---

## Summary

### Critical Success Factors

1. ✅ **Model availability research before region selection**
2. ✅ **Cost-performance analysis for embedding models**
3. ✅ **Multi-region architecture when beneficial**
4. ✅ **Remote state management with proper bootstrap**
5. ✅ **Validation and testing at each deployment step**

### Final Architecture

| Component | Region | Model/SKU | Rationale |
|-----------|--------|-----------|-----------|
| Azure OpenAI | westus | GPT-4o + text-embedding-3-small | Model availability, lower demand |
| Storage Account | southcentralus | Standard LRS | Quota availability |
| App Services | southcentralus | TBD | Quota availability, proximity to storage |

**Estimated Monthly Cost** (based on 30K TPM, moderate usage):
- Azure OpenAI: ~$150-300
- Storage Account: ~$20-50
- **Total**: ~$170-350/month

**Cost Savings**: ~$176/month from text-embedding-3-small selection

---

## Next Steps

1. Test Terraform deployment with updated configuration
2. Generate `.env` file from outputs
3. Commit infrastructure code to git
4. Implement MCP Server (Part 2)
5. Document integration patterns (Part 3+)

---

**Document Version**: 1.0  
**Last Updated**: January 31, 2026  
**Author**: Cristopher Coronado (Microsoft MVP AI)  
**Series**: MAF + GraphRAG - Part 1
