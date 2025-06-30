#!/usr/bin/env python3
"""
Run TraderMade WebSocket Streaming Client with Database Storage
"""
import asyncio
from src.stream.stream_client_db import main

if __name__ == "__main__":
    asyncio.run(main())