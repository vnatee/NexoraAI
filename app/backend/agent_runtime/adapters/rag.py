import logging
from typing import Any

from azure.search.documents.models import VectorizedQuery

from agent_runtime.tools import ToolRegistry, ToolSpec
from approaches.approach import Approach
from core.attachment_retrieval import bounded_attachment_evidence


def register_rag_tool(
    registry: ToolRegistry,
    approach: Approach,
    overrides: dict[str, Any],
    *,
    include_enterprise: bool = True,
) -> None:
    configured_attachment_ids = overrides.get("_temporary_attachment_ids") or []

    async def search_knowledge(arguments, context):
        query = str(arguments.get("query") or "").strip()
        if not query:
            raise ValueError("query is required")
        top = max(1, min(int(arguments.get("top") or overrides.get("top") or 5), 20))
        attachment_results = []
        attachment_index = overrides.get("_temporary_attachment_index")
        attachment_ids = configured_attachment_ids
        if attachment_index and attachment_ids:
            attachment_results = await attachment_index.search(
                owner_id=str(overrides.get("_temporary_attachment_owner_id") or ""),
                conversation_id=str(overrides.get("_temporary_attachment_conversation_id") or ""),
                query=query,
                attachment_ids=attachment_ids,
                limit=top,
            )
        documents = []
        if include_enterprise:
            try:
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
            except Exception:
                if not attachment_results:
                    raise
                logging.exception("Enterprise knowledge search failed; returning selected temporary attachments")
        attachment_evidence = bounded_attachment_evidence(attachment_results)
        attachment_sources = [
            f"{citation}: {text}"
            for _, citation, text in attachment_evidence
        ]
        return {
            "query": query,
            "results": [document.serialize_for_results() for document in documents],
            "temporary_attachment_results": [
                {
                    "source": citation,
                    "filename": result.filename,
                    "page": result.page_number,
                    "section": result.page_label,
                    "content": text,
                    "untrusted": True,
                }
                for result, citation, text in attachment_evidence
            ],
            "citations": [
                *approach.get_sources_content(
                    documents,
                    use_semantic_captions=bool(overrides.get("semantic_captions")),
                    use_image_citation=False,
                ),
                *attachment_sources,
            ],
        }

    registry.register(
        ToolSpec(
            name="search_knowledge",
            description=(
                "Search the authorized enterprise knowledge base and selected private temporary attachments."
                    if include_enterprise and configured_attachment_ids
                else "Search the authorized enterprise knowledge base (RAG). Use it for questions about uploaded documents or indexed websites."
                if include_enterprise
                else "Search only the private temporary document attachments selected for this conversation."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A concise semantic search query",
                    },
                    "top": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=search_knowledge,
            source="rag",
        )
    )
