"""Tests for F14 (Browser Reader), F15 (Download Safety), F16 (Permission/Logs), F14.5 (MCP)."""

import json
import unittest

from app.mcp.config import MCP_BLOCKED_TOOLS, MCP_SAFE_TOOLS
from app.mcp.tool_adapter import create_default_adapter
from app.services.download_candidate_extractor import DownloadCandidateExtractor
from app.services.download_risk_classifier import DownloadRiskClassifier
from app.services.web_reader_service import WebReaderService
from app.services.web_search_service import WebSearchService
from app.schemas.local_agent_settings import LocalAgentSettingsOut, LocalAgentSettingsPatch


# =============================================================================
# F14: WebReaderService
# =============================================================================

class WebReaderServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = WebReaderService()

    def test_rejects_non_http_scheme(self):
        result = self.svc.read("file:///etc/passwd")
        self.assertEqual(result["status"], "error")
        self.assertIn("http", result["message"].lower())

    def test_rejects_javascript_scheme(self):
        result = self.svc.read("javascript:alert(1)")
        self.assertEqual(result["status"], "error")

    def test_rejects_localhost(self):
        result = self.svc.read("http://localhost:8000/admin")
        self.assertEqual(result["status"], "error")
        self.assertIn("security", result["message"].lower())

    def test_rejects_loopback_ip(self):
        result = self.svc.read("http://127.0.0.1:12345/secret")
        self.assertEqual(result["status"], "error")

    def test_rejects_private_ip(self):
        result = self.svc.read("http://192.168.1.1/admin")
        self.assertEqual(result["status"], "error")

    def test_reads_public_page(self):
        result = self.svc.read("https://example.com")
        self.assertEqual(result["status"], "ok")
        self.assertIn("Example Domain", result["title"])
        self.assertTrue(len(result["content"]) > 0)
        self.assertIn("url", result)
        self.assertIsInstance(result["links"], list)

    def test_returns_error_on_nonexistent_domain(self):
        result = self.svc.read("https://this-domain-definitely-does-not-exist-12345.com")
        self.assertEqual(result["status"], "error")
        self.assertTrue(len(result["message"]) > 0)


# =============================================================================
# F14: WebSearchService
# =============================================================================

class WebSearchServiceTests(unittest.TestCase):
    def test_returns_error_when_not_configured(self):
        svc = WebSearchService(api_key="", cx="")
        result = svc.search("test query")
        self.assertEqual(result["status"], "error")
        self.assertIn("not configured", result["message"].lower())

    def test_returns_results_when_configured(self):
        svc = WebSearchService(api_key="test-key", cx="test-cx")
        # Will fail at network level but shouldn't crash
        result = svc.search("test query")
        self.assertIn(result["status"], ("ok", "error"))
        self.assertIsInstance(result["results"], list)


# =============================================================================
# F15: Download Candidate Extraction
# =============================================================================

class DownloadCandidateExtractorTests(unittest.TestCase):
    def setUp(self):
        self.extractor = DownloadCandidateExtractor()

    def test_extracts_exe_links(self):
        links = [
            {"text": "Download Windows", "href": "https://example.com/app.exe"},
        ]
        candidates = self.extractor.extract(links)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["extension"], ".exe")
        self.assertEqual(candidates[0]["domain"], "example.com")

    def test_extracts_msi_links(self):
        links = [
            {"text": "Installer", "href": "https://example.com/setup.msi"},
        ]
        candidates = self.extractor.extract(links)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["extension"], ".msi")

    def test_extracts_download_keyword_links(self):
        links = [
            {"text": "高速下载", "href": "https://example.com/download"},
        ]
        candidates = self.extractor.extract(links)
        self.assertEqual(len(candidates), 1)

    def test_detects_double_extension(self):
        links = [
            {"text": "Photo", "href": "https://example.com/image.jpg.exe"},
        ]
        candidates = self.extractor.extract(links)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["extension"], ".exe")

    def test_ignores_non_download_links(self):
        links = [
            {"text": "About", "href": "https://example.com/about"},
            {"text": "Contact", "href": "https://example.com/contact"},
        ]
        candidates = self.extractor.extract(links)
        self.assertEqual(len(candidates), 0)


