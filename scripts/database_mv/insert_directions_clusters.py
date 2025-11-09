from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func

from src.core.database.connection import engine
from src.core.database.models import Directions, Clusters
from scripts.database_mv.preprocess_excel import preprocess_excel
from src.recommendation.students import clusterize_directions

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
FILTERED_FILE = RESULTS_DIR / "filtered_data.xlsx"

def insert_clusters_and_directions(df_clusters: pd.DataFrame, embeddings: np.ndarray, final_labels: list[int], embed_dim: int):
    with Session(engine) as db:
        # Удаляем существующие данные
        print("🗑️ Удаление существующих кластеров и направлений...")
        deleted_directions = db.execute(delete(Directions)).rowcount
        deleted_clusters = db.execute(delete(Clusters)).rowcount
        db.commit()
        print(f"   Удалено направлений: {deleted_directions}, кластеров: {deleted_clusters}")

        # Создаем кластеры
        cluster_ids = {}
        unique_cluster_labels = sorted(set(final_labels))
        print(f"\n📦 Создание {len(unique_cluster_labels)} кластеров...")
        
        for cluster_label in unique_cluster_labels:
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
            print(f"   ✅ Создан кластер '{title}' (ID: {cluster.id}, метка: {cluster_label}, направлений: {len(indices)})")

        print(f"\n✅ Всего создано кластеров: {len(cluster_ids)}")
        print(f"   Метки кластеров: {list(cluster_ids.keys())}")

        # Создаем направления
        print(f"\n📚 Создание {len(df_clusters)} направлений...")
        directions_without_cluster = []
        directions_added = 0
        
        for idx, row in df_clusters.iterrows():
            # Преобразуем метку кластера в int для надежности
            cluster_label = int(row["Кластер"])
            direction_title = str(row["Направление"]).strip()
            
            # Проверяем наличие кластера
            cluster_id = cluster_ids.get(cluster_label)
            
            if cluster_id is None:
                directions_without_cluster.append((direction_title, cluster_label))
                print(f"   ⚠️ Направление '{direction_title}' не имеет кластера (метка: {cluster_label}, тип: {type(cluster_label)})")
                print(f"      Доступные метки кластеров: {list(cluster_ids.keys())[:10]}...")
            else:
                direction = Directions(title=direction_title, cluster_id=cluster_id)
                db.add(direction)
                directions_added += 1
                if directions_added <= 5 or directions_added % 50 == 0:
                    print(f"   ✅ Добавлено направление '{direction_title}' -> кластер {cluster_label} (ID: {cluster_id})")
        
        db.commit()
        print(f"\n✅ Добавлено направлений: {directions_added}")
        
        if directions_without_cluster:
            print(f"\n⚠️ ВНИМАНИЕ: {len(directions_without_cluster)} направлений не были связаны с кластерами:")
            for title, label in directions_without_cluster[:10]:
                print(f"   - {title} (метка кластера: {label})")
            if len(directions_without_cluster) > 10:
                print(f"   ... и еще {len(directions_without_cluster) - 10} направлений")
        
        # Проверяем результат
        final_clusters_count = db.scalar(select(func.count(Clusters.id)))
        final_directions_count = db.scalar(select(func.count(Directions.id)))
        
        print(f"\n📊 Итоговая проверка:")
        print(f"   Кластеров в БД: {final_clusters_count}")
        print(f"   Направлений в БД: {final_directions_count}")
        
        # Дополнительная проверка: показываем направления для каждого кластера
        print(f"\n🔍 Детальная проверка связей:")
        all_clusters = db.scalars(select(Clusters)).all()
        for cluster in all_clusters[:10]:  # Показываем первые 10 кластеров
            directions_in_cluster = db.scalars(select(Directions).where(Directions.cluster_id == cluster.id)).all()
            print(f"   {cluster.title}: {len(directions_in_cluster)} направлений")
            if len(directions_in_cluster) == 0:
                print(f"      ⚠️ Кластер не имеет направлений!")
        if len(all_clusters) > 10:
            print(f"   ... и еще {len(all_clusters) - 10} кластеров")

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
