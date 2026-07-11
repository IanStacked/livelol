# Project Overview (Mermaid)

> **Paste-ready sources:** keep fence-free copies of each diagram in `agent/diagrams/` so
> they load directly into https://mermaid.live without trimming the ```` ```mermaid ````
> fence. Keep the two copies in sync when editing.

## 1. Live update loop (end-to-end)

```mermaid
flowchart TD
    A[!track region riot_id] --> B[cogs/track.py]
    B --> C[utils/riot_api: resolve PUUID + ranked info]
    C --> D[(Firestore: tracked_users)]
    L[background_update_task] --> E[fetch current ranked info]
    E --> F{tier/rank/LP changed?}
    F -- no --> L
    F -- yes --> G[update Firestore + get_recent_match_info]
    G --> H[MatchDetailsView embed]
    H --> I[post to guild updates channel]
```

## 2. Module dependencies

```mermaid
flowchart LR
    main[main.py] --> bot[bot.py]
    bot --> db[database.py]
    bot --> cogs[cogs/*]
    cogs --> dbsvc[utils/db_service]
    cogs --> riot[utils/riot_api]
    cogs --> ui[utils/ui_components]
    dbsvc --> db
    riot --> exc[utils/exceptions]
    ui --> const[utils/constants]
    dbsvc --> const
```