# =============================================================================
# F15: Download Risk Classification
# =============================================================================

class DownloadRiskClassifierTests(unittest.TestCase):
    def setUp(self):
        self.classifier = DownloadRiskClassifier(db=None)

    def test_blocks_javascript_url(self):
        result = self.classifier.classify([{
            "text": "Click here",
            "href": "javascript:alert(1)",
            "domain": "",
            "extension": "",
        }])
        self.assertEqual(result[0]["risk_level"], "blocked")

    def test_blocks_localhost_url(self):
        result = self.classifier.classify([{
            "text": "Download",
            "href": "http://127.0.0.1/malware.exe",
            "domain": "127.0.0.1",
            "extension": ".exe",
        }])
        self.assertEqual(result[0]["risk_level"], "blocked")

    def test_blocks_file_scheme(self):
        result = self.classifier.classify([{
            "text": "File",
            "href": "file:///C:/Windows/System32/hosts",
            "domain": "",
            "extension": "",
        }])
        self.assertEqual(result[0]["risk_level"], "blocked")

    def test_blocks_double_extension(self):
        result = self.classifier.classify([{
            "text": "Image",
            "href": "https://example.com/download.jpg.exe",
            "domain": "example.com",
            "extension": ".exe",
        }])
        self.assertEqual(result[0]["risk_level"], "blocked")

    def test_flags_untrusted_exe_as_high(self):
        result = self.classifier.classify([{
            "text": "Setup",
            "href": "https://random-site.com/app.exe",
            "domain": "random-site.com",
            "extension": ".exe",
        }])
        self.assertEqual(result[0]["risk_level"], "high")

    def test_flags_crack_keyword_as_high(self):
        result = self.classifier.classify([{
            "text": "Crack v2.0 download",
            "href": "https://example.com/crack.zip",
            "domain": "example.com",
            "extension": ".zip",
        }])
        self.assertEqual(result[0]["risk_level"], "high")

    def test_flags_keygen_as_high(self):
        result = self.classifier.classify([{
            "text": "Keygen for Adobe",
            "href": "https://example.com/keygen.zip",
            "domain": "example.com",
            "extension": ".zip",
        }])
        self.assertEqual(result[0]["risk_level"], "high")

    def test_flags_high_speed_downloader_as_high(self):
        result = self.classifier.classify([{
            "text": "高速下载器",
            "href": "https://example.com/downloader.exe",
            "domain": "example.com",
            "extension": ".exe",
        }])
        self.assertEqual(result[0]["risk_level"], "high")

    def test_unknown_for_unrecognized_extension(self):
        result = self.classifier.classify([{
            "text": "Document",
            "href": "https://example.com/file.xyz",
            "domain": "example.com",
            "extension": ".xyz",
        }])
        self.assertIn(result[0]["risk_level"], ("unknown", "low"))

    def test_low_risk_for_pdf(self):
        result = self.classifier.classify([{
            "text": "Manual",
            "href": "https://example.com/manual.pdf",
            "domain": "example.com",
            "extension": ".pdf",
        }])
        self.assertEqual(result[0]["risk_level"], "low")

    def test_requires_confirmation_for_high_risk(self):
        result = self.classifier.classify([{
            "text": "Setup",
            "href": "https://random-site.com/app.exe",
            "domain": "random-site.com",
            "extension": ".exe",
        }])
        self.assertTrue(result[0]["requires_confirmation"])
        self.assertEqual(result[0]["risk_level"], "high")

    def test_blocked_does_not_require_confirmation(self):
        """Blocked items are outright rejected, not confirmed."""
        result = self.classifier.classify([{
            "text": "X",
            "href": "javascript:void(0)",
            "domain": "",
            "extension": "",
        }])
        self.assertFalse(result[0]["requires_confirmation"])

    def test_classify_returns_reasons(self):
        result = self.classifier.classify([{
            "text": "Crack",
            "href": "https://example.com/crack.exe",
            "domain": "example.com",
            "extension": ".exe",
        }])
        self.assertTrue(len(result[0]["reasons"]) > 0)


