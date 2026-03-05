#!/bin/bash
# Speaking Bot — serverga deploy qilish skripti
# Serverda bir marta ishga tushiring: bash deploy.sh

set -e

echo "=== 1. Eski containerlarni to'xtatish ==="
docker-compose down 2>/dev/null || true

echo "=== 2. SSL init config o'rnatish (birinchi marta) ==="
cp nginx-init.conf nginx.conf.tmp
cp nginx.conf nginx.conf.backup

echo "=== 3. HTTP only rejimda ishga tushirish ==="
cp nginx-init.conf /tmp/nginx-current.conf
docker-compose up -d db redis

echo "=== 4. Django build ==="
docker-compose build web

echo "=== 5. nginx HTTP only bilan ishga tushirish ==="
# Vaqtincha nginx-init.conf ni ishlatish
docker run --rm -d \
  --name nginx-init \
  -p 80:80 \
  -v $(pwd)/nginx-init.conf:/etc/nginx/conf.d/default.conf:ro \
  -v $(pwd)/staticfiles:/app/staticfiles:ro \
  nginx:alpine

echo "=== 6. SSL sertifikat olish ==="
docker-compose run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  --email admin@ittatuz.uz \
  --agree-tos \
  --no-eff-email \
  -d ittatuz.uz \
  -d www.ittatuz.uz

echo "=== 7. Init nginx-ni to'xtatish ==="
docker stop nginx-init 2>/dev/null || true

echo "=== 8. To'liq stack ishga tushirish (HTTPS bilan) ==="
docker-compose up -d --build

echo "=== 9. Migratsiyalar ==="
sleep 10  # DB tayyor bo'lishini kutish
docker-compose exec web python manage.py migrate --noinput
docker-compose exec web python manage.py collectstatic --noinput

echo ""
echo "=== DEPLOY MUVAFFAQIYATLI YAKUNLANDI ==="
echo "Site: https://ittatuz.uz"
echo "Admin: https://ittatuz.uz/admin"
echo "WebApp: https://ittatuz.uz/webapp/"
