from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from sentence_transformers import SentenceTransformer
import hdbscan

from src.core.database.connection import engine
from src.core.database.models import Directions, Clusters
from scripts.database_mv.preprocess_excel import preprocess_excel


# === Пути ===
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FILTERED_FILE = RESULTS_DIR / "filtered_data.xlsx"

# === Модель эмбеддингов ===
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
EMBED_DIM = model.get_sentence_embedding_dimension()  # обычно 384

def clusterize_directions(directions: list[str]):
    """Векторизация и кластеризация направлений"""
    print(f"🧠 Векторизация {len(directions)} направлений...")
    embeddings = model.encode(directions, normalize_embeddings=True, show_progress_bar=True)

    print("🔍 Запуск HDBSCAN кластеризации...")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1, metric="euclidean")
    labels = clusterer.fit_predict(embeddings)

    # обработка выбросов (-1)
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

    return df_clusters, embeddings, final_labels


def insert_clusters_and_directions(df_clusters: pd.DataFrame, embeddings: np.ndarray, final_labels: list[int]):
    """Сохраняет кластеры и направления в базу"""
    with Session(engine) as db:
        # === Удаляем старые данные перед вставкой ===
        db.execute(delete(Directions))
        db.execute(delete(Clusters))
        db.commit()

        # === Создаём кластеры ===
        cluster_ids = {}
        for cluster_label in sorted(set(final_labels)):
            indices = [i for i, lbl in enumerate(final_labels) if lbl == cluster_label]
            cluster_vectors = embeddings[indices]
            centroid = cluster_vectors.mean(axis=0)
            # паддинг если нужно
            if len(centroid) < EMBED_DIM:
                centroid = np.pad(centroid, (0, EMBED_DIM - len(centroid)))
            title = f"Кластер {cluster_label + 1}"
            cluster = Clusters(title=title, centroid=centroid.tolist())
            db.add(cluster)
            db.commit()
            db.refresh(cluster)
            cluster_ids[cluster_label] = cluster.id

        print(f"✅ Добавлено кластеров: {len(cluster_ids)}")

        # === Добавляем направления ===
        for idx, row in df_clusters.iterrows():
            cluster_id = cluster_ids.get(row["Кластер"])
            db.add(Directions(title=row["Направление"], cluster_id=cluster_id))
        db.commit()

        print(f"✅ Добавлено направлений: {len(df_clusters)}")


def main():
    print("🔄 Шаг 1: Предобработка Excel...")
    preprocess_excel()

    if not FILTERED_FILE.exists():
        raise FileNotFoundError(f"❌ Не найден файл {FILTERED_FILE}")

    df = pd.read_excel(FILTERED_FILE)
    if "Специальность" not in df.columns:
        raise ValueError("❌ В файле отсутствует столбец 'Специальность'")

    directions = (
        df["Специальность"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: s != ""]
        .drop_duplicates()
        .tolist()
    )

    print(f"📚 Найдено {len(directions)} уникальных направлений")

    # === Проверка на новые направления ===
    with Session(engine) as db:
        existing_titles = {d.title.lower() for d in db.scalars(select(Directions.title)).all()}
        new_dirs = [d for d in directions if d.lower() not in existing_titles]

    if not existing_titles:
        print("🆕 БД пуста. Выполняем первую кластеризацию...")
    elif new_dirs:
        print(f"⚠️ Обнаружено {len(new_dirs)} новых направлений. Пересоздаём кластеры...")
    else:
        print("✅ Новых направлений нет. Кластеризация не требуется.")
        return

    # === Запуск кластеризации и вставки ===
    df_clusters, embeddings, final_labels = clusterize_directions(directions)
    insert_clusters_and_directions(df_clusters, embeddings, final_labels)


if __name__ == "__main__":
    main()
