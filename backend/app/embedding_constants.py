"""Версия и размерность векторов вкуса / фото (должны совпадать у photo_embeddings и user_taste_vectors)."""

# OpenCLIP ViT-B/32 через fastembed ImageEmbedding — 512 измерений.
EMBEDDING_MODEL_VERSION = "fastembed-vit-b-32"
EMBEDDING_DIM = 512

# EMA профиля пользователя после лайка/дизлайка (k от view_time умножается отдельно).
TASTE_EMA_ALPHA_BASE = 0.22
