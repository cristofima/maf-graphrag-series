# Multi-Region Architecture Overview

## Deployment Strategy

This project uses a **cross-region architecture** to optimize for cost, model availability, and quota flexibility.

```
┌─────────────────────────────────────────────────────┐
│                    Client Application               │
│                  (Future: Week 2-3)                 │
└───────────────────────┬─────────────────────────────┘
                        │
                        │ HTTPS API Calls
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────────┐          ┌───────────────────┐
│  SOUTHCENTRALUS   │          │      WESTUS       │
│                   │          │                   │
│ ┌───────────────┐ │          │ ┌───────────────┐ │
│ │ Storage       │ │          │ │ Azure OpenAI  │ │
│ │ Account (LRS) │ │          │ │               │ │
│ │               │ │          │ │ - GPT-4o      │ │
│ │ Containers:   │ │          │ │   30K TPM     │ │
│ │ • input       │ │          │ │               │ │
│ │ • output      │ │          │ │ - embedding   │ │
│ │ • cache       │ │          │ │   3-small     │ │
│ └───────────────┘ │          │ │   30K TPM     │ │
│                   │          │ └───────────────┘ │
│ ┌───────────────┐ │          │                   │
│ │ App Service / │ │          │                   │
│ │ Container Apps│ │          │                   │
│ │ (Future)      │ │          │                   │
│ └───────────────┘ │          │                   │
└───────────────────┘          └───────────────────┘
```

## Regional Selection Rationale

### southcentralus (Storage & Compute)
**Why chosen:**
- ✅ Better quota availability for App Services and Container Apps
- ✅ User (Cristopher) has working quotas in this region
- ✅ Lower contention for compute resources
- ✅ Same US geography (no data sovereignty issues)

**Services deployed:**
- Azure Storage Account (Standard LRS)
- Future: Azure Container Apps or App Service

### westus (Azure OpenAI)
**Why chosen:**
- ✅ `text-embedding-3-small` model availability
- ✅ `gpt-4o` model availability (all versions)
- ✅ Lower demand than eastus/eastus2
- ✅ Fewer provisioning delays
- ✅ Same US geography (no data sovereignty issues)

**Services deployed:**
- Azure OpenAI Account
  - GPT-4o deployment (30K TPM)
  - text-embedding-3-small deployment (30K TPM)

## Performance Characteristics

### Cross-Region Latency
- **Azure backbone latency** (southcentralus ↔ westus): ~20-30ms
- **Total API call latency**: ~50-100ms (includes Azure OpenAI processing)
- **GraphRAG indexing per document**: 5-15 seconds (LLM processing dominates)

**Impact Analysis:**
- Cross-region latency is < 1% of total processing time
- For batch workloads (GraphRAG indexing), this is negligible
- For real-time applications, consider same-region deployment

### Network Traffic Patterns

#### Indexing Phase (Heavy)
```
Documents (Storage) → Python Script → Azure OpenAI
  ↓                                        ↓
Cache (Storage)  ← Embeddings & Entities ←┘
  ↓
Output (Storage) ← Knowledge Graph
```

**Traffic**: Mostly southcentralus ↔ westus API calls (metadata only, ~KB per request)

#### Query Phase (Light)
```
User Query → Python Script → Azure OpenAI (Embeddings)
                    ↓              ↓
              Storage (KG) → Local/Global Search
                    ↓
              Response
```

**Traffic**: Minimal, primarily local reads from storage

## Cost Analysis

### Cross-Region Data Transfer
- **Azure OpenAI API calls**: ~$0.01-0.05/GB (negligible, mostly JSON metadata)
- **Estimated monthly egress**: < $5 for typical GraphRAG workload

### Cost Comparison

