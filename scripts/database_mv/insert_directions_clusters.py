from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from src.core.database.connection import engine
from src.core.database.models import Directions, Clusters
from scripts.database_mv.preprocess_excel import preprocess_excel
from src.recommendation.students import clusterize_directions

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FILTERED_FILE = RESULTS_DIR / "filtered_data.xlsx"

def insert_clusters_and_directions(df_clusters: pd.DataFrame, embeddings: np.ndarray, final_labels: list[int], embed_dim: int):
    with Session(engine) as db:
        db.execute(delete(Directions))
        db.execute(delete(Clusters))
        db.commit()

        cluster_ids = {}
        for cluster_label in sorted(set(final_labels)):
            indices = [i for i, lbl in enumerate(final_labels) if lbl == cluster_label]
            cluster_vectors = embeddings[indices]
            centroid = cluster_vectors.mean(axis=0)
            if len(centroid) < embed_dim:
                centroid = np.pad(centroid, (0, embed_dim - len(centroid)))
            title = f"Кластер {cluster_label + 1}"
            cluster = Clusters(title=title, centroid=centroid.tolist())
            db.add(cluster)
            db.commit()
            db.refresh(cluster)
            cluster_ids[cluster_label] = cluster.id

        print(f"✅ Добавлено кластеров: {len(cluster_ids)}")

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

    with Session(engine) as db:
        existing_titles = {d.lower() for d in db.scalars(select(Directions.title)).all()}
        new_dirs = [d for d in directions if d.lower() not in existing_titles]

    if not existing_titles:
        print("🆕 БД пуста. Выполняем первую кластеризацию...")
    elif new_dirs:
        print(f"⚠️ Обнаружено {len(new_dirs)} новых направлений. Пересоздаём кластеры...")
    else:
        print("✅ Новых направлений нет. Кластеризация не требуется.")
        return

    df_clusters, embeddings, final_labels, embed_dim = clusterize_directions(directions)
    insert_clusters_and_directions(df_clusters, embeddings, final_labels, embed_dim)

if __name__ == "__main__":
    main()
