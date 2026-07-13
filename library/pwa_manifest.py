from django.templatetags.static import static


def build_manifest(request) -> dict:
    origin = request.build_absolute_uri("/").rstrip("/")

    def asset(path: str) -> str:
        return request.build_absolute_uri(static(path))

    return {
        "id": f"{origin}/",
        "name": "Pick-a-Print",
        "short_name": "Pick-a-Print",
        "description": "Your 3D printing library — save models, run scans, organize collections.",
        "start_url": f"{origin}/?source=pwa",
        "scope": f"{origin}/",
        "display": "standalone",
        "orientation": "any",
        "theme_color": "#0b0d10",
        "background_color": "#0b0d10",
        "prefer_related_applications": False,
        "categories": ["productivity", "utilities"],
        "icons": [
            {
                "src": asset("library/icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": asset("library/icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": asset("library/icons/icon-maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "Save model",
                "short_name": "Save",
                "url": f"{origin}/models/save/",
                "icons": [{"src": asset("library/icons/icon-192.png"), "sizes": "192x192"}],
            },
            {
                "name": "3D scan",
                "short_name": "Scan",
                "url": f"{origin}/scan/",
                "icons": [{"src": asset("library/icons/icon-192.png"), "sizes": "192x192"}],
            },
        ],
        "share_target": {
            "action": f"{origin}/share/",
            "method": "POST",
            "enctype": "multipart/form-data",
            "params": {
                "title": "title",
                "text": "text",
                "url": "url",
                "files": [
                    {
                        "name": "files",
                        "accept": [
                            "image/*",
                            "text/plain",
                            "text/*",
                            "application/zip",
                            "application/octet-stream",
                            "model/stl",
                            "model/3mf",
                            ".stl",
                            ".3mf",
                        ],
                    }
                ],
            },
        },
        "launch_handler": {
            "client_mode": "navigate-existing",
        },
    }
