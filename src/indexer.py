"""
GraphRAG Indexing Pipeline
===========================

This script builds the knowledge graph from documents in the input/ directory.
It performs:
1. Document chunking
2. Entity extraction (using GPT-4o)
3. Relationship detection
4. Community detection (Leiden algorithm)
5. Community summarization
6. Embeddings generation (using text-embedding-3-small)

Output: Parquet files in output/ directory containing:
- entities.parquet
- relationships.parquet
- communities.parquet
- community_reports.parquet
- text_units.parquet

Usage:
    python src/indexer.py
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from graphrag.index import create_pipeline_config
from graphrag.index.run import run_pipeline_with_config

# Load environment variables
load_dotenv()

# Verify required environment variables
required_vars = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_CHAT_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    print(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
    print("\nPlease ensure your .env file contains:")
    for var in required_vars:
        print(f"  {var}=<your-value>")
    sys.exit(1)


async def run_indexing():
    """
    Run the GraphRAG indexing pipeline.
    
    This will:
    1. Read documents from input/documents/
    2. Extract entities and relationships using GPT-4o
    3. Detect communities using the Leiden algorithm
    4. Generate embeddings using text-embedding-3-small
    5. Save results to output/ directory
    """
    
    # Get project root directory
    root_dir = Path(__file__).parent.parent
    
    # Verify settings.yaml exists
    settings_path = root_dir / "settings.yaml"
    if not settings_path.exists():
        print(f"❌ Error: settings.yaml not found at {settings_path}")
        sys.exit(1)
    
    # Verify input documents exist
    input_dir = root_dir / "input" / "documents"
    if not input_dir.exists() or not any(input_dir.glob("*.md")):
        print(f"❌ Error: No markdown documents found in {input_dir}")
        sys.exit(1)
    
    print("🚀 Starting GraphRAG Indexing Pipeline\n")
    print(f"📂 Input Directory: {input_dir}")
    print(f"📂 Output Directory: {root_dir / 'output'}")
    print(f"⚙️  Settings File: {settings_path}")
    print(f"\n🔑 Using Azure OpenAI:")
    print(f"   Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"   Chat Model: {os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT')}")
    print(f"   Embedding Model: {os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT')}")
    print("\n" + "="*60 + "\n")
    
    try:
        # Run the pipeline
        # Note: GraphRAG CLI equivalent: graphrag index --root .
        print("⏳ Building knowledge graph...")
        print("   This may take several minutes depending on document size.\n")
        
        # The run_pipeline_with_config will automatically use settings.yaml
        # from the root directory
        result = await run_pipeline_with_config(
            config_or_path=str(settings_path),
            root_dir=str(root_dir)
        )
        
        print("\n" + "="*60)
        print("✅ Indexing Complete!\n")
        
        # Check output files
        output_dir = root_dir / "output"
        output_files = [
            "entities.parquet",
            "relationships.parquet", 
            "communities.parquet",
            "community_reports.parquet",
            "text_units.parquet"
        ]
        
        print("📊 Generated Files:")
        for filename in output_files:
            filepath = output_dir / filename
            if filepath.exists():
                size_mb = filepath.stat().st_size / (1024 * 1024)
                print(f"   ✓ {filename} ({size_mb:.2f} MB)")
            else:
                print(f"   ✗ {filename} (not found)")
        
        print("\n💡 Next Steps:")
        print("   1. Run local search: python src/local_search.py")
        print("   2. Run global search: python src/global_search.py")
        print("   3. Explore graph: Open notebooks/01_explore_graph.ipynb\n")
        
    except Exception as e:
        print(f"\n❌ Error during indexing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run the async indexing pipeline
    asyncio.run(run_indexing())
