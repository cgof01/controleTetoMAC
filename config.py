import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nqqcgnjyaxgcxhqviprr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable__6YN43KozIVDxTLEDFMQyQ_5q6AnWD5")

_use = os.environ.get("USE_SUPABASE", "True")
USE_SUPABASE = _use.lower() not in ("false", "0", "no")
