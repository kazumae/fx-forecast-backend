#!/bin/bash

echo "=== API Health Check ==="
curl -s http://localhost:8900/health | jq

echo -e "\n=== Database Connection Test ==="
PGPASSWORD=fx_password psql -h localhost -p 6543 -U fx_user -d fx_forecast -c "SELECT 'Database connected successfully' as status"

echo -e "\n=== Tables in Database ==="
docker-compose exec -T db psql -U fx_user -d fx_forecast -c "\dt"

echo -e "\n=== Create Test User ==="
curl -s -X POST http://localhost:8900/api/v1/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpassword"
  }' | jq

echo -e "\n=== Get Users List ==="
curl -s http://localhost:8900/api/v1/users/ | jq

echo -e "\n=== Create Forex Forecast ==="
curl -s -X POST http://localhost:8900/api/v1/forex/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "currency_pair": "USD/JPY",
    "forecast_horizon": 1
  }' | jq