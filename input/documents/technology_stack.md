# TechVenture Inc. - Technology Stack & Standards

## Programming Languages

### Primary Languages

**Python 3.11+**
- **Usage:** Backend services, AI/ML, data pipelines
- **Champions:** Dr. James Mitchell, Sophia Lee, Nina Kowalski
- **Standards:** Black formatter, Ruff linter, type hints required
- **Package Manager:** Poetry for all Python projects

**TypeScript 5.x**
- **Usage:** Frontend applications, Node.js services
- **Champions:** Mark Johnson, Carlos Martinez
- **Standards:** ESLint, Prettier, strict mode enabled
- **Package Manager:** pnpm for monorepo management

### Secondary Languages

- **Go:** Infrastructure tooling (Tom Bradley)
- **Rust:** Performance-critical components (experimental, Priya Patel)
- **SQL:** Database queries, analytics (Marcus Chen)
- **KQL:** Azure Data Explorer queries (analytics team)

## Frameworks & Libraries

### Backend Frameworks

| Framework | Version | Use Case | Owner |
|-----------|---------|----------|-------|
| FastAPI | 0.110+ | REST APIs, async services | Nina Kowalski |
| Pydantic | 2.x | Data validation | David Kumar |
| SQLAlchemy | 2.x | ORM for PostgreSQL | Marcus Chen |
| LangChain | 0.1+ | LLM orchestration | Dr. James Mitchell |
| GraphRAG | 1.2.0 | Knowledge graphs | Sophia Lee |

### Frontend Frameworks

| Framework | Version | Use Case | Owner |
|-----------|---------|----------|-------|
| Next.js | 14.x | Customer Portal, Marketing | Mark Johnson |
| React | 18.x | Component library | Carlos Martinez |
| TailwindCSS | 3.x | Styling | Carlos Martinez |
| Shadcn/ui | Latest | UI components | Design Team |
| AG-UI Protocol | 0.1+ | AI streaming interfaces | Mark Johnson, Dr. James Mitchell |

### Data & ML Libraries

| Library | Use Case | Owner |
|---------|----------|-------|
| pandas | Data manipulation | Marcus Chen |
| PyTorch | Deep learning models | Dr. James Mitchell |
| scikit-learn | Classical ML | Elena Rodriguez |
| MLflow | Model tracking | Dr. Emily Harrison |
| Azure AI SDK | Azure OpenAI integration | AI Research Team |

## Cloud Services (Azure)

### Compute

| Service | Use Case | Owner |
|---------|----------|-------|
| Azure Container Apps | Microservices hosting | Tom Bradley |
| Azure Functions | Event-driven processing | Nina Kowalski |
| Azure Machine Learning | Model training | Dr. James Mitchell |
| Azure Databricks | Big data processing | Marcus Chen |

### Data Storage

| Service | Use Case | Owner |
|---------|----------|-------|
| Azure Cosmos DB | Document store, sessions | Mark Johnson |
| Azure PostgreSQL | Transactional data | Marcus Chen |
| Azure Data Lake Gen2 | Data lake bronze/silver/gold | Marcus Chen |
| Azure Blob Storage | Files, artifacts | Tom Bradley |
| Azure Cache for Redis | Caching, rate limiting | Priya Patel |

### AI & Cognitive Services

| Service | Use Case | Owner |
|---------|----------|-------|
| Azure OpenAI (GPT-4o) | LLM for Project Alpha | Dr. James Mitchell |
| Azure OpenAI (text-embedding-3-small) | Vector embeddings | Sophia Lee |
| Azure AI Search | Hybrid search | Priya Patel |
| Azure AI Document Intelligence | Document processing | Alex Turner |

### Networking & Security

| Service | Use Case | Owner |
|---------|----------|-------|
| Azure API Management | API Gateway | Mark Johnson |
| Azure Virtual Network | Network isolation | Jennifer Park |
| Azure Key Vault | Secrets management | Jessica Nguyen |
| Azure AD B2C | Customer identity | Security Team |

## Development Tools

### IDEs & Editors

- **VS Code:** Primary IDE for all teams
  - Required extensions: Python, ESLint, Prettier, Azure Tools
  - Shared settings in `.vscode/settings.json`
- **JetBrains DataGrip:** Database management (Marcus Chen's team)
- **Jupyter Lab:** ML experimentation (AI Research)

### Version Control

- **GitHub Enterprise:** Primary repository hosting
- **Branching Strategy:** GitHub Flow (main + feature branches)
- **Code Review:** Minimum 2 approvals for main branch
- **Commit Conventions:** Conventional Commits (feat, fix, docs, etc.)

### CI/CD Tools

| Tool | Purpose | Owner |
|------|---------|-------|
| GitHub Actions | CI/CD pipelines | Tom Bradley |
| Trivy | Container security scanning | Jessica Nguyen |
| CodeQL | Static code analysis | Security Team |
| Terraform | Infrastructure as Code | Jennifer Park |
| Azure DevOps | Enterprise features, boards | Kevin Wright |

### Observability Tools

| Tool | Purpose | Owner |
|------|---------|-------|
| Azure Monitor | Infrastructure metrics | Tom Bradley |
| Application Insights | APM, distributed tracing | Tom Bradley |
| Grafana | Custom dashboards | DevOps Team |
| PagerDuty | On-call management | Jennifer Park |
| Sentry | Error tracking (frontend) | Mark Johnson |

## Communication & Collaboration

### Team Communication

- **Slack:** Primary communication (channels per project/team)
- **Microsoft Teams:** External meetings, enterprise clients
- **GitHub Discussions:** Technical RFCs, architecture decisions

### Documentation

- **Notion:** Internal wiki, runbooks, onboarding
- **GitHub Wiki:** Technical documentation per repository
- **Swagger/OpenAPI:** API documentation (auto-generated)
- **Storybook:** Component documentation (Design Team)

### Project Management

- **Linear:** Engineering task management
- **Productboard:** Product roadmap (Amanda Foster)
- **GitHub Projects:** Sprint planning

## Coding Standards

### Code Quality Requirements

1. **Test Coverage:** Minimum 80% for core services
2. **Type Safety:** Required for Python (mypy) and TypeScript (strict)
3. **Documentation:** Docstrings for public APIs
4. **Security:** No hardcoded secrets, use Key Vault references
5. **Performance:** Sub-200ms P95 latency for API endpoints

### Code Review Checklist

- [ ] Tests included and passing
- [ ] Type annotations complete
- [ ] Security review for sensitive operations
- [ ] Documentation updated
- [ ] No breaking changes without versioning
- [ ] Performance impact assessed

## Technology Radar

### Adopt (Production-ready)
- Azure Container Apps, FastAPI, Next.js 14, GraphRAG, AG-UI Protocol

### Trial (Pilot projects)
- Rust for performance-critical paths (Priya Patel experimenting)
- LangGraph for complex agent workflows (Dr. James Mitchell)
- Azure Confidential Computing for healthcare (Project Beta)

### Assess (Evaluation)
- WebAssembly for browser-based ML
- OpenTelemetry as unified observability standard
- Semantic Kernel for agent orchestration

### Hold (Not recommended)
- Self-hosted Kubernetes (use Container Apps instead)
- Synchronous batch processing (prefer event-driven)
- Monolithic architectures (microservices preferred)
