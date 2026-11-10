"""Konfigurasi aplikasi ICALORA-LABS (dibaca dari environment / .env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Aplikasi
    app_name: str = "ICALORA-LABS API"
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    cors_origins: str = Field(default="http://localhost:3000")

    # PostgreSQL (infra lokal: 127.0.0.1:54432)
    postgres_host: str = Field(default="127.0.0.1")
    postgres_port: int = Field(default=54432)
    postgres_user: str = Field(default="icalora")
    postgres_password: str = Field(default="")
    postgres_db: str = Field(default="icalora")

    # Redis (infra lokal: 127.0.0.1:54379)
    redis_host: str = Field(default="127.0.0.1")
    redis_port: int = Field(default=54379)
    redis_password: str = Field(default="")

    # SeaweedFS S3 (infra lokal: 127.0.0.1:54333)
    s3_endpoint: str = Field(default="http://127.0.0.1:54333")
    s3_access_key: str = Field(default="icalora")
    s3_secret_key: str = Field(default="")
    s3_region: str = Field(default="us-east-1")
    s3_bucket: str = Field(default="icalora")

    # LLM (Ollama bersama di server: 127.0.0.1:11434)
    llm_provider: str = Field(default="ollama")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434")
    ollama_model: str = Field(default="qwen2.5:7b-instruct")
    ollama_embed_model: str = Field(default="bge-m3")
    llm_timeout: int = Field(default=120)
    # Durasi model tetap dimuat di VRAM setelah panggilan terakhir. "5m" = 5 menit
    # (default Ollama), "0" = langsung dilepas setelah tiap panggilan (hemat VRAM
    # saat server dibagi 24/7), "-1" = selalu residen. Dapat diubah via .env.
    ollama_keep_alive: str = Field(default="5m")

    # Ingest korpus
    contact_email: str = Field(default="")  # mailto polite-pool OpenAlex/Crossref
    ingest_page_size: int = Field(default=200)
    core_api_key: str = Field(default="")
    semantic_scholar_api_key: str = Field(default="")
    ncbi_api_key: str = Field(default="")

    # Bot Telegram (akses privat)
    telegram_bot_token: str = Field(default="")
    telegram_allowed_chat_ids: str = Field(default="")  # daftar id dipisah koma
    telegram_bot_secret: str = Field(default="")  # wajib untuk perintah krusial
    backend_base_url: str = Field(default="http://127.0.0.1:58010")

    # Auth / sesi
    session_secret: str = Field(default="icalora-dev-secret-change-me")
    session_cookie: str = Field(default="icalora_session")
    session_ttl_days: int = Field(default=30)
    history_retention_days: int = Field(default=3)
    frontend_base_url: str = Field(default="http://localhost:58030")
    allow_demo_login: bool = Field(default=False)
    admin_password: str = Field(default="")
    admin_email: str = Field(default="admin@icalora-labs.local")
    admin_name: str = Field(default="Super Admin")
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")

    # Email (SMTP) untuk notifikasi kata sandi
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from: str = Field(default="")
    google_redirect_uri: str = Field(
        default="http://localhost:58030/api/backend/auth/google/callback"
    )

    # Cek sumber daring (tanpa unduh) — query API akademik gratis secara
    # real-time. OpenAlex/Crossref/arXiv/Wikipedia bebas; CORE perlu key +
    # aktif hanya bila lisensi mengizinkan (lihat ToS CORE).
    online_check_enabled: bool = Field(default=True)
    core_api_key: str = Field(default="")
    core_enabled: bool = Field(default=True)
    # Ambil teks-PENUH open-access (PDF/HTML) untuk paper yang teridentifikasi
    # sebagai publikasi dokumen (DOI/judul sendiri). Diproses ephemeral di
    # memori saat pengecekan — TIDAK disimpan ke disk/DB, jadi tak menambah
    # penyimpanan. Ini membuat % plagiarisme akurat untuk karya terbit/duplikat.
    online_fulltext_enabled: bool = Field(default=True)
    online_fulltext_max_bytes: int = Field(default=20 * 1024 * 1024)
    online_fulltext_max_docs: int = Field(default=5)
    # Selain kandidat ber-identitas-publikasi, ambil teks-PENUH OA untuk
    # kandidat PALING MIRIP (calon sumber plagiarisme) agar perbandingan
    # mencakup seluruh isi sumber, bukan hanya abstrak. Tetap ephemeral
    # (di memori, tak disimpan) → nol tambahan disk.
    online_fulltext_similar_docs: int = Field(default=8)
    # Penyedia Open Access tambahan (gratis, legal — hanya metadata/abstrak OA).
    # DOAJ: Directory of Open Access Journals (banyak jurnal Indonesia).
    # Unpaywall: resolver DOI → URL PDF OA legal (memperluas cakupan teks-penuh).
    online_doaj_enabled: bool = Field(default=True)
    online_unpaywall_enabled: bool = Field(default=True)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/0"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
