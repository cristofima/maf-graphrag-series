# Lessons Learned: MAF + GraphRAG Series

## Overview

This document captures key insights, challenges, and solutions encountered during:
1. **Azure infrastructure setup** for the MAF + GraphRAG series (Challenges 1-5)
2. **GraphRAG 1.2.0 → 3.0.1 migration** (Challenges 6-10)
3. **Agent Framework integration** with MCP Server (Challenges 11-13)

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
- [GraphRAG v3 Config Reference](https://microsoft.github.io/graphrag/config/yaml/)

---

## Challenge 6: GraphRAG 1.2.0 → 3.0.1 API Breaking Changes

### Problem
The migration from GraphRAG 1.2.0 to 3.0.1 introduced several breaking API changes. The primary motivation was numpy compatibility—GraphRAG 1.2.0 pinned `numpy <2.0.0`, while Microsoft Agent Framework (`agent-framework`) required `numpy >=2.2.6`. This made it impossible to install both in the same environment.

### Breaking Changes Encountered

#### 1. `nodes` Parameter Removed from Search APIs

**OLD (1.2.0)**:
```python
await api.local_search(
    config=config,
    nodes=data.nodes,        # ← REMOVED in 3.x
    entities=data.entities,
    community_reports=data.community_reports,
    ...
)
```

**NEW (3.0.1)**:
```python
await api.local_search(
    config=config,
    entities=data.entities,
    communities=data.communities,  # ← NEW parameter
    community_reports=data.community_reports,
    ...
)
```

#### 2. `build_index` API Signature Changed

```diff
- run_id: str               # Removed
- is_resume_run: bool       # Renamed
- memory_profile: bool      # Removed
- progress_logger            # Removed
+ method: IndexingMethod     # New (Standard, Fast, etc.)
+ is_update_run: bool        # Renamed from is_resume_run
+ verbose: bool              # New
+ input_documents: DataFrame # New
```

### Solution

Updated three core modules:

1. **`core/data_loader.py`**: Added `communities` field to `GraphData` dataclass, removed `nodes`
2. **`core/search.py`**: Updated `local_search()` and `global_search()` to use `communities` instead of `nodes`
3. **`core/indexer.py`**: Updated `build_index()` to use new parameter names (`method`, `is_update_run`, `verbose`)

### Key Insight
Pin to a tilde version (`~3.0.1`) in `pyproject.toml` to allow patch updates while preventing future major breaking changes. Always check the [GraphRAG changelog](https://github.com/microsoft/graphrag/releases) before upgrading.

---

## Challenge 7: Output File Naming Convention Change

### Problem
GraphRAG 3.x changed the output Parquet file naming convention. All references to old file names throughout the codebase caused `FileNotFoundError` exceptions.

**OLD (1.2.0)**:
```
output/create_final_entities.parquet
output/create_final_relationships.parquet
output/create_final_communities.parquet
output/create_final_community_reports.parquet
output/create_final_text_units.parquet
```

**NEW (3.0.1)**:
```
output/entities.parquet
output/relationships.parquet
output/communities.parquet
output/community_reports.parquet
output/text_units.parquet
```

### Impact
This change affected **every layer** of the codebase:
- Python code (`data_loader.py`, `config.py`, `index.py`)
- Notebooks (`01_explore_graph.ipynb`)
- Documentation (README, docs/, articles/)
- Even prompt-related output references

### Solution
Systematic codebase-wide search and replace using `grep` to find all `create_final_` references, then updating each file in context. The `core/config.py` validation function was updated to check for the new file names.

### Key Insight
When a framework changes naming conventions, **grep the entire codebase** before considering the migration complete. Hidden references in documentation, comments, and print statements are easy to miss.

---

## Challenge 8: settings.yaml Configuration Format Overhaul

### Problem
GraphRAG 3.x completely restructured the `settings.yaml` format. The v1.2.0 configuration was incompatible and could not be incrementally updated.

**OLD (1.2.0)**:
```yaml
llm:
  api_key: ${GRAPHRAG_API_KEY}
  model: gpt-4o
  type: azure_openai_chat
  api_base: ${GRAPHRAG_API_BASE}

embeddings:
  llm:
    api_key: ${GRAPHRAG_API_KEY}
    model: text-embedding-3-small
    type: azure_openai_embedding
```

**NEW (3.0.1)**:
```yaml
completion_models:
  default_completion_model:
    model_provider: azure
    model: gpt-4o
    azure_deployment_name: ${AZURE_OPENAI_CHAT_DEPLOYMENT}
    api_base: ${AZURE_OPENAI_ENDPOINT}
    auth_method: api_key
    api_key: ${AZURE_OPENAI_API_KEY}

embedding_models:
  default_embedding_model:
    model_provider: azure
    model: text-embedding-3-small
    azure_deployment_name: ${AZURE_OPENAI_EMBEDDING_DEPLOYMENT}
    ...
```

### Additional Config Changes
- Environment variable names changed (e.g., `GRAPHRAG_API_KEY` → `AZURE_OPENAI_API_KEY`)
- `vector_store` section now requires explicit `index_schema` with `vector_size`
- Storage sections renamed (`storage` → `output_storage`, `input_storage` added)
- New sections: `cache.storage`, `reporting`, workflow-level model assignments

### Solution

1. Ran `poetry run graphrag init --force` to generate a fresh v3.x `settings.yaml`
2. Manually merged Azure OpenAI credentials and custom settings
3. Updated `.env` variable names to match new config expectations
4. Added explicit `vector_store.index_schema` with `vector_size: 1536` for text-embedding-3-small

### Key Insight
Don't try to incrementally patch a major config format change. Generate a fresh config and merge your customizations into it. Keep a backup of the old config for reference.

---

## Challenge 9: Prompt Template Incompatibilities

### Problem
Custom prompt templates that worked with GraphRAG 1.2.0 contained placeholders that were no longer injected by the v3.x runtime, causing `KeyError` exceptions during indexing.

### Error
```
KeyError: 'max_length'
```

### Affected Prompts

| File | Removed Placeholder |
|------|---------------------|
| `prompts/summarize_descriptions.txt` | `{max_length}` |
| `prompts/global_search_map_system_prompt.txt` | `{max_length}` |
| `prompts/global_search_reduce_system_prompt.txt` | `{max_length}` |
| `prompts/community_report_text.txt` | `{max_report_length}` |
| `prompts/community_report_graph.txt` | `{max_report_length}` |

### Solution
Removed the unsupported placeholders from all prompt files. In v3.x, these parameters are controlled via `settings.yaml` under the workflow sections (e.g., `summarize_descriptions.max_length: 500`, `community_reports.max_length: 2000`).

### Key Insight
Custom prompts are a **hidden migration risk**. If you've customized any prompts from the defaults, test each one individually after upgrading. The safest approach is to regenerate prompts with `graphrag init --force` and re-apply only your custom wording changes.

---

## Challenge 10: Knowledge Graph Statistics Shift After Re-indexing

### Problem
After completing the migration and re-indexing with GraphRAG 3.0.1, the knowledge graph statistics changed significantly:

| Metric | v1.2.0 | v3.0.1 | Change |
|--------|--------|--------|--------|
| Entities | 176 | 147 | -16.5% |
| Relationships | 342 | 263 | -23.1% |
| Communities | 33 | 32 | -3.0% |

### Root Cause
This was **NOT data loss**. GraphRAG 3.x includes improved entity deduplication and graph summarization algorithms:

1. **Better entity resolution**: v3.x more aggressively merges near-duplicate entities (e.g., "Azure OpenAI Service" and "Azure OpenAI" now correctly resolve to a single entity)
2. **Improved relationship deduplication**: Redundant relationships between the same entity pairs are consolidated
3. **Refined community detection**: The Leiden algorithm parameters were tuned, producing slightly fewer but more meaningful communities

### Verification
Confirmed via notebook exploration:
- Core entities (people, projects, technologies) are all preserved
- Relationship types and weights remain accurate
- Community reports still capture all organizational themes
- Search quality (local and global) is equal or better

### Key Insight
After any GraphRAG version upgrade, **compare statistics and verify search quality** rather than only checking that code runs. A decrease in entity/relationship counts usually indicates better deduplication, not data loss. Document the before/after numbers for transparency.

---

## Challenge 11: MCP Transport Protocol (SSE vs Streamable HTTP)

### Problem
The MCP Server originally used `sse_app()` transport for Server-Sent Events, but the Microsoft Agent Framework's `MCPStreamableHTTPTool` requires the Streamable HTTP transport.

```
Error: Session terminated (MCP client expected Streamable HTTP, server exposed SSE)
```

### Root Cause
MCP (Model Context Protocol) supports two HTTP transports:

| Transport | Use Case | Endpoint |
|-----------|----------|----------|
| **SSE (Server-Sent Events)** | Browser clients, MCP Inspector UI | `/sse` |
| **Streamable HTTP** | Agent Framework, programmatic clients | `/mcp` |

The `MCPStreamableHTTPTool` from Agent Framework uses Streamable HTTP protocol, not SSE.

### Solution
Changed `mcp_server/server.py` from:

```python
# Before: SSE transport
app = mcp.sse_app()
```

To:

```python
# After: Streamable HTTP transport
app = mcp.streamable_http_app()
```

Also updated the endpoint from `/sse` to `/mcp` for clarity.

### Key Insight
When integrating MCP servers with different clients:
- **MCP Inspector / Browsers**: Use `sse_app()` on `/sse`
- **Agent Framework / Code clients**: Use `streamable_http_app()` on `/mcp`
- Production servers may need to expose both transports on different endpoints

---

## Challenge 12: Microsoft Agent Framework API Changes

### Problem
Initial agent implementation used incorrect class names and parameters based on outdated assumptions.

```python
# Error 1: Class doesn't exist
from agent_framework import ChatAgent  # ❌ ImportError

# Error 2: Wrong client type
client = AsyncAzureOpenAI(...)  # ❌ Type mismatch

# Error 3: Wrong parameters
Agent(chat_client=client, model="gpt-4o")  # ❌ Unknown parameters
```

### Root Cause
The Microsoft Agent Framework (`agent-framework-core ^1.0.0b260212`) has its own patterns:

1. **Class name**: `Agent` not `ChatAgent`
2. **Client wrapper**: `AzureOpenAIChatClient` not raw `AsyncAzureOpenAI`
3. **Parameters**: `client` and `instructions` not `chat_client` and `model`

### Solution

```python
# Correct imports
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.azure import AzureOpenAIChatClient

# Correct client
client = AzureOpenAIChatClient(
    endpoint=config.azure_endpoint,
    deployment_name=config.deployment_name,
    api_key=config.api_key,
    api_version=config.api_version,
)

# Correct agent creation
agent = Agent(
    client=client,
    name="knowledge_captain",
    instructions=SYSTEM_PROMPT,
    tools=[mcp_tool],
)
```

### Key Insight
The Microsoft Agent Framework is still in beta (note the `b` in version). Always verify:
1. Import paths via `from agent_framework import *`
2. Client wrappers from `agent_framework.azure`
3. Constructor parameters from the actual class signatures

---

## Challenge 13: Conversation Memory with AgentSession

### Problem
Follow-up questions lost context from previous exchanges because each `agent.run()` call was stateless.

```
User: Who leads Project Alpha?
Agent: Dr. Sarah Chen leads Project Alpha...

User: What about their background?  
Agent: I don't know who you're referring to...  ← Lost context
```

### Root Cause
The `Agent.run()` method is stateless by default. Each call starts fresh without memory of previous exchanges.

### Solution
Use `AgentSession` to maintain conversation history:

```python
from agent_framework import AgentSession

# Create session once per conversation
session = AgentSession()

# Pass session to each run call
result = await agent.run("Who leads Project Alpha?", session=session)

# Follow-up questions now have context
result = await agent.run("What about their background?", session=session)
```

### Implementation Pattern

```python
class KnowledgeCaptainRunner:
    async def __aenter__(self):
        self._session = AgentSession()  # Create on connect
        return self
    
    async def ask(self, question: str):
        return await self.agent.run(question, session=self._session)
    
    def clear_history(self):
        self._session = AgentSession()  # Reset conversation
```

### Key Insight
Agent Framework separates:
- **Agent**: Stateless processor with tools and instructions
- **Session**: Stateful container for conversation history

This design allows:
- Multiple users sharing one Agent instance
- Explicit control over when to clear history
- Easy serialization of conversation state (future feature)

---

## Summary

### Critical Success Factors

1. ✅ **Model availability research before region selection**
2. ✅ **Cost-performance analysis for embedding models**
3. ✅ **Multi-region architecture when beneficial**
4. ✅ **Remote state management with proper bootstrap**
5. ✅ **Validation and testing at each deployment step**
6. ✅ **Full backup before major version migration**
7. ✅ **Codebase-wide search for outdated references after migration**
8. ✅ **Generate fresh config files instead of incremental patching**
9. ✅ **Test custom prompts individually after framework upgrade**
10. ✅ **Compare knowledge graph statistics before and after re-indexing**
11. ✅ **Match MCP transport to client type (SSE vs Streamable HTTP)**
12. ✅ **Verify Agent Framework APIs from actual imports, not documentation**
13. ✅ **Use AgentSession for multi-turn conversation memory**

### Final Architecture

| Component | Region | Model/SKU | Rationale |
|-----------|--------|-----------|-----------|
| Azure OpenAI | westus | GPT-4o + text-embedding-3-small | Model availability, lower demand |
| Storage Account | southcentralus | Standard LRS | Quota availability |
| App Services | southcentralus | TBD | Quota availability, proximity to storage |
| GraphRAG | — | v3.0.1 (migrated from v1.2.0) | numpy 2.x compat, agent-framework support |

**Estimated Monthly Cost** (based on 30K TPM, moderate usage):
- Azure OpenAI: ~$150-300
- Storage Account: ~$20-50
- **Total**: ~$170-350/month

**Cost Savings**: ~$176/month from text-embedding-3-small selection

---

## Next Steps

1. ~~Test Terraform deployment with updated configuration~~ ✅
2. ~~Generate `.env` file from outputs~~ ✅
3. ~~Commit infrastructure code to git~~ ✅
4. ~~Implement MCP Server (Part 2)~~ ✅
5. ~~Implement Supervisor Agent Pattern (Part 3)~~ ✅
6. Implement Agent Evaluation (Part 4)

---

**Document Version**: 3.0  
**Last Updated**: February 16, 2026  
**Author**: Cristopher Coronado  
**Series**: MAF + GraphRAG - Parts 1, 2 & 3
