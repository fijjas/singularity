"""Shared database configuration. Reads from substrate secrets or environment."""
import os

def _load_env():
    """Load db.env from substrate secrets, then singularity .env as fallback."""
    env_paths = [
        os.path.expanduser('~/substrate/secrets/db.env'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        os.environ.setdefault(key.strip(), value.strip())

_load_env()

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5433')),
    'user': os.environ.get('DB_USER', 'kai'),
    'password': os.environ.get('DB_PASSWORD', os.environ.get('DB_PASS', '')),
    'dbname': os.environ.get('DB_NAME', 'kai_mind'),
}
