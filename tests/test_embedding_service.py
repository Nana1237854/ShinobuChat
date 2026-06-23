"""Tests for the enhanced EmbeddingService with provider selection.

Covers:
  - embed_query with provider=none → None
  - embed_query with provider=google, no API key → None (no throw)
  - embed_documents returns list of results
  - Legacy embed() still works with settings.memory_embedding_*
  - ConfigService integration
"""
import sys
import uuid

sys.path.insert(0, ".")

pass_count = 0
fail_count = 0


def check(name, cond):
    global pass_count, fail_count
    if cond:
        pass_count += 1
        print(f"  [PASS] {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name}")


# =============================================================================
# Test 1: embed_query with no config_service → returns None (no-op fallback)
# =============================================================================
print("=== Test 1: embed_query no config → None ===")

from app.services.embedding_service import EmbeddingService

svc = EmbeddingService(config_service=None)
uid = uuid.UUID("00000000-0000-0000-0000-000000000001")

result = svc.embed_query(uid, "我想听歌")
check("1a: embed_query no config returns None", result is None)


# =============================================================================
# Test 2: embed_query with provider=none → None
# =============================================================================
print("\n=== Test 2: embed_query provider=none → None ===")


class FakeConfigServiceNone:
    def get_effective_value(self, user_id, field_name):
        if field_name == "embedding_provider":
            return "none"
        return None


svc2 = EmbeddingService(config_service=FakeConfigServiceNone())
result2 = svc2.embed_query(uid, "我想听歌")
check("2a: provider=none returns None", result2 is None)


# =============================================================================
# Test 3: embed_query with provider=google, no API key → None (no throw)
# =============================================================================
print("\n=== Test 3: embed_query provider=google, no API key → None ===")


class FakeConfigServiceNoKey:
    def get_effective_value(self, user_id, field_name):
        if field_name == "embedding_provider":
            return "google"
        if field_name == "google_embedding_api_key":
            return ""  # no key
        return None


svc3 = EmbeddingService(config_service=FakeConfigServiceNoKey())
result3 = svc3.embed_query(uid, "我想听歌")
check("3a: provider=google no key returns None", result3 is None)


# =============================================================================
# Test 4: embed_documents
# =============================================================================
print("\n=== Test 4: embed_documents ===")


class FakeConfigLocal:
    def get_effective_value(self, user_id, field_name):
        if field_name == "embedding_provider":
            return "local"
        return None


svc4 = EmbeddingService(config_service=FakeConfigLocal())
results4 = svc4.embed_documents(uid, ["hello", "world"])
check("4a: embed_documents returns list", isinstance(results4, list))
check("4b: embed_documents length matches", len(results4) == 2)
check("4c: all results are lists", all(isinstance(r, list) for r in results4))


# =============================================================================
# Test 5: Legacy embed() still works with settings
# =============================================================================
print("\n=== Test 5: Legacy embed() respects settings ===")

from app.core import config as app_config

old_dim = app_config.settings.memory_embedding_dimensions
try:
    app_config.settings.memory_embedding_dimensions = 2
    svc5 = EmbeddingService(config_service=None)
    result5 = svc5.embed("hello")
    check("5a: legacy embed returns vector", isinstance(result5, list) and len(result5) > 0)
finally:
    app_config.settings.memory_embedding_dimensions = old_dim


# =============================================================================
# Test 6: embed_text with empty string → None
# =============================================================================
print("\n=== Test 6: Empty string → None ===")

result6 = svc.embed_text(uid, "")
check("6a: empty string returns None", result6 is None)

result6b = svc.embed_query(uid, "   ")
check("6b: whitespace only returns None", result6b is None)


# =============================================================================
# Test 7: GoogleEmbeddingProvider unit test (no actual API call)
# =============================================================================
print("\n=== Test 7: GoogleEmbeddingProvider basic ===")

from app.services.embedding_providers.google_embedding_provider import GoogleEmbeddingProvider

provider = GoogleEmbeddingProvider(
    api_key="test-key",
    model="gemini-embedding-001",
)
check("7a: provider has model", provider.model == "gemini-embedding-001")
check("7b: embed empty text returns None", provider.embed("") is None)


# =============================================================================
# Summary
# =============================================================================
if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"Results: {pass_count} passed, {fail_count} failed, {pass_count + fail_count} total")
    if fail_count > 0:
        print("SOME TESTS FAILED!")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED!")
