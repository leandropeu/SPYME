# Higienizacao da VPS SPYGYM

Objetivo: manter apenas o stack Docker ativo e evitar conflito com servicos legados.

## 1. Desativar backend legado

```bash
systemctl stop spygym-backend.service
systemctl disable spygym-backend.service
systemctl status spygym-backend.service
```

## 2. Confirmar portas

```bash
ss -ltnp | grep :80
ss -ltnp | grep :8000
```

Esperado:

- porta `80` ocupada por `docker-proxy`
- porta `8000` sem `uvicorn` legado externo

## 3. Usar apenas o deploy Docker

```bash
cd /root/Documents/CUNHADO/spygym/deploy/deploy
docker compose -f docker-compose.vps.yml up -d --build --force-recreate backend frontend nginx
docker compose -f docker-compose.vps.yml ps
```

## 4. Validar API e CORS

```bash
curl http://127.0.0.1/api/health
curl -i -X OPTIONS "http://127.0.0.1/api/auth/login" \
  -H "Origin: http://191.252.212.6" \
  -H "Access-Control-Request-Method: POST"
```

## 5. Configuracao importante

O arquivo `backend/.env` deve conter a mesma `SPYGYM_SECRET_SEED` que ja estiver em uso na VPS.
Nao troque esse valor sem planejar a migracao das credenciais criptografadas.
