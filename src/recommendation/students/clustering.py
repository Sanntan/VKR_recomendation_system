import pandas as pd
import numpy as np
import hdbscan
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM = model.get_sentence_embedding_dimension()

def clusterize_directions(directions: list[str]):
    print(f"🧠 Векторизация {len(directions)} направлений...")
    embeddings = model.encode(directions, normalize_embeddings=True, show_progress_bar=True)

    print("🔍 Запуск HDBSCAN кластеризации...")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric="euclidean")
    labels = clusterer.fit_predict(embeddings)

    unique_labels = [lbl for lbl in set(labels) if lbl != -1]
    next_cluster_id = max(unique_labels, default=-1) + 1

    final_labels = []
    for lbl in labels:
        if lbl == -1:
            final_labels.append(next_cluster_id)
            next_cluster_id += 1
        else:
            final_labels.append(lbl)

    print(f"✅ Получено {len(set(final_labels))} кластеров (включая индивидуальные)")

    df_clusters = pd.DataFrame({
        "Направление": directions,
        "Кластер": final_labels,
        "Тип": ["индивидуальный" if l >= len(unique_labels) else "основной" for l in final_labels]
    })

    return df_clusters, embeddings, final_labels, EMBED_DIM
