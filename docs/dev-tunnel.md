# Dev tunnel: `dev.olmenta.com`

`https://dev.olmenta.com` reaches the webapp running on your machine (`localhost:3000`) through a Cloudflare Tunnel. Use it to try real Auth0 login on a real host, or to open your local build from your phone.

- **Only the webapp goes through the tunnel.** The API stays on `localhost:8000`, reachable only by the webapp (the BFF).
- **Real login only.** Without Auth0, the webapp answers only `localhost` and `127.0.0.1`; any other host gets a 403. Through the tunnel you always sign in with the dev Auth0 application.

## 1. Publish the hostname on the tunnel

The tunnel is managed from the Cloudflare dashboard, and its connector runs as a service on the dev Mac. On this Mac, the tunnel is "test tunnel dev", and `cloudflared tunnel list` shows it.

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → **test tunnel dev** → Public hostnames → **Add a public hostname**:
   - **Subdomain:** `dev`. **Domain:** `olmenta.com`.
   - **Service:** `HTTP`, `localhost:3000`.
   - Additional settings → HTTP Settings: leave **HTTP Host Header** empty, so the webapp sees `dev.olmenta.com` as the host.
2. Save. Cloudflare creates the proxied `dev` CNAME in the `olmenta.com` zone by itself.

**On a new machine:**

1. Zero Trust → Networks → Tunnels → **Create a tunnel** (Cloudflared).
2. Install the connector with the command it shows (`sudo cloudflared service install <token>`).
3. Add the public hostname above.

**Recommended:** put Cloudflare Access in front, so only you reach the page even before Auth0 asks for a password.

1. Zero Trust → Access → Applications → **Add an application** → Self-hosted, domain `dev.olmenta.com`.
2. Add a policy: Allow, emails = yours. It's free for up to 50 users.

## 2. Configure the local environment for real login

The Auth0 objects come from [auth0-setup.md](auth0-setup.md): the dev application already lists `https://dev.olmenta.com` in its callback, logout and web-origin URLs.

**`webapp/.env`:**

```
APP_ENV=dev
AUTH0_DOMAIN=olmenta.eu.auth0.com
AUTH0_CLIENT_ID=<Olmenta (dev) client id>
AUTH0_CLIENT_SECRET=<Olmenta (dev) client secret>
AUTH0_SECRET=<openssl rand -hex 32>
APP_BASE_URL=http://localhost:3000,https://dev.olmenta.com
AUTH0_AUDIENCE=https://api-dev.olmenta.com
```

`APP_BASE_URL` lists both origins. For each request, the Auth0 SDK picks the one the browser used, so `localhost:3000` and `dev.olmenta.com` both work at the same time.

**`backend/.env`:**

```
APP_ENV=dev
AUTH_MODE=auth0
AUTH0_DOMAIN=olmenta.eu.auth0.com
AUTH0_AUDIENCE=https://api-dev.olmenta.com
```

Restart both dev servers after changing the files (`volta run npm run dev` in `webapp/`; the API as usual). Then open `https://dev.olmenta.com`.

## 3. What changes while real login is on

- **You start as a new user** in the dev database: the first sign-in creates your user, and you land in the onboarding. The seeded development user (`dev@localhost`) and its data stay untouched.
- **Going back to the development user:** set `APP_ENV=local` and `AUTH_MODE=dev_user`, comment out the `AUTH0_*` variables, then restart.
- **The dev MCP server needs the development user.** It calls the API without a token, so with `AUTH_MODE=auth0` its tools get 401. Switch back to use it.
- **The e2e suite isn't affected.** It runs its own API and webapp with auth disabled.

## 4. Turning it off

When the dev server isn't running, `dev.olmenta.com` shows a Cloudflare 502 page, and nothing on your machine is reachable. To unpublish the hostname, delete it from the tunnel's Public hostnames. To stop the connector itself: `sudo launchctl unload /Library/LaunchDaemons/com.cloudflare.cloudflared.plist`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| 403 "Sign-in isn't configured on this server." | `AUTH0_DOMAIN` is missing from `webapp/.env`. Without it, the webapp only answers `localhost`. |
| Auth0 "Callback URL mismatch" | The dev application's Allowed Callback URLs lack `https://dev.olmenta.com/auth/callback`. |
| An error that the request origin isn't allowed | `APP_BASE_URL` doesn't list `https://dev.olmenta.com`, or the tunnel's HTTP Host Header is overridden. |
| The API refuses to start: "AUTH_MODE=dev_user is not allowed with APP_ENV=dev" | Set `AUTH_MODE=auth0` together with `APP_ENV=dev`. |
| The page loads but never updates while editing code | `allowedDevOrigins` in `webapp/next.config.ts` must include `dev.olmenta.com`. |
