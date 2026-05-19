# MarketClaw

This project is my entry for the DataVita OpenClaw Challenge. It is an AI-powered car market intelligence system that detects undervalued listings on Facebook Marketplace by comparing them with AutoTrader, incorporating image analysis to evaluate vehicle condition, and using Clawbot to orchestrate data ingestion, matching, and analysis workflows.



## How To Use

venv\Scripts\activate # Windows
source .venv/bin/activate # Mac/Linux

uvicorn api.main:app --reload # Windows/Mac/Linux

While the server is running, the Facebook scraper also runs automatically every day at **11:00** and **19:00** (local time by default). Optional: set `SCRAPE_SCHEDULE_TZ=Europe/London` in `.env` for a specific timezone.


## API Endpoints

    Health Check:
    http://127.0.0.1:8000/

    Database Check:
    http://127.0.0.1:8000/db_test



    Scrape Facebook Data (manual; also runs automatically at 11:00 and 19:00):
    http://127.0.0.1:8000/scrape/run

    Facebook vehicles pending AI enrichment:
    http://127.0.0.1:8000/fb_vehicles/pending_enrichment

    Enrich car (plate → vehicle → damage → scam; only when ai_last_updated is null):
    http://127.0.0.1:8000/agents/enrich_car/{vehicle_id}



    Facebook vehicles pending AutoTrader (completed is false):
    http://127.0.0.1:8000/fb_vehicles/pending_completion

    AutoTrader (WebSocket — interactive filter conversation, saves top 3 matches; sets completed=true):
    ws://127.0.0.1:8000/autotrader/ws/{fb_vehicle_id}
    

    
    AutoTrader saved matches (GET):
    http://127.0.0.1:8000/autotrader/matches/{fb_vehicle_id}

    Get one Facebook vehicle (includes AutoTrader matches):
    http://127.0.0.1:8000/fb_vehicles/{vehicle_id}