from typing import Any

from azure.search.documents.models import VectorizedQuery

from agent_runtime.tools import ToolRegistry, ToolSpec
from approaches.approach import Approach


def register_rag_tool(registry: ToolRegistry, approach: Approach, overrides: dict[str, Any]) -> None:
    async def search_knowledge(arguments, context):
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        top = max(1, min(int(arguments.get("top") or overrides.get("top") or 5), 20))
        retrieval_mode = str(overrides.get("retrieval_mode") or "hybrid")
        use_text = retrieval_mode in ("text", "hybrid")
        use_vectors = retrieval_mode in ("vectors", "hybrid")
        vectors: list[VectorizedQuery] = []
        if use_vectors:
            vectors.append(await approach.compute_text_embedding(query))
        documents = await approach.search(
            top=top,
            query_text=query,
            filter=approach.build_filter(overrides, context.auth_claims),
            vectors=vectors,
            use_text_search=use_text,
            use_vector_search=use_vectors,
            use_semantic_ranker=bool(overrides.get("semantic_ranker")),
            use_semantic_captions=bool(overrides.get("semantic_captions")),
            minimum_search_score=overrides.get("minimum_search_score"),
            minimum_reranker_score=overrides.get("minimum_reranker_score"),
            use_query_rewriting=bool(overrides.get("query_rewriting")),
        )
        return {
            "query": query,
            "results": [document.serialize_for_results() for document in documents],
            "citations": approach.get_sources_content(
                documents,
                use_semantic_captions=bool(overrides.get("semantic_captions")),
                use_image_citation=False,
            ),
        }

    registry.register(
        ToolSpec(
            name="search_knowledge",
            description="Search the authorized enterprise knowledge base (RAG). Use it for questions about uploaded documents or indexed websites.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "A concise semantic search query"},
                    "top": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=search_knowledge,
            source="rag",
        )
    )
