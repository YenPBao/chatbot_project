import os
from contextlib import contextmanager
from typing import Generator

from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableConfig
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_chroma import Chroma

try:
    # These optional providers may not be installed in the analysis environment.
    from langchain_cohere import CohereEmbeddings  # type: ignore[import]
except Exception:  # pragma: no cover
    CohereEmbeddings = None  # type: ignore


from app.ai.shared.configuration import BaseConfiguration


def make_text_encoder(model: str) -> Embeddings:
    provider, model = model.split("/", maxsplit=1)
    match provider:
        case "openai":
            from langchain_openai import OpenAIEmbeddings

            return OpenAIEmbeddings(model=model)
        case "cohere":
            if CohereEmbeddings is None:
                raise RuntimeError("Cohere embeddings provider not installed")
            return CohereEmbeddings(model=model)  # type: ignore
        case _:
            raise ValueError(f"Unsupported embedding provider: {provider}")


@contextmanager
def make_chroma_retriever(
    configuration, embedding_model
) -> Generator[VectorStoreRetriever, None, None]:
    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
    collection = os.environ.get("CHROMA_COLLECTION", "langchain_index")

    vstore = Chroma(
        collection_name=collection,
        persist_directory=persist_dir,
        embedding_function=embedding_model,
    )
    yield vstore.as_retriever(search_kwargs=configuration.search_kwargs)


@contextmanager
def make_elastic_retriever(
    configuration: BaseConfiguration, embedding_model: Embeddings
):

    connection_options = {}
    provider = configuration.retriever_provider

    if provider == "elastic-local":
        if os.getenv("ELASTICSEARCH_USER") and os.getenv("ELASTICSEARCH_PASSWORD"):
            connection_options = {
                "es_user": os.environ["ELASTICSEARCH_USER"],
                "es_password": os.environ["ELASTICSEARCH_PASSWORD"],
            }
        else:
            connection_options = {}
    else:
        connection_options = {"es_api_key": os.environ["ELASTICSEARCH_API_KEY"]}

    try:
        from langchain_elasticsearch import ElasticsearchStore  # type: ignore[import]
    except Exception:
        raise RuntimeError("Elasticsearch store provider not installed")

    vstore = ElasticsearchStore(
        es_url=os.environ["ELASTICSEARCH_URL"],
        index_name="langchain_index",
        embedding=embedding_model,
        **connection_options,
    )
    yield vstore.as_retriever(search_kwargs=configuration.search_kwargs)


@contextmanager
def make_pinecone_retriever(
    configuration: BaseConfiguration, embedding_model: Embeddings
) -> Generator[VectorStoreRetriever, None, None]:
    """Configure this agent to connect to a specific pinecone index."""
    from langchain_pinecone import PineconeVectorStore  # type: ignore[import]

    vstore = PineconeVectorStore.from_existing_index(
        os.environ["PINECONE_INDEX_NAME"], embedding=embedding_model
    )
    yield vstore.as_retriever(search_kwargs=configuration.search_kwargs)


@contextmanager
def make_mongodb_retriever(
    configuration: BaseConfiguration, embedding_model: Embeddings
) -> Generator[VectorStoreRetriever, None, None]:
    """Configure this agent to connect to a specific MongoDB Atlas index & namespaces."""
    from langchain_mongodb.vectorstores import MongoDBAtlasVectorSearch  # type: ignore[import]

    vstore = MongoDBAtlasVectorSearch.from_connection_string(
        os.environ["MONGODB_URI"],
        namespace="langgraph_retrieval_agent.default",
        embedding=embedding_model,
    )
    yield vstore.as_retriever(search_kwargs=configuration.search_kwargs)


@contextmanager
def make_retriever(
    config: RunnableConfig,
) -> Generator[VectorStoreRetriever, None, None]:
    """Create a retriever for the agent, based on the current configuration."""
    configuration = BaseConfiguration.from_runnable_config(config)
    embedding_model = make_text_encoder(configuration.embedding_model)
    match configuration.retriever_provider:
        case "elastic" | "elastic-local":
            with make_elastic_retriever(configuration, embedding_model) as retriever:
                yield retriever

        case "pinecone":
            with make_pinecone_retriever(configuration, embedding_model) as retriever:
                yield retriever

        case "mongodb":
            with make_mongodb_retriever(configuration, embedding_model) as retriever:
                yield retriever
        case "chroma":
            with make_chroma_retriever(configuration, embedding_model) as r:
                yield r

        case _:
            raise ValueError(
                "Unrecognized retriever_provider in configuration. "
                f"Expected one of: {', '.join(BaseConfiguration.__annotations__['retriever_provider'].__args__)}\n"
                f"Got: {configuration.retriever_provider}"
            )
