# TriPhase — Modélisation de réseau électrique assistée par Gemma 4

Application full-stack pour **concevoir, visualiser et corriger** un réseau électrique à partir d’un JSON, d’une image ou d’un chat en langage naturel.

Le modèle de langage **Gemma 4** (API Google) propose des mutations ; le backend **valide et applique** de façon déterministe (cycles, références, types). Le frontend affiche la topologie en graphe interactif, exportable vers **Excalidraw**.

---

## Le problème que le projet cherche à résoudre

Concevoir ou documenter un réseau électrique (zones, centrales, générateurs, charges, liaisons) reste souvent **fragmenté et fragile** :

1. **Sources hétérogènes** — la topologie arrive en schéma papier/image, en JSON ad hoc, ou en description orale ; il n’y a pas de chemin unique pour en faire un modèle cohérent.
2. **Erreurs structurelles invisibles** — cycles d’alimentation, zones isolées, références cassées ou IDs dupliqués passent facilement inaperçus tant qu’on n’a pas un validateur dédié.
3. **Écart entre intention et modèle** — on décrit une modification en langage naturel (« ajoute une centrale dans la zone 2 »), mais la faire entrer correctement dans une structure hiérarchique (zone → power station → générateur, charges, lignes) demande du travail manuel et de l’expertise du schéma.
4. **Peu de feedback visuel immédiat** — sans graphe vivant et sans export (Excalidraw), il est difficile de vérifier rapidement que le réseau « tient debout » et de le partager.

**TriPhase** répond à cela en unifiant **ingestion** (JSON / image / chat), **modèle hiérarchique unique**, **validation déterministe**, **suggestions de correction** et **visualisation / export**, avec Gemma 4 comme assistant — jamais comme seule source de vérité.

---

## Vision

| Entrée | Traitement | Sortie |
|--------|------------|--------|
| JSON de topologie | Store + validateur | Graphe zones / PS / composants |
| Image de schéma | Gemma 4 vision → merge | Diagnostics + suggestions |
| Chat (« ajoute une charge… ») | Gemma → opérations structurées | Fichier `.excalidraw` |

**Principe :** Gemma propose ; le code décide. Les cycles et erreurs de configuration ne dépendent pas du LLM.

---

## Architecture métier

Hiérarchie visuelle alignée sur un schéma de type « Système TriPhase » :

```
Réseau
 └── Zone  (maille)
      ├── Power Station  (centrale)
      │    └── Générateur(s) / source / onduleur / batterie
      └── Charges / compteurs / interrupteurs
 └── Lignes  (liens orientés entre zones)
```

Les **lignes** relient les zones (`from_zone` → `to_zone`).  
Les **générateurs** vivent dans une **power station**, elle-même dans une **zone**.  
Les **charges** sont attachées directement à la zone.

### Acteurs (cadre applicatif)

- Groupe électrogène (production P, U, I, f)
- Compteur (puissance de maille)
- Tableau de bord (visualisation, alertes, actions)
- Consommateurs (charges)

---

## Stack technique

```
┌─────────────────────┐         ┌──────────────────────────┐
│  Frontend Vue 3     │  /api   │  Backend FastAPI         │
│  Vite + TS          │ ──────► │  Store mémoire           │
│  UIKit + Tailwind   │         │  Validator (cycles)      │
│  Vue Flow (graphe)  │         │  Suggestions             │
└─────────────────────┘         │  Export Excalidraw       │
                                │  Gemma 4 (google-genai)  │
                                └──────────────────────────┘
```

| Couche | Technologies |
|--------|----------------|
| Frontend | Vue 3, TypeScript, Vite, UIKit, Tailwind CSS v4, Vue Flow |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| IA | Gemma 4 (`gemma-4-26b-a4b-it`) via Gemini API |
| Export | JSON Excalidraw (`.excalidraw`) |

---

## Fonctionnalités

### Import
- Chargement d’un **JSON** de réseau
- Upload d’une **image** de schéma → extraction par Gemma 4 → fusion intelligente (réutilisation des IDs)

### Chat
- Modifications en français (« ajoute une power station dans zone2… »)
- Gemma renvoie des **opérations structurées** (`add_zone`, `add_power_station`, `add_generator`, `add_load`, `add_line`, `remove_*`, …)
- Affichage des actions réellement appliquées (pas seulement le texte du modèle)

### Visualisation
- Graphe interactif **Zone → Power Station → Générateur** + charges
- Pictogrammes distincts par type (générateur, source, onduleur, batterie, charge, compteur, interrupteur, bus)
- Animation à l’ajout de composants
- Lignes animées entre zones

### Énergie & bilan
- Production générateur `P_min` / `P_max` / `P_eff`, demande charge `P_demand`
- Limites de transport par ligne, export des surplus entre zones
- Bilan zone : `P_production`, `P_demand`, `P_surplus`, `P_in`, `P_out`
- Affichage sur les nœuds zone et labels de lignes (flux / limite)

### Diagnostics
- Détection de **cycles**, références cassées, IDs dupliqués, zones / PS vides
- Contrôles énergétiques : `P_eff` hors plage, surcharge ligne, déficit / surplus piégé
- **Suggestions** de correction avec bouton « Appliquer »

