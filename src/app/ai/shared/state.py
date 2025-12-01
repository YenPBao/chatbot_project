import uuid
from typing import Any, Literal, Optional, Union
from langchain_core.documents import Document

_UUID_NS = uuid.NAMESPACE_URL  # hoặc NAMESPACE_DNS

def _generate_uuid(page_content: str) -> str:
    return str(uuid.uuid5(_UUID_NS, page_content))

def reduce_docs(
    existing: Optional[list[Document]],
    new: Union[list[Document], list[dict[str, Any]], list[str], str, Literal["delete"]],
) -> list[Document]:
    if new == "delete":
        return []

    existing_list = list(existing) if existing else []
    existing_ids = {doc.metadata.get("uuid") for doc in existing_list}

    def ensure_doc(item: Any) -> Optional[Document]:
        if isinstance(item, Document):
            uid = item.metadata.get("uuid") or _generate_uuid(item.page_content)
            md = dict(item.metadata or {})
            md["uuid"] = uid
            return Document(page_content=item.page_content, metadata=md)

        if isinstance(item, str):
            uid = _generate_uuid(item)
            return Document(page_content=item, metadata={"uuid": uid})

        if isinstance(item, dict):
            page = item.get("page_content", "")
            md = dict(item.get("metadata", {}) or {})
            uid = md.get("uuid") or _generate_uuid(page)
            md["uuid"] = uid
            return Document(page_content=page, metadata=md)

        return None

    if isinstance(new, str):
        doc = ensure_doc(new)
        return existing_list + ([doc] if doc and doc.metadata["uuid"] not in existing_ids else [])

    out = []
    if isinstance(new, list):
        for item in new:
            doc = ensure_doc(item)
            if not doc:
                continue
            uid = doc.metadata.get("uuid")
            if uid and uid not in existing_ids:
                existing_ids.add(uid)
                out.append(doc)

    return existing_list + out
