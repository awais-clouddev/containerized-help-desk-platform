#!/bin/bash

set -e

echo "Checking Help Desk Platform health..."

echo "Checking Nginx..."
curl -fs http://localhost:8090 > /dev/null
echo "Nginx is healthy"

echo "Checking API..."
curl -fs http://localhost:8090/api/health > /dev/null
echo "API is healthy"

echo "Checking Docker containers..."
docker compose ps

echo "Platform health check completed successfully."
