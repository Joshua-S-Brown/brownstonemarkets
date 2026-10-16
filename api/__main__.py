"""Print the web contract for openapi-typescript."""
import json

from . import schema

print(json.dumps(schema(), sort_keys=True))
