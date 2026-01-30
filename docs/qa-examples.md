# GraphRAG Q&A Examples

This document demonstrates GraphRAG's ability to answer complex questions by leveraging the knowledge graph built from organizational documents.

## Understanding Search Types

| Search Type | Best For | How It Works |
|-------------|----------|--------------|
| **Local** | Entity-specific questions | Searches entities and their direct relationships |
| **Global** | Thematic/broad questions | Analyzes community reports across the organization |

---

## Local Search Examples

Local search excels at answering questions about **specific entities** and their **direct relationships**.

### Example 1: Leadership Query

**Question:**
```
Who leads Project Alpha and what is their role?
```

**Command:**
```powershell
.\run_query.ps1 "Who leads Project Alpha and what is their role?" -Method local
```

**Response:**

> ## Leadership of Project Alpha
>
> Project Alpha is led by Dr. Emily Harrison, who serves as the Project Lead. Dr. Harrison is the Head of AI Research at TechVenture Inc., and she plays a pivotal role in overseeing the overall project strategy and research direction. Her responsibilities include coordinating between all contributing teams, managing product management aspects, hosting demo sessions, providing monthly updates, and managing timeline risks.
>
> ## Role and Responsibilities
>
> Dr. Emily Harrison's leadership in Project Alpha involves several key responsibilities. She is deeply involved in advanced AI research, focusing on machine learning models and algorithm development. Her expertise in natural language processing and knowledge graphs is crucial for the project's success. As the Project Lead, Dr. Harrison collaborates on machine learning infrastructure needs and ensures that the project aligns with the strategic goals of TechVenture Inc.
>
> Dr. Harrison's role is supported by a team of specialists, including Dr. James Mitchell, who focuses on large language model integration, and Sophia Lee, who works on knowledge graph construction. Together, they contribute to the technical and strategic aspects of Project Alpha.

---

### Example 2: Technology Stack Query

**Question:**
```
What technologies are used in Project Alpha?
```

**Command:**
```powershell
.\run_query.ps1 "What technologies are used in Project Alpha?" -Method local
```

**Response:**

> # Technologies Used in Project Alpha
>
> Project Alpha, TechVenture Inc.'s flagship initiative, employs a diverse array of cutting-edge technologies to build an enterprise-grade AI assistant platform.
>
> ## AI and Machine Learning Technologies
>
> The AI and machine learning components of Project Alpha are primarily built using **Azure OpenAI**, specifically leveraging **GPT-4o** for natural language processing tasks. This technology is crucial for developing the NLP engine, which is led by Alex Turner, focusing on query understanding and intent classification.
>
> Additionally, the project utilizes **Microsoft GraphRAG** for knowledge graph construction, a task spearheaded by Sophia Lee. This technology is integrated with **Azure AI Search** to enhance semantic search capabilities and entity extraction.
>
> ## Backend and API Technologies
>
> The backend infrastructure of Project Alpha is developed using **Python** and **FastAPI**, which are essential for API development and integration. Mark Johnson leads the API Gateway development, ensuring seamless integration with Nina Kowalski's backend services.
>
> ## Frontend Technologies
>
> For frontend development, Project Alpha employs **Next.js** and **TypeScript**, along with the **AG-UI Protocol** for real-time streaming. These technologies are crucial for implementing the user interface and experience.
>
> ## Infrastructure and Deployment Technologies
>
> The infrastructure and deployment aspects of Project Alpha are managed using **Azure Container Apps** and **GitHub Actions**. Tom Bradley is responsible for setting up CI/CD pipelines and ensuring observability through **Azure Monitor** and **Application Insights**.
>
> ## Data and Observability Technologies
>
> For data management, Project Alpha utilizes **Azure Cosmos DB** and **Azure Blob Storage**, ensuring efficient data handling and storage.

---

## Global Search Examples

Global search is ideal for **thematic questions** that span the entire organization.

### Example 3: Strategic Initiatives

**Question:**
```
What are the main themes and strategic initiatives at TechVenture Inc?
```

**Command:**
```powershell
.\run_query.ps1 "What are the main themes and strategic initiatives at TechVenture Inc?" -Method global
```

