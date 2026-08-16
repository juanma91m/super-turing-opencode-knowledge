# Engram Cloud server

Deployment portable de la fase Engram. El cliente local no comparte archivos ni
volúmenes con estos contenedores: Postgres pertenece al servidor y cada cliente
conserva su propio `~/.engram/engram.db`.

## Inicialización

```bash
./server/init-env.sh \
  --projects super-turing-opencode-knowledge \
  --client-config "$HOME/.config/opencode/knowledge-sync.conf" \
  --client-server http://127.0.0.1:18080
docker compose --env-file server/.env -f server/compose.yaml config --quiet
docker compose --env-file server/.env -f server/compose.yaml up -d --build
curl -fsS http://127.0.0.1:18080/health
```

La imagen se construye desde el ref exacto declarado en `.env` y aplica el patch
versionado del addon. No usa `latest`. El GHCR `latest` auditado apuntaba a Engram
1.20.0/revisión `ba9e46c`, anterior al cliente gestionado por este addon.
El `.dockerignore` excluye secrets, backups, Git y tests del build context.

Para clientes remotos, bindear al IP de Tailscale y usar ese URL en el cliente.
No publicar Postgres ni exponer Engram directamente a Internet. TLS puede
terminarse en un reverse proxy o en la capa de red privada.

## Operación

```bash
docker compose --env-file server/.env -f server/compose.yaml ps
docker compose --env-file server/.env -f server/compose.yaml logs engram-cloud
docker compose --env-file server/.env -f server/compose.yaml stop
docker compose --env-file server/.env -f server/compose.yaml start
docker compose --env-file server/.env -f server/compose.yaml down
```

`down` conserva el volumen. No usar `down -v` salvo destrucción deliberada.

## Backup PostgreSQL

Crear un dump lógico mientras el servicio está saludable:

```bash
umask 077
docker compose --env-file server/.env -f server/compose.yaml exec -T postgres \
  sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > "$HOME/engram-cloud-$(date +%Y%m%dT%H%M%S).dump"
```

Verificar el archivo:

```bash
docker compose --env-file server/.env -f server/compose.yaml exec -T postgres \
  pg_restore --list < "$HOME/engram-cloud-YYYYMMDDTHHMMSS.dump" >/dev/null
```

## Recuperación PostgreSQL

La restauración reemplaza estado remoto. Primero detener `engram-cloud`, guardar
otro dump y revisar que ningún cliente esté sincronizando. Luego:

```bash
docker compose --env-file server/.env -f server/compose.yaml stop engram-cloud
docker compose --env-file server/.env -f server/compose.yaml exec -T postgres \
  sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose --env-file server/.env -f server/compose.yaml exec -T postgres \
  sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < "$HOME/engram-cloud-YYYYMMDDTHHMMSS.dump"
docker compose --env-file server/.env -f server/compose.yaml start engram-cloud
```

Después validar `/health` y ejecutar primero `knowledge-sync-status` desde un
cliente. El backup local existente y este dump son artefactos separados.
