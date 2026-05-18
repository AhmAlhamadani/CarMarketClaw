# MarketClaw

This project is my entry for the DataVita OpenClaw Challenge. It is an AI-powered car market intelligence system that detects undervalued listings on Facebook Marketplace by comparing them with AutoTrader, incorporating image analysis to evaluate vehicle condition, and using Clawbot to orchestrate data ingestion, matching, and analysis workflows.



## How To Use

venv\Scripts\activate

uvicorn api.main:app --reload


## API Endpoints

    Health Check:
    http://127.0.0.1:8000/

    Database Check:
    http://127.0.0.1:8000/db_test

    Scrape Data:
    http://127.0.0.1:8000/scrape/run

    Run Agents:
    http://127.0.0.1:8000/agents/vehicle/{vehicle_id}
    http://127.0.0.1:8000/agents/scam/{vehicle_id}
    http://127.0.0.1:8000/agents/damage/{vehicle_id}
    http://127.0.0.1:8000/agents/plate/{vehicle_id}

    AutoTrader (WebSocket — interactive filter conversation, saves top 3 matches):
    ws://127.0.0.1:8000/autotrader/ws/{fb_vehicle_id}
    
    AutoTrader saved matches (GET):
    http://127.0.0.1:8000/autotrader/matches/{fb_vehicle_id}

