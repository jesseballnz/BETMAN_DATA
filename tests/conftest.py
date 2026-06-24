from __future__ import annotations

import os

os.environ.setdefault("ADMIN_API_KEY", "test-admin-key")
os.environ.setdefault("PLATFORM_MASTER_KEY", "test-platform-master-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080")
