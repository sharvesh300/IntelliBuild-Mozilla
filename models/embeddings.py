from typing import List, Optional
from pydantic import BaseModel, Field

class EmbeddingResult(BaseModel):
    embedding: List[float] = Field(..., description="The embedding vector")

class EmbeddingResponse(BaseModel):
    results: List[EmbeddingResult] = Field(..., description="The list of embedding results")
    model_id: str = Field(..., description="The ID of the model used to generate the embeddings")

    @property
    def first_embedding(self) -> Optional[List[float]]:
        """Helper property to easily get the first embedding vector."""
        if self.results and len(self.results) > 0:
            return self.results[0].embedding
        return None

    @property
    def embeddings(self) -> List[List[float]]:
        """Helper property to get list of all raw embedding vectors."""
        return [res.embedding for res in self.results]
