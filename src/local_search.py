"""
GraphRAG Local Search
=====================

Local search is optimized for answering specific questions about entities
and their direct relationships. It focuses on a subset of the knowledge graph.

Best for:
- "Who works on Project Alpha?"
- "What technologies does Sarah Chen use?"
- "What is the relationship between David Kumar and Emily Harrison?"

Usage:
    python src/local_search.py "Your question here"
    
Example:
    python src/local_search.py "Who leads Project Alpha?"
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from graphrag.query.indexer_adapters import read_indexer_entities, read_indexer_reports
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.local_search.mixed_context import LocalSearchMixedContext
from graphrag.query.structured_search.local_search.search import LocalSearch
from graphrag.vector_stores.lancedb import LanceDBVectorStore

# Load environment variables
load_dotenv()


async def perform_local_search(query: str):
    """
    Perform a local search query against the knowledge graph.
    
    Args:
        query: The question to ask
        
    Returns:
        Search results with context and response
    """
    
    # Get project root
    root_dir = Path(__file__).parent.parent
    output_dir = root_dir / "output"
    
    # Verify output files exist
    required_files = ["entities.parquet", "relationships.parquet", "text_units.parquet"]
    missing_files = [f for f in required_files if not (output_dir / f).exists()]
    
    if missing_files:
        print(f"❌ Error: Missing required files: {', '.join(missing_files)}")
        print("\nPlease run the indexer first: python src/indexer.py")
        sys.exit(1)
    
    print("🔍 Local Search Query\n")
    print(f"Question: {query}\n")
    print("="*60 + "\n")
    
    try:
        # Initialize LLM
        llm = ChatOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_type=OpenaiApiType.AzureOpenAI,
            model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            api_version="2024-02-15-preview",
            max_retries=3,
        )
        
        # Initialize vector store for embeddings
        description_embedding_store = LanceDBVectorStore(
            collection_name="entity_description_embeddings",
        )
        description_embedding_store.connect(db_uri=str(output_dir / "lancedb"))
        
        # Load entities and relationships
        print("📚 Loading knowledge graph...")
        entities = read_indexer_entities(
            entities=output_dir / "entities.parquet",
            entity_embeddings=output_dir / "embeddings.parquet",
            community_level=2
        )
        
        # Build context
        context_builder = LocalSearchMixedContext(
            community_reports=read_indexer_reports(
                output_dir / "community_reports.parquet",
                output_dir / "entities.parquet",
                community_level=2
            ),
            text_units=output_dir / "text_units.parquet",
            entities=entities,
            entity_text_embeddings=description_embedding_store,
        )
        
        # Initialize search engine
        search_engine = LocalSearch(
            llm=llm,
            context_builder=context_builder,
            response_type="multiple paragraphs",
        )
        
        # Perform search
        print("🤔 Thinking...\n")
        result = await search_engine.asearch(query)
        
        print("💬 Answer:\n")
        print(result.response)
        print("\n" + "="*60 + "\n")
        
        # Show context used
        if result.context_data:
            print("📖 Context Used:")
            entities_used = result.context_data.get("entities", [])
            if entities_used:
                print(f"   • {len(entities_used)} entities")
            relationships_used = result.context_data.get("relationships", [])
            if relationships_used:
                print(f"   • {len(relationships_used)} relationships")
            print()
        
    except Exception as e:
        print(f"\n❌ Error during search: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/local_search.py \"Your question here\"")
        print("\nExample:")
        print('  python src/local_search.py "Who leads Project Alpha?"')
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    asyncio.run(perform_local_search(query))
