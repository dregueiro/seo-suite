from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]

BASE_DIR = Path(__file__).resolve().parents[1]
CLIENT_SECRETS = BASE_DIR / "secrets" / "oauth-client.json"

if not CLIENT_SECRETS.exists():
    raise SystemExit(f"No existe: {CLIENT_SECRETS}")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), scopes=SCOPES)

creds = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent",
)

print("REFRESH_TOKEN =", creds.refresh_token)
