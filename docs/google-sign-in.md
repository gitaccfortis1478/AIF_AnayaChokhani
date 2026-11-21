# Google sign-in

YourSpace uses the Google Identity Services button for both account creation and sign-in. The backend verifies the ID token's signature, audience, issuer, expiry, verified email and browser nonce before creating its own HttpOnly session cookie. No Google password or refresh token is stored.

## Google Cloud setup

1. In Google Cloud Console, configure Google Auth Platform branding, audience and consent. While the app is in testing, add your testers.
2. Create an OAuth client with application type **Web application**.
3. Add the origin configured in `NEXT_PUBLIC_MYSPACE_PUBLIC_FRONTEND_URL` and your deployed frontend origin (for example `https://yourspace.example.com`) to **Authorized JavaScript origins**. Include the port locally; omit URL paths. This popup ID-token flow does not need a redirect URI or client secret.
4. Set backend `GOOGLE_CLIENT_ID` to that client's ID.

## Environment

Backend (load these in the backend process environment, or `backend/.env` when starting there):

```dotenv
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
NEXT_PUBLIC_MYSPACE_PUBLIC_FRONTEND_URL=https://yourspace.example.com
FORMAOS_COOKIE_SECURE=0
FORMAOS_COOKIE_SAMESITE=lax
```

`NEXT_PUBLIC_MYSPACE_PUBLIC_FRONTEND_URL` accepts a comma-separated list of exact allowed frontend origins. In production, use the deployed HTTPS origin and `FORMAOS_COOKIE_SECURE=1`.

Frontend (`frontend/.env.local` for development, or hosting build settings):

```dotenv
NEXT_PUBLIC_MYSPACE_PUBLIC_BACKEND_URL=https://api.yourspace.example.com
```

Use your public HTTPS backend URL for production and rebuild the frontend after changing it. The frontend obtains the Google client ID from the backend; no additional frontend Google variable is required.

Prefer serving the frontend and API on the same site (such as `app.example.com` and `api.example.com`). For different sites, the backend needs `FORMAOS_COOKIE_SAMESITE=none` and `FORMAOS_COOKIE_SECURE=1`; browser third-party cookie restrictions can still block sessions. Use a same-site API domain if that happens. Never configure `SameSite=none` without HTTPS and Secure cookies.

Install dependencies with `cd backend` then `uv sync`, and start the services normally. Keep the backend account/session store on persistent storage. This change retains the existing file-based store; multiple independent backend replicas need a shared transactional store before scaling.

## Existing accounts

Password sign-up and login endpoints now return HTTP 410. Existing passwords cannot sign users in. Existing sessions remain valid until logout or expiry. Google accounts are identified by Google's stable `sub`, never by email alone. Legacy accounts are not automatically linked, because their email addresses were unverified. Their projects stay associated with the original account and require an explicit ownership-verified migration to transfer.

## Verification

Automated tests mock Google's verification boundary and exercise nonce rejection, invalid/unverified tokens, origin rejection, account separation, returning users, and cookie sessions. To finish a live smoke test, configure a real client ID, open `/login`, continue with Google, verify `/workspace` opens, reload, then sign out. Repeat on the deployed HTTPS origins.

References: [Google token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token), [Google button API](https://developers.google.com/identity/gsi/web/reference/js-reference).