### Export
- Téléchargement d’une scène **Excalidraw** (zones, PS, générateurs, charges, flèches)

### UX
- Barres d’avancement **locales** (import, chat, validation…)
- Notifications persistantes (fermeture manuelle)

---

## Modèle de données (extrait)

```json
{
  "meta": { "name": "Cas test zones", "version": 1 },
  "zones": [
    {
      "id": "zone1",
      "label": "Zone 1",
      "power_stations": [
        {
          "id": "ps_zone1",
          "label": "Power Station 1",
          "generators": [
            {
              "id": "gen1",
              "type": "generator",
              "label": "Générateur 1",
              "production": { "P_min": 500, "P_max": 5000, "P_eff": 3200 }
            }
          ]
        }
      ],
      "loads": [
        {
          "id": "load1",
          "type": "load",
          "label": "Charge 1",
          "demand": { "P_demand": 1800 }
        }
      ],
      "balance": {
        "P_production": 3200,
        "P_demand": 1800,
        "P_surplus": 1400,
        "P_in": 0,
        "P_out": 1400,
        "P_exportable": 1400
      }
    }
  ],
  "lines": [
    {
      "id": "line1",
      "from_zone": "zone1",
      "to_zone": "zone2",
      "kind": "feeds",
      "transport": { "P_max": 1000, "P_flow": 700 }
    }
  ]
}
```

### Énergie (W)

| Entité | Champs | Rôle |
|--------|--------|------|
| Générateur | `production.P_min` / `P_max` / `P_eff` | Plage et production effective |
| Charge | `demand.P_demand` | Demande |
| Ligne | `transport.P_max` / `P_flow` | Limite de transport et flux estimé |
| Zone | `balance.P_production`, `P_demand`, `P_surplus`, `P_in`, `P_out`, `P_exportable` | Bilan recalculé serveur |

Ops chat associées : `update_production`, `update_demand`, `update_line_transport`, `recompute_balance`.

Types de composants autorisés :  
`source` · `generator` · `inverter` · `battery` · `load` · `meter` · `switch` · `bus`

---

## API REST

| Méthode | Route | Description |
|---------|--------|-------------|
| `GET` | `/api/health` | Santé du service |
| `GET` / `PUT` | `/api/network` | Lire / remplacer le réseau |
| `POST` | `/api/network/from-image` | Image → Gemma → merge |
| `POST` | `/api/chat` | Chat NL → mutations |
| `GET` | `/api/validate` | Rapport d’erreurs / warnings |
| `GET` | `/api/suggestions` | Suggestions de correction |
| `POST` | `/api/ops` | Appliquer des mutations |
| `GET` | `/api/export/excalidraw` | Export `.excalidraw` |

Documentation interactive : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Démarrage rapide

### Prérequis

- Python **3.11+**
- Node.js **20+**
- Clé API Google (`GOOGLE_API_KEY`) — [Google AI Studio](https://aistudio.google.com/)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # renseigner GOOGLE_API_KEY
uvicorn app.main:app --reload --port 8000
```

Au premier démarrage (store vide), le fixture `fixtures/cas_test_zones.json` est chargé (5 zones, une PS + générateur + charge sur `zone1`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Interface : [http://localhost:5173](http://localhost:5173)  
Les appels `/api` sont proxifiés vers `http://127.0.0.1:8000`.

---

## Structure du dépôt

```
reseau-electrique/
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI + CORS + fixture
│   │   ├── models.py            # Zone, PowerStation, Component, Line…
│   │   ├── store.py             # État + mutations
│   │   ├── validator.py         # Cycles, refs, doublons
│   │   ├── suggestions.py       # Corrections proposées
│   │   ├── gemma.py             # Chat + vision Gemma 4
│   │   ├── excalidraw_export.py
│   │   └── routers/
│   │       ├── network.py
│   │       └── chat.py
│   ├── fixtures/
│   │   └── cas_test_zones.json
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.vue
    │   ├── api/                 # client HTTP + types
    │   ├── components/          # graphe, chat, import, diagnostics…
    │   ├── composables/         # avancement des traitements
    │   └── utils/               # notifications sticky
    ├── package.json
    └── vite.config.ts
```

---

## Exemples de prompts chat

```
Ajoute dans zone2 une power station ps2 avec un générateur gen2 et une charge load2.
```

```
Supprime zone5.
```

```
Relie zone4 à zone5 par une ligne line6.
```

Les opérations réellement appliquées s’affichent sous la réponse Gemma ; le graphe se met à jour avec animation.

---

## Points clés de conception

1. **Source of truth** = JSON réseau côté backend (pas le texte du LLM).
2. **Réutilisation des IDs** zones / lignes / PS / composants à chaque merge ou chat.
3. **Validation déterministe** (DFS pour les cycles, enums Pydantic pour les types).
4. **Alias de types** (`power_station` → générateur dans une PS, `charge` → `load`, etc.).
5. **UI découplée** : loaders proches de chaque action, toasts non auto-dismiss.

---

## Licence / contexte

Projet de modélisation et de démonstration — assistance IA pour la conception de réseaux électriques (topologie, dépendances, export visuel).
