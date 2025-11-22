#!/bin/bash

cleanup() {
  echo -e "\nShutting down servers..."
  kill $HTTP_PID
  kill $WS_PID
  echo "Done."
  exit 0
}

trap cleanup SIGINT

echo "Starting HTTP server on http://localhost:8000"
python3 -m http.server 8000 &
HTTP_PID=$!

echo "Starting WebSocket server on ws://localhost:8001"
python3 server.py &
WS_PID=$!

wait $WS_PID
wait $HTTP_PID
