-- Skema korpus ICALORA-LABS (ingest dataset).
-- Dijalankan otomatis (CREATE ... IF NOT EXISTS) oleh app.ingest.common.ensure_schema().

CREATE TABLE IF NOT EXISTS corpus_documents (
    id           BIGSERIAL PRIMARY KEY,
    source       TEXT NOT NULL,            -- 'openalex' | 'pmc' | 'core' | ...
    external_id  TEXT NOT NULL,            -- id unik di sumber (mis. OpenAlex work id)
    doi          TEXT,
    title        TEXT,
    license      TEXT,                     -- lisensi paper (untuk keputusan full-text)
    pub_year     INT,
    lang         TEXT,
    fields       TEXT[],                   -- konsep/bidang
    word_count   INT,
    char_count   INT,
    text_zstd    BYTEA,                    -- teks (abstrak) terkompresi zstd
    has_embedding BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_corpus_source      ON corpus_documents (source);
CREATE INDEX IF NOT EXISTS idx_corpus_year        ON corpus_documents (pub_year);
CREATE INDEX IF NOT EXISTS idx_corpus_license     ON corpus_documents (license);
CREATE INDEX IF NOT EXISTS idx_corpus_no_embed    ON corpus_documents (id) WHERE has_embedding = FALSE;

-- Sidik jari MinHash (deteksi salinan & near-duplicate)
CREATE TABLE IF NOT EXISTS corpus_fingerprints (
    doc_id    BIGINT PRIMARY KEY REFERENCES corpus_documents(id) ON DELETE CASCADE,
    num_perm  SMALLINT NOT NULL,
    minhash   BYTEA NOT NULL              -- array uint64 little-endian (num_perm elemen)
);

-- Embedding semantik (deteksi parafrase) — bge-m3 = 1024 dim, dihitung di GPU
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS corpus_embeddings (
    doc_id    BIGINT PRIMARY KEY REFERENCES corpus_documents(id) ON DELETE CASCADE,
    embedding halfvec(1024) NOT NULL
);

-- Index ANN untuk pencarian kemiripan semantik (cosine)
-- halfvec (float16): ~50% lebih hemat disk vs vector(float32), akurasi ~setara.
CREATE INDEX IF NOT EXISTS idx_corpus_emb_hnsw
    ON corpus_embeddings USING hnsw (embedding halfvec_cosine_ops);

-- Status pekerjaan ingest (resumable)
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id             BIGSERIAL PRIMARY KEY,
    source         TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'running',  -- running|paused|done|error
    cursor         TEXT,                             -- cursor API terakhir (resume)
    params         JSONB NOT NULL DEFAULT '{}'::jsonb,
    docs_ingested  BIGINT NOT NULL DEFAULT 0,
    docs_target    BIGINT,
    last_error     TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingest_source_status ON ingest_jobs (source, status);
