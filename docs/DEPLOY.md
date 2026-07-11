# Deploy to a VPS (Ubuntu / Debian)

The app runs as three Docker containers (postgres, backend, frontend). This guide
assumes a fresh Ubuntu/Debian VPS with SSH access.

## 0. Before you start (on your local machine)
Capture a Facebook session so Marketplace scraping works (optional — without it,
OLX + Otomoto still work, FB returns "session-not-configured"):

```bash
pip install playwright && playwright install chromium
FB_STORAGE_STATE_PATH=backend/secrets/fb_storage_state.json python scripts/fb_login.py
```

Log into the FB account in the window that opens, then set its **Marketplace
location to a Polish city** (e.g. Warszawa) in the same browser — the account's
Marketplace location is server-side and must be PL (otherwise FB returns
French/Paris results). Press Enter in the terminal to save the session.
Keep the resulting `backend/secrets/fb_storage_state.json` — you'll upload it.

## 1. Install Docker on the VPS
```bash
ssh user@<VPS_IP>
sudo apt-get update && sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER   # then log out/in (or `newgrp docker`)
docker --version && docker compose version   # verify
```
(For Debian, replace `ubuntu` with `debian` and `$UBUNTU_CODENAME` with `$VERSION_CODENAME`.)

## 2. Get the code
```bash
git clone https://github.com/danil-pro/CarSkyscanner.git
cd CarSkyscanner
```

## 3. Configure the environment
```bash
cp .env.example .env
```
Edit `.env` and set the **public** API address browsers will use:
```
NEXT_PUBLIC_API_URL=http://<VPS_IP>:8000
```
(This is baked into the frontend at build time. If you later add a domain/HTTPS,
set it to `https://<domain>/api` and rebuild.)

## 4. Add the Facebook session (optional)
Upload the file you captured locally:
```bash
# from your local machine
scp backend/secrets/fb_storage_state.json user@<VPS_IP>:~/CarSkyscanner/backend/secrets/
```

## 5. Build & run
```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d --build
```
First build takes a few minutes (Playwright/Chromium install in the backend image).
Check it's up:
```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f backend   # Ctrl-C to exit
```

## 6. Open firewall ports
The frontend is on **3000**, the API on **8000**:
```bash
sudo ufw allow 22 && sudo ufw allow 3000 && sudo ufw allow 8000 && sudo ufw enable
```

## 7. Open the app
- App:      `http://<VPS_IP>:3000`
- API health: `http://<VPS_IP>:8000/health`

## Optional: domain + HTTPS (reverse proxy)
Put nginx/Caddy in front, proxy `/` → `frontend:3000` and `/api/` → `backend:8000`,
then set `NEXT_PUBLIC_API_URL=https://<domain>/api` in `.env` and
`docker compose ... up -d --build` to rebuild the frontend with the new URL.

## Maintenance
- **Update:** `git pull && docker compose -f docker/docker-compose.yml --env-file .env up -d --build`
- **Logs:** `docker compose -f docker/docker-compose.yml logs -f`
- **FB returns 0/French results again:** the account's Marketplace location reverted to Paris — set it back to a Polish city (in the FB account) and re-capture the session (step 0), then re-upload (step 4). No code change needed.

## Notes
- The Postgres data lives in the `pgdata` volume — it survives container restarts.
- `AUTO_SEED=true` seeds demo data only when the DB is empty.
- Containers restart automatically (`restart: unless-stopped`).
