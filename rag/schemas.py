\
\
\
\
\
\
\
\
\
\
\
\
\
\
\
\
\


from pydantic import BaseModel, Field



MetadataValue = str | int | float | bool


class ParsedDocument(BaseModel):
\
\
\
\
\


    source_path: str
    file_name: str
    file_type: str
    file_hash: str
    text: str
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class DocumentChunk(BaseModel):
\
\
\
\
\
\
\
\
\
\


    chunk_id: str
    file_id: str
    source_path: str
    file_name: str
    file_type: str
    file_hash: str
    chunk_index: int
    text: str
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class IndexedFileRecord(BaseModel):
\
\
\
\
\
\
\


    file_id: str
    source_path: str
    file_name: str
    file_type: str
    file_hash: str
    chunk_ids: list[str] = Field(default_factory=list)
    last_indexed_at: str
    warnings: list[str] = Field(default_factory=list)


class IndexManifest(BaseModel):
\
\
\
\
\
\
\


    index_version: int = 1
    vector_store: str = "chroma"
    collection_name: str = "trade_business_docs"
    embedding_provider: str
    embedding_model: str
    files: dict[str, IndexedFileRecord] = Field(default_factory=dict)


class SearchHit(BaseModel):
\
\
\
\
\


    chunk_id: str
    file_id: str
    source_path: str
    file_name: str
    file_type: str
    file_hash: str
    chunk_index: int
    score: float
    text: str
    metadata: dict[str, MetadataValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RagAnswer(BaseModel):
\
\
\
\
\


    answer: str
    sources: list[SearchHit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
