from abc import ABC
from enum import Enum
from typing import Optional, Union

from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient, SearchIndexerClient

from core.knowledge_search import KnowledgeSearchClient, QdrantKnowledgeSearchClient

USER_AGENT = "azure-search-chat-demo/1.0.0"


class SearchInfo:
    """
    Class representing a connection to a search service
    To learn more, please visit https://learn.microsoft.com/azure/search/search-what-is-azure-search
    """

    def __init__(
        self,
        endpoint: str,
        credential: Union[AsyncTokenCredential, AzureKeyCredential],
        index_name: str,
        use_agentic_retrieval: Optional[bool] = False,
        agent_name: Optional[str] = None,
        agent_max_output_tokens: Optional[int] = None,
        azure_openai_searchagent_model: Optional[str] = None,
        azure_openai_searchagent_deployment: Optional[str] = None,
        azure_openai_endpoint: Optional[str] = None,
        provider: str = "azure",
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        qdrant_vector_size: Optional[int] = None,
        qdrant_vector_field: str = "embedding",
    ):
        self.endpoint = endpoint
        self.credential = credential
        self.index_name = index_name
        self.agent_name = agent_name
        self.agent_max_output_tokens = agent_max_output_tokens
        self.use_agentic_retrieval = use_agentic_retrieval
        self.azure_openai_searchagent_model = azure_openai_searchagent_model
        self.azure_openai_searchagent_deployment = azure_openai_searchagent_deployment
        self.azure_openai_endpoint = azure_openai_endpoint
        self.provider = provider
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.qdrant_vector_size = qdrant_vector_size
        self.qdrant_vector_field = qdrant_vector_field

    def create_search_client(self) -> KnowledgeSearchClient:
        if self.provider == "qdrant":
            if not self.qdrant_url or not self.qdrant_vector_size:
                raise ValueError("Qdrant URL and vector size are required")
            return QdrantKnowledgeSearchClient(
                endpoint=self.qdrant_url,
                collection_name=self.index_name,
                vector_size=self.qdrant_vector_size,
                vector_field=self.qdrant_vector_field,
                api_key=self.qdrant_api_key,
            )
        return SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=self.credential)

    def create_search_index_client(self) -> SearchIndexClient:
        return SearchIndexClient(endpoint=self.endpoint, credential=self.credential)

    def create_search_indexer_client(self) -> SearchIndexerClient:
        return SearchIndexerClient(endpoint=self.endpoint, credential=self.credential)


class DocumentAction(Enum):
    Add = 0
    Remove = 1
    RemoveAll = 2


class Strategy(ABC):
    """
    Abstract strategy for ingesting documents into a search service. It has a single setup step to perform any required initialization, and then a run step that actually ingests documents into the search service.
    """

    async def setup(self):
        raise NotImplementedError

    async def run(self):
        raise NotImplementedError
