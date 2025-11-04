from src.recommendation.events.llm_generator import load_events_csv, process_events

# Загружаем CSV
events = load_events_csv("events.csv")

# Обрабатываем (например, первые 5)
processed = process_events(events, limit=5)

print("\n✅ Всего обработано:", len(processed))
