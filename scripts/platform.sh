#!/bin/bash

set -e

case "$1" in
  start)
    docker compose up -d
    ;;

  stop)
    docker compose down
    ;;

  restart)
    docker compose down
    docker compose up -d
    ;;

  status)
    docker compose ps
    ;;

  health)
    ./scripts/health_check.sh
    ;;

  logs)
    if [ -z "$2" ]; then
      echo "Usage: ./scripts/platform.sh logs <service-name>"
      echo "Available services: nginx, frontend, api, postgres, redis"
      exit 1
    fi
    ./scripts/view_logs.sh "$2"
    ;;

  *)
    echo "Usage: ./scripts/platform.sh {start|stop|restart|status|health|logs}"
    echo "Example: ./scripts/platform.sh health"
    exit 1
    ;;
esac
