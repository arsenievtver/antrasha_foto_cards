"""Версия и размерность векторов вкуса / фото (должны совпадать у photo_embeddings и user_taste_vectors)."""

# CLIP ViT-B/32 vision encoder (fastembed) — 512 измерений.
FASTEMBED_IMAGE_MODEL = "Qdrant/clip-ViT-B-32-vision"
EMBEDDING_MODEL_VERSION = "fastembed-clip-vit-b-32-vision"
EMBEDDING_DIM = 512

# EMA профиля пользователя после лайка/дизлайка (k от view_time умножается отдельно).
TASTE_EMA_ALPHA_BASE = 0.22