# =============================================================================
# F16: Local Agent Settings Schema
# =============================================================================

class LocalAgentSettingsSchemaTests(unittest.TestCase):
    def test_defaults_are_correct(self):
        s = LocalAgentSettingsOut()
        self.assertTrue(s.local_launcher_enabled)
        self.assertTrue(s.browser_reader_enabled)
        self.assertFalse(s.browser_automation_enabled)
        self.assertFalse(s.mcp_enabled)
        self.assertTrue(s.require_confirm_for_executable)
        self.assertTrue(s.require_confirm_for_unknown_url)

    def test_patch_partial_update(self):
        patch = LocalAgentSettingsPatch(local_launcher_enabled=False)
        data = patch.model_dump(exclude_unset=True)
        self.assertIn("local_launcher_enabled", data)
        self.assertNotIn("mcp_enabled", data)

    def test_patch_no_fields(self):
        patch = LocalAgentSettingsPatch()
        data = patch.model_dump(exclude_unset=True)
        self.assertEqual(len(data), 0)


# =============================================================================
# F14.5: MCP Adapter
# =============================================================================

class McpAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = create_default_adapter()

    def test_lists_safe_tools(self):
        tools = self.adapter.list_tools()
        tool_names = {t["name"] for t in tools}
        for safe in MCP_SAFE_TOOLS:
            self.assertIn(safe, tool_names, f"Safe tool {safe} should be listed")

    def test_no_blocked_tools_listed(self):
        tools = self.adapter.list_tools()
        tool_names = {t["name"] for t in tools}
        for blocked in MCP_BLOCKED_TOOLS:
            self.assertNotIn(blocked, tool_names, f"Blocked tool {blocked} should not be listed")

    def test_shell_command_not_exposed(self):
        tools = self.adapter.list_tools()
        tool_names = {t["name"] for t in tools}
        self.assertNotIn("shell_command", tool_names)
        self.assertNotIn("run_installer", tool_names)
        self.assertNotIn("file_write", tool_names)
        self.assertNotIn("download_file", tool_names)
        self.assertNotIn("browser_click", tool_names)

    def test_open_url_callable(self):
        result = self.adapter.call_tool("open_url", {"url": "https://example.com"})
        data = json.loads(result)
        self.assertIn("status", data)

    def test_read_webpage_callable(self):
        result = self.adapter.call_tool("read_webpage", {"url": "https://example.com"})
        data = json.loads(result)
        self.assertIn("status", data)

    def test_search_web_callable(self):
        result = self.adapter.call_tool("search_web", {"query": "test"})
        data = json.loads(result)
        self.assertIn("status", data)

    def test_unknown_tool_returns_error(self):
        result = self.adapter.call_tool("nonexistent_tool", {})
        data = json.loads(result)
        self.assertIn("error", data)

    def test_mcp_config_defaults(self):
        self.assertIn("open_local_app", MCP_SAFE_TOOLS)
        self.assertIn("shell_command", MCP_BLOCKED_TOOLS)


# =============================================================================
# F15: Edge Cases
# =============================================================================

class EdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.classifier = DownloadRiskClassifier(db=None)

    def test_empty_candidate_list(self):
        result = self.classifier.classify([])
        self.assertEqual(len(result), 0)

    def test_empty_href(self):
        result = self.classifier.classify([{
            "text": "Empty",
            "href": "",
            "domain": "",
            "extension": "",
        }])
        self.assertIn(result[0]["risk_level"], ("blocked", "unknown"))

    def test_data_uri_blocked(self):
        result = self.classifier.classify([{
            "text": "Data",
            "href": "data:text/html,<script>alert(1)</script>",
            "domain": "",
            "extension": "",
        }])
        self.assertEqual(result[0]["risk_level"], "blocked")

    def test_medium_risk_for_archive_from_untrusted(self):
        result = self.classifier.classify([{
            "text": "Archive",
            "href": "https://unknown-site.com/file.zip",
            "domain": "unknown-site.com",
            "extension": ".zip",
        }])
        self.assertEqual(result[0]["risk_level"], "medium")


if __name__ == "__main__":
    unittest.main()
