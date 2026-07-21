# MAF + GraphRAG Series - Documentation

This directory contains detailed documentation, lessons learned, and reference materials for the MAF + GraphRAG project series.

## Contents

### Implementation Notes (by Part)

| Part | Notes                                                            | Description                                         |
| ---- | ---------------------------------------------------------------- | --------------------------------------------------- |
| 1    | [part1-implementation-notes.md](./part1-implementation-notes.md) | GraphRAG setup, Azure config, version fixes         |
| 2    | [part2-implementation-notes.md](./part2-implementation-notes.md) | MCP Server integration with FastMCP                 |
| 3    | [part3-implementation-notes.md](./part3-implementation-notes.md) | Supervisor Agent Pattern                            |
| 4    | [part4-implementation-notes.md](./part4-implementation-notes.md) | Workflow Patterns (Sequential, Concurrent, Handoff) |
| 5    | [part5-implementation-notes.md](./part5-implementation-notes.md) | Monitoring, Evaluation & Safety                     |
| 6+   | _Coming soon_                                                    | Human-in-the-Loop, Tool Registry, Production        |

### Reference Documents

| Document                                                       | Description                               |
| -------------------------------------------------------------- | ----------------------------------------- |
| [lessons-learned.md](./lessons-learned.md)                     | Azure deployment challenges and solutions |
| [qa-examples.md](./qa-examples.md)                             | Real Q&A responses from GraphRAG          |
| [query-guide.md](./query-guide.md)                             | Query syntax and search types             |
| [multi-region-architecture.md](./multi-region-architecture.md) | Cross-region strategy                     |
| [poetry-guide.md](./poetry-guide.md)                           | Poetry setup and usage guide              |

## Documentation Purpose

These documents serve as:

- **Knowledge Base**: Reference for troubleshooting similar issues
- **Decision Log**: Context for architectural choices made
- **Learning Resource**: Educational material for the MAF community
- **Best Practices**: Reusable patterns for Azure AI deployments

## Contributing

As this series progresses through Part 6-8, additional documentation will be added:

- Part 6: Human-in-the-Loop
- Part 7: Tool Registry
- Part 8: Production Deployment

## Related Resources

- **Main README**: [../README.md](../README.md)
- **Infrastructure**: [../infra/README.md](../infra/README.md)
- **GraphRAG Settings**: [../settings.yaml](../settings.yaml)

---

**Series**: GraphRAG + Azure OpenAI (8-Part Series)
**Parts**: 1-5 complete (GraphRAG Fundamentals, MCP Server, Supervisor Agent, Workflow Patterns, Agent Evaluation)
**Author**: Cristopher Coronado
