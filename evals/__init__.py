import os

# Quiet fastmcp client logs; must run before fastmcp is imported.
os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")