| Component | Location | Monthly Cost (Est.) |
|-----------|----------|-------------------|
| Azure OpenAI (GPT-4o) | westus | $150-250 |
| Azure OpenAI (text-embedding-3-small) | westus | $10-30 |
| Storage (LRS) | southcentralus | $20-40 |
| Cross-region transfer | N/A | < $5 |
| **Total** | | **$180-325** |

**Savings from text-embedding-3-small**: ~$176/month vs ada-002

## Alternative Architectures

### Option 1: Single Region (eastus2)
✅ All services in one region (lowest latency)  
❌ High demand region (provisioning delays)  
❌ Quota limitations  
❌ Higher cost (no flexibility)

**Verdict**: Not viable due to quota issues

### Option 2: Single Region (southcentralus)
✅ Good quota availability  
❌ Missing text-embedding-3-small model  
❌ Forced to use text-embedding-ada-002 (5x more expensive)

**Verdict**: More expensive, lower performance

### Option 3: Multi-Region (SELECTED)
✅ Best model availability (westus)  
✅ Best quota availability (southcentralus)  
✅ Cost optimization (text-embedding-3-small)  
⚠️ Cross-region latency (~25ms, negligible for batch)

**Verdict**: Optimal for cost, performance, and reliability

## Scalability Considerations

### Future Enhancements

#### Add Failover Region
```
Primary: westus (Azure OpenAI)
Failover: eastus2 (Azure OpenAI)
```

Benefits:
- High availability for OpenAI API
- Automatic failover with retry logic
- Global quota distribution

#### Add CDN/Front Door
```
User → Azure Front Door → App Service (southcentralus)
                ↓
         Azure OpenAI (westus)
```

Benefits:
- Global edge caching
- WAF protection
- Load balancing

#### Add API Management
```
App Service → API Management → Azure OpenAI (westus)
                    ↓              ↓
                   Metrics    OpenAI (eastus2)
```

Benefits:
- Request throttling
- Usage analytics
- Circuit breaker pattern
- Multi-backend routing

## Deployment Instructions

### 1. Bootstrap Remote State (Region-Agnostic)
```bash
cd infra/bootstrap
terraform init
terraform apply

# Extract backend config
terraform output -raw backend_config > ../backend.hcl
```

### 2. Deploy Main Infrastructure
```bash
cd ../
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

**Resources Created**:
- Resource Group: `maf-graphrag-dev-rg` (westus)
- Azure OpenAI: `maf-graphrag-openai-XXXXX` (westus)
- Storage: `mafgraphragdevstXXXXX` (southcentralus)

### 3. Generate Environment Configuration
```bash
terraform output -raw env_file_content > ../.env
```

## Monitoring & Troubleshooting

### Key Metrics to Watch

1. **Cross-Region Latency**
   - Monitor Azure OpenAI API response times
   - Alert if > 500ms average

2. **Quota Utilization**
   - Track TPM usage in westus (Azure OpenAI)
   - Track storage IOPS in southcentralus

3. **Error Rates**
   - 429 errors (rate limiting) → increase TPM capacity
   - 503 errors (regional outage) → implement failover

### Troubleshooting Guide

#### Problem: High API Latency
```bash
# Test cross-region connectivity
Test-NetConnection -ComputerName <openai-endpoint>.openai.azure.com -Port 443

# Check Azure Service Health
az monitor activity-log list --max-events 10
```

#### Problem: Storage Access Issues
```bash
# Verify storage account connectivity
az storage account show --name <storage-account> --query "primaryEndpoints"

# Check network rules
az storage account network-rule list --account-name <storage-account>
```

## References

- [Azure OpenAI Model Availability](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/models)
- [Azure Multi-Region Architecture](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/azure-openai-gateway-multi-backend)
- [Azure Network Latency Statistics](https://learn.microsoft.com/en-us/azure/networking/azure-network-latency)
- [GraphRAG Documentation](https://microsoft.github.io/graphrag/)

---

**Last Updated**: January 30, 2026  
**Architecture Version**: 1.0  
**Status**: Production-Ready for Week 1
