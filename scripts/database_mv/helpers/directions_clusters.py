"""Helper utilities for clustering academic directions and loading them into the DB."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.core.database.connection import engine
from src.core.database.models import Clusters, Directions
from src.recommendation.students import clusterize_directions

from .preprocess_excel import FILTERED_FILE, preprocess_excel

BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = BASE_DIR / "results" / "directions"


def _ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def insert_clusters_and_directions(
    df_clusters: pd.DataFrame,
    embeddings: np.ndarray,
    final_labels: Iterable[int],
    embed_dim: int,
) -> None:
    """Persist clustered directions into the database."""

    with Session(engine) as db:
        print("🗑️ Удаление существующих кластеров и направлений...")
        deleted_directions = db.execute(delete(Directions)).rowcount
        deleted_clusters = db.execute(delete(Clusters)).rowcount
        db.commit()
        print(
            f"   Удалено направлений: {deleted_directions}, кластеров: {deleted_clusters}"
        )

        cluster_ids: dict[int, str] = {}
        unique_cluster_labels = sorted(set(int(lbl) for lbl in final_labels))
        print(f"\n📦 Создание {len(unique_cluster_labels)} кластеров...")

        for cluster_label in unique_cluster_labels:
            indices = [i for i, lbl in enumerate(final_labels) if int(lbl) == cluster_label]
            cluster_vectors = embeddings[indices]
            centroid = cluster_vectors.mean(axis=0)
            if centroid.size < embed_dim:
                centroid = np.pad(centroid, (0, embed_dim - centroid.size))
            title = f"Кластер {cluster_label + 1}"
            cluster = Clusters(title=title, centroid=centroid.tolist())
            db.add(cluster)
            db.commit()
            db.refresh(cluster)
            cluster_ids[cluster_label] = cluster.id
            print(
                "   ✅ Создан кластер "
                f"'{title}' (ID: {cluster.id}, метка: {cluster_label}, направлений: {len(indices)})"
            )

        print(f"\n✅ Всего создано кластеров: {len(cluster_ids)}")
        print(f"   Метки кластеров: {list(cluster_ids.keys())}")

        print(f"\n📚 Создание {len(df_clusters)} направлений...")
        directions_without_cluster: list[tuple[str, int]] = []
        directions_added = 0

        for _, row in df_clusters.iterrows():
            cluster_label = int(row["Кластер"])
            direction_title = str(row["Направление"]).strip()
            cluster_id = cluster_ids.get(cluster_label)

            if cluster_id is None:
                directions_without_cluster.append((direction_title, cluster_label))
                print(
                    "   ⚠️ Направление "
                    f"'{direction_title}' не имеет кластера (метка: {cluster_label})"
                )
            else:
                direction = Directions(title=direction_title, cluster_id=cluster_id)
                db.add(direction)
                directions_added += 1
                if directions_added <= 5 or directions_added % 50 == 0:
                    print(
                        "   ✅ Добавлено направление "
                        f"'{direction_title}' -> кластер {cluster_label} (ID: {cluster_id})"
                    )

        db.commit()
        print(f"\n✅ Добавлено направлений: {directions_added}")

        if directions_without_cluster:
            print(
                f"\n⚠️ ВНИМАНИЕ: {len(directions_without_cluster)} направлений не были связаны с кастерами:"
            )
            for title, label in directions_without_cluster[:10]:
                print(f"   - {title} (метка кластера: {label})")
            if len(directions_without_cluster) > 10:
                print(f"   ... и еще {len(directions_without_cluster) - 10} направлений")

        final_clusters_count = db.scalar(select(func.count(Clusters.id)))
        final_directions_count = db.scalar(select(func.count(Directions.id)))

        print("\n📊 Итоговая проверка:")
        print(f"   Кластеров в БД: {final_clusters_count}")
        print(f"   Направлений в БД: {final_directions_count}")

        print("\n🔍 Детальная проверка связей:")
        all_clusters = db.scalars(select(Clusters)).all()
        for cluster in all_clusters[:10]:
            directions_in_cluster = db.scalars(
                select(Directions).where(Directions.cluster_id == cluster.id)
            ).all()
            print(f"   {cluster.title}: {len(directions_in_cluster)} направлений")
            if not directions_in_cluster:
                print("      ⚠️ Кластер не имеет направлений!")
        if len(all_clusters) > 10:
            print(f"   ... и еще {len(all_clusters) - 10} кластеров")


def run_directions_pipeline(force_preprocess: bool = True) -> None:
    """Preprocess Excel, cluster directions and load them into the database."""

    _ensure_results_dir()

    if force_preprocess or not FILTERED_FILE.exists():
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
