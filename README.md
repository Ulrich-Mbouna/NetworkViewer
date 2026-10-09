# Réseau électrique TriPhase + Gemma 4

Modélisation d’un réseau électrique (zones, lignes, composants) avec :

- **Backend** FastAPI — store, validation (cycles), export Excalidraw, chat / image via Gemma 4
- **Frontend** Vue 3 + Vite + **UIKit** + **Tailwind CSS** + **Vue Flow** (graphe zones/lignes)

## Prérequis

- Python 3.11+
- Node.js 20+
- Clé API Google (`GOOGLE_API_KEY`) pour Gemma 4 via Gemini API

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # renseigner GOOGLE_API_KEY
uvicorn app.main:app --reload --port 8000
```

API : http://127.0.0.1:8000/docs

Au démarrage, le fixture `fixtures/cas_test_zones.json` (5 zones) est chargé si le store est vide.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

UI : http://localhost:5173 — les appels `/api` sont proxifiés vers le backend.

Stack UI : composants **UIKit** (navbar, cards, buttons, notifications) + utilitaires **Tailwind**.

## Endpoints principaux

| Méthode | Route | Rôle |
|---------|--------|------|
| GET | `/api/health` | Santé |
| GET/PUT | `/api/network` | Lire / remplacer le réseau |
| POST | `/api/network/from-image` | Image → Gemma → merge |
| POST | `/api/chat` | Chat NL → mutations |
| GET | `/api/validate` | Cycles, refs, warnings |
| GET | `/api/suggestions` | Suggestions de correction |
| POST | `/api/ops` | Appliquer des mutations structurées |
| GET | `/api/export/excalidraw` | Scène `.excalidraw` |
