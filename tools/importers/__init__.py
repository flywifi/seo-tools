"""tools/importers -- optional live-API importer tier for the content-import lane (P45).

Each module pulls a creator's OWN videos + stats from one platform's API using their own OAuth
credentials, and normalizes into the record shape tools/video_library.py:normalize_record consumes.
This tier is OFF by default: it runs only when the content_import_live master flag AND the per-platform
read flag are enabled, with credentials in pipeline/user-context/api-credentials.local.json. Every
fetch takes an injectable getter so selftests run with no network. Revenue is never fetched via API
(YouTube Studio CSV only). See shared/content-import-engine.md.
"""
