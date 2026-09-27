#!/bin/bash
set -e
BASE=http://127.0.0.1:8000

echo "--- registro ---"
REG=$(curl -s -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"secret123"}')
echo "$REG"
TOKEN=$(echo "$REG" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "--- subir prenda ---"
printf '\xff\xd8\xff\xe0fake' > /tmp/prenda.jpg
curl -s -X POST $BASE/garments -H "Authorization: Bearer $TOKEN" \
  -F "category=top" -F "color=azul" -F "warmth=light" -F "name=camiseta" \
  -F "image=@/tmp/prenda.jpg;type=image/jpeg"
echo

echo "--- listar prendas ---"
curl -s $BASE/garments -H "Authorization: Bearer $TOKEN"
echo

echo "--- generar outfit (requiere OPENWEATHER_API_KEY en .env) ---"
curl -s -X POST $BASE/outfits/generate -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"occasion":"casual","lat":19.4,"lon":-99.1}'
echo
