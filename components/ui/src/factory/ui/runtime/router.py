from typing import Dict, Optional


class Router:
    """
    Maps paths to view IDs (filenames).
    """

    def __init__(self, routes: Optional[Dict[str, str]] = None):
        self.routes = routes or {}

    def resolve(self, path: str) -> Optional[str]:
        """
        Resolves a path to a view ID.
        If exact match found in routes config, returns that.
        Otherwise, treats the path as the view ID (stripping leading slash).
        """
        # 1. Check explicit routes
        if path in self.routes:
            return self.routes[path]

        # 2. Implicit mapping (e.g. /dashboard -> dashboard)
        clean_path = path.lstrip("/")
        if not clean_path:
            # Default to 'index' if root
            return self.routes.get("/", "index")

        return clean_path
