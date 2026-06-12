from encoderfile import EncoderfileBuilder, ModelType

builder = EncoderfileBuilder(
    name="minilm-embeddings",
    model_type=ModelType.Embedding,
    path="./models/all-MiniLM-L6-v2",
)

builder.build()