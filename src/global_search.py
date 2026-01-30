"""
GraphRAG Global Search
======================

Global search is optimized for answering broad, thematic questions that
require understanding of the entire knowledge graph and its communities.

Best for:
- "What are the main projects at TechVenture?"
- "Summarize the organizational structure"
- "What are the key technologies being used?"
- "What are the relationships between departments?"

Usage:
    python src/global_search.py "Your question here"
    
Example:
    python src/global_search.py "What are the main themes in this organization?"
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from graphrag.query.indexer_adapters import read_indexer_entities, read_indexer_reports
from graphrag.query.llm.oai.chat_openai import ChatOpenAI
from graphrag.query.llm.oai.typing import OpenaiApiType
from graphrag.query.structured_search.global_search.community_context import (
    GlobalCommunityContext,
)
from graphrag.query.structured_search.global_search.search import GlobalSearch

# Load environment variables
load_dotenv()


async def perform_global_search(query: str):
    """
    Perform a global search query against the knowledge graph.
    
    Args:
        query: The question to ask
        
    Returns:
        Search results with comprehensive answer
    """
    
    # Get project root
    root_dir = Path(__file__).parent.parent
    output_dir = root_dir / "output"
    
    # Verify output files exist
    required_files = ["entities.parquet", "community_reports.parquet"]
    missing_files = [f for f in required_files if not (output_dir / f).exists()]
    
    if missing_files:
        print(f"❌ Error: Missing required files: {', '.join(missing_files)}")
        print("\nPlease run the indexer first: python src/indexer.py")
        sys.exit(1)
    
    print("🌍 Global Search Query\n")
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
        
        # Load data
        print("📚 Loading knowledge graph communities...")
        entities = read_indexer_entities(
            entities=output_dir / "entities.parquet",
            entity_embeddings=output_dir / "embeddings.parquet",
            community_level=2
        )
        
        reports = read_indexer_reports(
            reports=output_dir / "community_reports.parquet",
            entities=output_dir / "entities.parquet",
            community_level=2
        )
        
        # Build context from community reports
        context_builder = GlobalCommunityContext(
            community_reports=reports,
            entities=entities,
            token_encoder=None,  # Will use default
        )
        
        # Initialize search engine
        search_engine = GlobalSearch(
            llm=llm,
            context_builder=context_builder,
            max_data_tokens=12000,  # From settings.yaml
        )
        
        # Perform search
        print("🤔 Analyzing communities...\n")
        result = await search_engine.asearch(query)
        
        print("💬 Answer:\n")
        print(result.response)
        print("\n" + "="*60 + "\n")
        
        # Show context used
        if result.context_data:
            print("📖 Context Used:")
            communities = result.context_data.get("reports", [])
            if communities:
                print(f"   • {len(communities)} community reports analyzed")
            print()
        
    except Exception as e:
        print(f"\n❌ Error during search: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/global_search.py \"Your question here\"")
        print("\nExample:")
        print('  python src/global_search.py "What are the main themes in this organization?"')
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    asyncio.run(perform_global_search(query))
