# 05 — Pilihan Teknologi & Struktur Folder

Rekomendasi stack untuk ICALORA-LABS. Semua dibangun **fresh** untuk proyek ini (self-contained).

---

## Stack Rekomendasi

### Frontend
- **Next.js** (App Router) + **TypeScript**
- **Tailwind CSS** + komponen UI (shadcn/ui)
- **React Query / tRPC** untuk data fetching
- **WebSocket/polling** untuk status job

### Backend
- **Python 3.12 + FastAPI** (ideal untuk beban ML/AI)
- **Pydantic** untuk validasi
- **Celery / RQ** untuk antrian job berat
- **Uvicorn/Gunicorn** sebagai server

### Data & Index
- **PostgreSQL** (data utama)
- **pgvector** atau **Qdrant** (vector search)
- **SeaweedFS** (S3-compatible object storage, open-source)
- **Redis** (cache + broker antrian)

### ML / AI
- **sentence-transformers** (embedding)
- **datasketch** (MinHash) / SimHash untuk near-duplicate
- **PyTorch + Hugging Face Transformers** (AI detector classifier)
- **scikit-learn** (fitur stylometry & baseline)
- **Abstraksi LLM**: adapter agar bisa pilih provider (API komersial atau model open-source self-hosted)

### Infra / DevOps
- **Docker + docker-compose** (dev)
- **GitHub Actions** (CI/CD)
- Reverse proxy (Caddy/Nginx)

---

## Struktur Folder (usulan monorepo)

```
icalora-labs/
├── README.md
├── docs/                      # dokumen rencana (ini)
├── docker-compose.yml
├── frontend/                  # Next.js app
│   ├── app/
│   ├── components/
│   │   └── report-viewer/     # komponen laporan (highlight, sumber)
│   ├── lib/
│   └── package.json
├── backend/                   # FastAPI
│   ├── app/
│   │   ├── api/               # endpoint per fitur
│   │   ├── core/              # config, auth, db
│   │   ├── services/
│   │   │   ├── llm/           # fitur ringan (chat, grammar, dst.)
│   │   │   ├── plagiarism/    # engine similarity
│   │   │   ├── ai_detector/   # classifier + statistik
│   │   │   ├── authorship/    # stylometry
│   │   │   └── citation/      # Crossref/OpenAlex
│   │   ├── workers/           # Celery/RQ tasks
│   │   └── models/            # schema DB & pydantic
│   └── pyproject.toml
├── corpus/                    # pipeline data
│   ├── ingest/                # konektor OpenAlex/PMC/DOAJ/CORE
│   ├── process/               # clean, segment, fingerprint, embed
│   └── index/                 # builder MinHash & vector index
├── ml/                        # training & eksperimen
│   ├── ai_detector/           # dataset + training classifier
│   └── authorship/            # stylometry
└── infra/                     # deployment, env, scripts
```

---

## Keputusan yang Perlu Diambil Saat Eksekusi
1. **LLM provider**: API komersial (cepat, biaya per-token) vs model open-source self-hosted (kontrol penuh, butuh GPU). → bisa hybrid.
2. **Vector DB**: pgvector (sederhana, satu DB) vs Qdrant (khusus, skalabel). → mulai pgvector, migrasi bila perlu.
3. **Hosting**: VPS/GPU server vs cloud managed. → sesuai anggaran.

> Semua keputusan ini ditetapkan saat mulai Fase 0, bukan sekarang.