**Response:**

> ## Main Themes at TechVenture Inc.
>
> TechVenture Inc. is a mid-sized technology company that specializes in AI-powered enterprise solutions and distributed systems. The company employs over 150 people across three main divisions, positioning itself as a significant player in the enterprise software market.
>
> A key theme at TechVenture Inc. is **cross-departmental collaboration**, which is especially emphasized in the context of Project Alpha. This collaboration is crucial for the project's success and exemplifies the company's commitment to innovation and teamwork.
>
> Another important theme is the company's strong focus on **AI research and development**. Key figures such as Dr. Emily Harrison and Michael Rodriguez play pivotal roles in advancing AI research and development at TechVenture Inc.
>
> ## Strategic Initiatives
>
> ### Project Alpha
>
> Project Alpha is TechVenture Inc.'s flagship initiative, focused on developing an AI assistant platform. It integrates cutting-edge technologies such as natural language processing, knowledge graph technology, and real-time data analytics. The project is expected to launch in the third quarter of 2026 with a substantial budget of $8 million.
>
> ### Azure Migration
>
> The Azure Migration is another significant cross-departmental initiative at TechVenture Inc. Led by Jennifer Park with support from David Kumar's engineering team, this project is crucial for enhancing the company's cloud capabilities and ensuring scalability.

---

### Example 4: Organizational Structure

**Question:**
```
How are departments connected at TechVenture Inc?
```

**Command:**
```powershell
.\run_query.ps1 "How are departments connected at TechVenture Inc?" -Method global
```

**Response:**

> ### Cross-Departmental Collaboration at TechVenture Inc.
>
> TechVenture Inc. exemplifies a strong culture of cross-departmental collaboration, which is crucial for the success of its complex projects.
>
> #### Project Alpha
>
> Project Alpha is a prime example of the need for coordinated efforts across departments. This project underscores TechVenture Inc.'s commitment to innovation and teamwork.
>
> #### Azure Migration
>
> The Azure Migration is another significant cross-departmental initiative, led by Jennifer Park with support from David Kumar's engineering team. This project is vital for enhancing the company's cloud capabilities and ensuring scalability.
>
> #### AI Research and Development
>
> In the realm of AI research and development, the collaboration between Dr. Emily Harrison and Michael Rodriguez is pivotal. Dr. Harrison leads the AI Research Department and reports to Michael Rodriguez, who ensures that her work aligns with the company's strategic goals.
>
> #### Customer Portal Development
>
> The development of the Customer Portal is a joint effort involving key figures such as David Kumar, Carlos Martinez, and Amanda Foster. This project highlights the interdisciplinary approach taken by TechVenture Inc.
>
> ### Conclusion
>
> Overall, TechVenture Inc.'s projects demonstrate the importance of inter-departmental collaboration in achieving strategic goals and fostering innovation.

---

## When to Use Each Search Type

| Question Type | Use Local | Use Global |
|---------------|-----------|------------|
| "Who works on X?" | ✅ | |
| "What does person Y do?" | ✅ | |
| "What technologies does Z use?" | ✅ | |
| "What are the main themes?" | | ✅ |
| "Summarize the organization" | | ✅ |
| "How are teams connected?" | | ✅ |
| "What patterns exist across projects?" | | ✅ |

## Key Insights

1. **Data Citations**: GraphRAG includes data citations like `[Data: Reports (2, 5)]` showing which community reports and entities contributed to the answer.

2. **Structured Responses**: Answers are well-structured with headings and organized content.

3. **Relationship Awareness**: Unlike standard RAG, GraphRAG understands multi-hop relationships (e.g., "Dr. Harrison → leads → Project Alpha → uses → Azure OpenAI").

4. **Community Understanding**: Global search leverages community detection to provide thematic summaries that span the entire organization.

---

## Running Your Own Queries

```powershell
# Activate the virtual environment
.\.venv\Scripts\Activate

# Local search (entity-focused)
.\run_query.ps1 "Your specific question about an entity" -Method local

# Global search (thematic)
.\run_query.ps1 "Your broad question about themes or patterns" -Method global
```

See [query-guide.md](query-guide.md) for more query options and configurations.
