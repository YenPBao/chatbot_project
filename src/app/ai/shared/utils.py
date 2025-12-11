from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
import os
from app.core.config import settings


def _format_doc(doc: Document) -> str:
    metadata = doc.metadata or {}
    meta = "".join(f" {k}={v!r}" for k, v in metadata.items())
    if meta:
        meta = f" {meta}"

    return f"<document{meta}>\n{doc.page_content}\n</document>"


def format_docs(docs: Optional[list[Document]]) -> str:
    if not docs:
        return "<documents></documents>"
    formatted = "\n".join(_format_doc(doc) for doc in docs)
    return f"""<documents>
{formatted}
</documents>"""


def load_chat_model(fully_specified_name: str) -> BaseChatModel:
    if "/" in fully_specified_name:
        provider, model = fully_specified_name.split("/", maxsplit=1)
    else:
        provider = ""
        model = fully_specified_name

    print(f"[load_chat_model] incoming: provider={provider!r}, model={model!r}")

    if provider in {"", "openai"}:
        provider = "openai"
        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY is not set in .env / Settings.")
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key.get_secret_value()

    elif provider in {"google", "gemini"}:
        if settings.google_api_key is None:
            raise RuntimeError("GOOGLE_API_KEY is not set in .env / Settings.")
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key.get_secret_value()
        provider = "google_genai"

    print(f"[load_chat_model] normalized: provider={provider!r}, model={model!r}")
    return init_chat_model(model, model_provider=provider)
