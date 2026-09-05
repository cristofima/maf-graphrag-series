# MAF + GraphRAG Series - Documentation

This directory contains detailed documentation, lessons learned, and reference materials for the MAF + GraphRAG project series.

## Contents

### Implementation Notes (by Part)

Implementation notes are historical snapshots of each article part. For current
runtime entry points and active usage, use:

- [../README.md](../README.md)
- [../src/maf_graphrag/agents/README.md](../src/maf_graphrag/agents/README.md)
- [../src/maf_graphrag/workflows/README.md](../src/maf_graphrag/workflows/README.md)

| Part | Notes                                                            | Description                                         |
| ---- | ---------------------------------------------------------------- | --------------------------------------------------- |
| 1    | [part1-implementation-notes.md](./part1-implementation-notes.md) | GraphRAG setup, Azure config, version fixes         |
| 2    | [part2-implementation-notes.md](./part2-implementation-notes.md) | MCP Server integration with FastMCP                 |
| 3    | [part3-implementation-notes.md](./part3-implementation-notes.md) | Supervisor Agent Pattern (historical reference)     |
| 4    | [part4-implementation-notes.md](./part4-implementation-notes.md) | Workflow Patterns (Sequential, Concurrent, Handoff) |
| 5    | [part5-implementation-notes.md](./part5-implementation-notes.md) | Monitoring, Evaluation & Safety                     |
| 6    | [part6-implementation-notes.md](./part6-implementation-notes.md) | Production Router Integration                       |
| 7    | [part7-implementation-notes.md](./part7-implementation-notes.md) | Conversational Session Readiness                    |
| 8    | _Coming soon_                                                    | Human-in-the-Loop                                   |
| 9    | _Coming soon_                                                    | Tool Registry                                       |
| 10   | _Coming soon_                                                    | Production Deployment                               |

### Reference Documents

| Document                                                       | Description                               |
| -------------------------------------------------------------- | ----------------------------------------- |
| [lessons-learned.md](./lessons-learned.md)                     | Azure deployment challenges and solutions |
| [qa-examples.md](./qa-examples.md)                             | Real Q&A responses from GraphRAG          |
| [query-guide.md](./query-guide.md)                             | Query syntax and search types             |
| [multi-region-architecture.md](./multi-region-architecture.md) | Cross-region strategy                     |
| [uv-guide.md](./uv-guide.md)                                   | uv setup and usage guide                  |

## Documentation Purpose

These documents serve as:

- **Knowledge Base**: Reference for troubleshooting similar issues
- **Decision Log**: Context for architectural choices made
- **Learning Resource**: Educational material for the MAF community
- **Best Practices**: Reusable patterns for Azure AI deployments

## Contributing

As this series progresses through Part 8-10, additional documentation will be added:

- Part 8: Human-in-the-Loop
- Part 9: Tool Registry
- Part 10: Production Deployment

## Related Resources

- **Main README**: [../README.md](../README.md)
- **Infrastructure**: [../infra/README.md](../infra/README.md)
- **GraphRAG Settings**: [../settings.yaml](../settings.yaml)

---

**Series**: GraphRAG + Azure OpenAI (10-Part Series)
**Parts**: 1-7 complete (manual induced-timeout checkpoint run deferred with automated coverage), 8-10 pending
**Author**: Cristopher Coronado
