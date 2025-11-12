-- ==========================================
-- ПОЛНАЯ СХЕМА БД ДЛЯ SUPABASE
-- ==========================================
-- Скопируйте весь этот файл и выполните в SQL Editor Supabase

-- ==========================================
-- РАСШИРЕНИЯ
-- ==========================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_cron";

-- ==========================================
-- ОЧИСТКА (если нужно переопределить схему)
-- ==========================================

DROP TABLE IF EXISTS favorites CASCADE;
DROP TABLE IF EXISTS recommendations CASCADE;
DROP TABLE IF EXISTS feedback CASCADE;
DROP TABLE IF EXISTS bot_users CASCADE;
DROP TABLE IF EXISTS event_clusters CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS directions CASCADE;
DROP TABLE IF EXISTS clusters CASCADE;

-- ==========================================
-- КЛАСТЕРЫ (основные тематические группы)
-- ==========================================

CREATE TABLE clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    centroid VECTOR(768),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clusters_title ON clusters(LOWER(title));

-- ==========================================
-- НАПРАВЛЕНИЯ ПОДГОТОВКИ
-- ==========================================

CREATE TABLE directions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    cluster_id UUID REFERENCES clusters(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_directions_title_cluster
    ON directions(LOWER(title), cluster_id);

-- ==========================================
-- СТУДЕНТЫ
-- ==========================================

CREATE TABLE students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id TEXT UNIQUE NOT NULL,
    institution TEXT,
    direction_id UUID REFERENCES directions(id) ON DELETE SET NULL,
    profile_embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==========================================
-- МЕРОПРИЯТИЯ
-- ==========================================

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    short_description TEXT,
    description TEXT,
    format TEXT,
    start_date DATE,
    end_date DATE,
    link TEXT,
    image_url TEXT,
    vector_embedding VECTOR(768),
    likes_count INT NOT NULL DEFAULT 0 CHECK (likes_count >= 0),
    dislikes_count INT NOT NULL DEFAULT 0 CHECK (dislikes_count >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==========================================
-- СВЯЗЬ МЕРОПРИЯТИЕ ↔ КЛАСТЕР
-- ==========================================

CREATE TABLE event_clusters (
    id SERIAL PRIMARY KEY,
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    cluster_id UUID REFERENCES clusters(id) ON DELETE CASCADE,
    CONSTRAINT event_clusters_unique UNIQUE (event_id, cluster_id)
);

-- ==========================================
-- РЕКОМЕНДАЦИИ
-- ==========================================

CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    event_id UUID REFERENCES events(id) ON DELETE CASCADE,
    score DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recs_student ON recommendations(student_id);
CREATE INDEX IF NOT EXISTS idx_recs_event ON recommendations(event_id);
CREATE INDEX IF NOT EXISTS idx_recs_score ON recommendations(score);

-- ==========================================
-- ОБРАТНАЯ СВЯЗЬ
-- ==========================================

CREATE TABLE feedback (
    id SERIAL PRIMARY KEY,
    student_id UUID REFERENCES students(id) ON DELETE CASCADE,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==========================================
-- ТЕЛЕГРАМ-ПОЛЬЗОВАТЕЛИ
-- ==========================================

CREATE TABLE bot_users (
    telegram_id BIGINT PRIMARY KEY,
    student_id UUID UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    username TEXT,
    last_activity TIMESTAMP DEFAULT NOW(),
    email TEXT,
    is_linked BOOLEAN NOT NULL DEFAULT FALSE
);

-- ==========================================
-- ИЗБРАННЫЕ МЕРОПРИЯТИЯ
-- ==========================================

CREATE TABLE favorites (
    id SERIAL PRIMARY KEY,
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT favorites_unique UNIQUE (student_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_favorites_student ON favorites(student_id);
CREATE INDEX IF NOT EXISTS idx_favorites_event ON favorites(event_id);
CREATE INDEX IF NOT EXISTS idx_favorites_created ON favorites(created_at DESC);

-- ==========================================
-- ИНДЕКСЫ
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_events_vector
    ON events USING ivfflat (vector_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_students_vector
    ON students USING ivfflat (profile_embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_directions_cluster ON directions(cluster_id);
CREATE INDEX IF NOT EXISTS idx_students_direction ON students(direction_id);
CREATE INDEX IF NOT EXISTS idx_event_clusters_cluster ON event_clusters(cluster_id);
CREATE INDEX IF NOT EXISTS idx_event_clusters_event ON event_clusters(event_id);
CREATE INDEX IF NOT EXISTS idx_events_is_active ON events(is_active);
CREATE INDEX IF NOT EXISTS idx_events_dates ON events(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_directions_id_cluster ON directions(id, cluster_id);

-- ==========================================
-- ПЛАНИРОВЩИК: авто-деактивация прошедших мероприятий
-- ==========================================

SELECT cron.schedule(
    'deactivate_past_events',
    '0 3 * * *',
    $$
    UPDATE events
    SET is_active = FALSE
    WHERE end_date < CURRENT_DATE AND is_active = TRUE;
    $$
);

-- ==========================================
-- ИЗМЕНЕНИЕ РАЗМЕРА ВЕКТОРОВ С 768 НА 384
-- ==========================================

ALTER TABLE clusters ALTER COLUMN centroid TYPE vector(384);
ALTER TABLE students ALTER COLUMN profile_embedding TYPE vector(384);
ALTER TABLE events ALTER COLUMN vector_embedding TYPE vector(384);

DROP INDEX IF EXISTS idx_events_vector;
CREATE INDEX idx_events_vector 
    ON events USING ivfflat (vector_embedding vector_cosine_ops);

DROP INDEX IF EXISTS idx_students_vector;
CREATE INDEX idx_students_vector 
    ON students USING ivfflat (profile_embedding vector_cosine_ops);

