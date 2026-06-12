from pydantic import BaseModel, Field
from typing import List

class DocumentChunk(BaseModel):
    id: str = Field(..., description="Unique identifier for the document chunk")
    text: str = Field(..., description="Text content of the chunk")
    embedding: List[float] = Field(..., description="The embedding vector associated with the text chunk")
    source: str = Field(..., description="Source metadata/origin of the chunk")

class SearchResult(BaseModel):
    chunk: DocumentChunk = Field(..., description="The matching document chunk")
    score: float = Field(..., description="Similarity/relevance score")
