"""Export OpenAPI 3.1 JSON schema from the DevMind FastAPI application."""

import json
from pathlib import Path
import sys

# Ensure server package is on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "server"))

from app.main import create_app

def main() -> None:
    app = create_app()
    openapi_schema = app.openapi()

    output_path = REPO_ROOT / "common" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"Exported OpenAPI schema to {output_path} ({len(openapi_schema.get('paths', {}))} paths)")

if __name__ == "__main__":
    main()
