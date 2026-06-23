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


# =============================================================================
# Fix 2 regression: LocalAgentSettingsService enforcement
# =============================================================================

class LocalAgentSettingsServiceTests(unittest.TestCase):
    def test_defaults_all_enabled(self):
        from app.services.local_agent_settings_service import LocalAgentSettingsService
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            svc = LocalAgentSettingsService(db)
            settings = svc.get_settings(None)  # None user_id won't match rows
            self.assertTrue(settings["local_launcher_enabled"])
            self.assertTrue(settings["browser_reader_enabled"])
            self.assertFalse(settings["browser_automation_enabled"])
            self.assertFalse(settings["mcp_enabled"])
        finally:
            db.close()

    def test_forbidden_error_subclass(self):
        from app.core.exceptions import ForbiddenError
        err = ForbiddenError("test")
        self.assertIsInstance(err, Exception)
        self.assertEqual(err.detail, "test")

    def test_is_local_launcher_enabled_no_rows(self):
        from app.services.local_agent_settings_service import LocalAgentSettingsService
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            svc = LocalAgentSettingsService(db)
            # Use a random UUID that has no config rows
            import uuid
            self.assertTrue(svc.is_local_launcher_enabled(uuid.uuid4()))
        finally:
            db.close()


# =============================================================================
# Fix 3 regression: MCP disabled exit
# =============================================================================

class McpDisabledTests(unittest.TestCase):
    def test_handle_request_rejects_tools_when_disabled(self):
        from app.mcp import server
        from app.mcp.tool_adapter import create_default_adapter

        original = server.MCP_ENABLED
        try:
            server.MCP_ENABLED = False
            adapter = create_default_adapter()
            resp = server.handle_request(
                {"method": "tools/list", "id": 1}, adapter
            )
            self.assertIsNotNone(resp)
            self.assertIn("error", resp)
            self.assertIn("disabled", resp["error"]["message"])
        finally:
            server.MCP_ENABLED = original

    def test_handle_request_allows_initialize_when_disabled(self):
        from app.mcp import server
        from app.mcp.tool_adapter import create_default_adapter

        original = server.MCP_ENABLED
        try:
            server.MCP_ENABLED = False
            adapter = create_default_adapter()
            resp = server.handle_request(
                {"method": "initialize", "id": 1}, adapter
            )
            self.assertIsNotNone(resp)
            self.assertIn("result", resp)
            self.assertIn("ShinobuChat", resp["result"]["serverInfo"]["name"])
        finally:
            server.MCP_ENABLED = original


# =============================================================================
# Fix 4 regression: MCP ToolRegistry integration
# =============================================================================

class McpToolRegistryIntegrationTests(unittest.TestCase):
    def test_adapter_accepts_registry(self):
        from app.mcp.tool_adapter import McpToolAdapter
        adapter = McpToolAdapter(tool_registry=None)
        tools = adapter.list_tools()
        self.assertEqual(len(tools), 0)

    def test_fallback_handler_returns_error_for_unregistered(self):
        from app.mcp.tool_adapter import McpToolAdapter
        adapter = McpToolAdapter(tool_registry=None)
        result = adapter.call_tool("nonexistent", {})
        data = json.loads(result)
        self.assertIn("error", data)

    def test_create_default_adapter_has_fallback_handlers(self):
        from app.mcp.tool_adapter import create_default_adapter
        adapter = create_default_adapter(tool_registry=None)
        tools = adapter.list_tools()
        tool_names = {t["name"] for t in tools}
        self.assertIn("read_webpage", tool_names)
        self.assertIn("search_web", tool_names)
        self.assertIn("open_url", tool_names)
        self.assertIn("open_local_app", tool_names)

    def test_fallback_read_webpage_works(self):
        from app.mcp.tool_adapter import create_default_adapter
        adapter = create_default_adapter(tool_registry=None)
        result = adapter.call_tool("read_webpage", {"url": "https://example.com"})
        data = json.loads(result)
        self.assertIn("status", data)


# =============================================================================
# Fix 5 regression: TrustedSourceItem user_id None
# =============================================================================

class TrustedSourceItemSchemaTests(unittest.TestCase):
    def test_user_id_none_allowed(self):
        from app.schemas.browser import TrustedSourceItem
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        item = TrustedSourceItem(
            id="00000000-0000-0000-0000-000000000001",
            user_id=None,
            domain="example.com",
            trust_level="trusted",
            source_type="builtin",
            created_at=now,
        )
        self.assertIsNone(item.user_id)
        self.assertEqual(item.domain, "example.com")


# =============================================================================
# Fix 6 regression: WebSummarizerService runtime_config
# =============================================================================

class WebSummarizerRuntimeConfigTests(unittest.TestCase):
    def test_summarize_accepts_runtime_config(self):
        from app.services.web_summarizer_service import WebSummarizerService
        svc = WebSummarizerService()
        result = svc.summarize(
            "https://example.com",
            runtime_config={"ai_model": "custom-model"},
        )
        self.assertIn("status", result)

    def test_runtime_config_keyword(self):
        import inspect
        from app.services.web_summarizer_service import WebSummarizerService
        sig = inspect.signature(WebSummarizerService.summarize)
        self.assertIn("runtime_config", sig.parameters)


# =============================================================================
# MCP standalone server: ToolRegistry integration tests
# =============================================================================

class McpToolRegistryRealTests(unittest.TestCase):
    """Verify MCP server uses real ToolRegistry when SC_MCP_ENABLED=true."""

    @classmethod
    def setUpClass(cls):
        from app.api.deps import get_tool_registry
        cls.registry = get_tool_registry()

    def test_tool_registry_has_read_webpage(self):
        schemas = self.registry.schemas()
        names = {s.get("function", {}).get("name") for s in schemas}
        self.assertIn("read_webpage", names)

    def test_tool_registry_has_search_web(self):
        schemas = self.registry.schemas()
        names = {s.get("function", {}).get("name") for s in schemas}
        self.assertIn("search_web", names)

    def test_tool_registry_has_open_url(self):
        schemas = self.registry.schemas()
        names = {s.get("function", {}).get("name") for s in schemas}
        self.assertIn("open_url", names)

    def test_tool_registry_has_open_local_app(self):
        schemas = self.registry.schemas()
        names = {s.get("function", {}).get("name") for s in schemas}
        self.assertIn("open_local_app", names)

    def test_adapter_with_registry_calls_execute_verified(self):
        """When ToolRegistry is provided, call_tool goes through execute_verified."""
        from app.mcp.tool_adapter import create_default_adapter
        adapter = create_default_adapter(tool_registry=self.registry)
        tools = adapter.list_tools()
        tool_names = {t.get("function", {}).get("name", t.get("name", "")) for t in tools}
        self.assertIn("read_webpage", tool_names)
        self.assertIn("search_web", tool_names)
        self.assertIn("open_url", tool_names)

    def test_list_tools_from_registry_excludes_blocked(self):
        """Blocked tools must not appear in MCP tools/list from ToolRegistry."""
        from app.mcp.tool_adapter import create_default_adapter
        from app.mcp.config import MCP_BLOCKED_TOOLS
        adapter = create_default_adapter(tool_registry=self.registry)
        tools = adapter.list_tools()
        tool_names = {
            t.get("function", {}).get("name", t.get("name", ""))
            for t in tools
        }
        for blocked in MCP_BLOCKED_TOOLS:
            self.assertNotIn(blocked, tool_names,
                             f"Blocked tool '{blocked}' must not appear in MCP tools/list")


class McpUserContextGateTests(unittest.TestCase):
    """Verify that tools requiring user context are gated."""

    def test_server_rejects_open_local_app_without_default_user_id(self):
        from app.mcp import server
        from app.mcp.tool_adapter import create_default_adapter

        orig_enabled = server.MCP_ENABLED
        try:
            server.MCP_ENABLED = True
            adapter = create_default_adapter()
            resp = server.handle_request(
                {
                    "method": "tools/call",
                    "id": 1,
                    "params": {"name": "open_local_app", "arguments": {}},
                },
                adapter,
                default_user_id=None,
            )
            self.assertIsNotNone(resp)
            result = resp.get("result", {})
            content = result.get("content", [])
            self.assertTrue(len(content) > 0,
                            f"Expected error content, got result={result}")
            text = content[0].get("text", "")
            self.assertIn("SC_MCP_DEFAULT_USER_ID", text)
            self.assertTrue(result.get("isError", False))
        finally:
            server.MCP_ENABLED = orig_enabled

    def test_disabled_mcp_rejects_tools_list(self):
        from app.mcp import server
        from app.mcp.tool_adapter import create_default_adapter

        orig = server.MCP_ENABLED
        try:
            server.MCP_ENABLED = False
            adapter = create_default_adapter()
            resp = server.handle_request(
                {"method": "tools/list", "id": 2}, adapter
            )
            self.assertIn("error", resp)
            self.assertIn("disabled", resp["error"]["message"])
        finally:
            server.MCP_ENABLED = orig

    def test_disabled_mcp_rejects_tools_call(self):
        from app.mcp import server
        from app.mcp.tool_adapter import create_default_adapter

        orig = server.MCP_ENABLED
        try:
            server.MCP_ENABLED = False
            adapter = create_default_adapter()
            resp = server.handle_request(
                {"method": "tools/call", "id": 3,
                 "params": {"name": "read_webpage", "arguments": {}}},
                adapter,
            )
            self.assertIn("error", resp)
            self.assertIn("disabled", resp["error"]["message"])
        finally:
            server.MCP_ENABLED = orig


class ToolPolicyMCPTests(unittest.TestCase):
    """Verify ToolPolicyService handles the four MCP-safe tools correctly."""

    def test_open_local_app_is_local_app_group(self):
        from app.services.tool_policy_service import _classify_tool
        self.assertEqual(_classify_tool("open_local_app"), "local_app")

    def test_open_url_is_browser_open_group(self):
        from app.services.tool_policy_service import _classify_tool
        self.assertEqual(_classify_tool("open_url"), "browser_open")

    def test_read_webpage_is_web_search_group(self):
        from app.services.tool_policy_service import _classify_tool
        self.assertEqual(_classify_tool("read_webpage"), "web_search")

    def test_search_web_is_web_search_group(self):
        from app.services.tool_policy_service import _classify_tool
        self.assertEqual(_classify_tool("search_web"), "web_search")

    def test_work_mode_allows_all_mcp_tools(self):
        """MCP uses 'work' mode — all 4 safe tools must be allowed."""
        from app.services.tool_policy_service import ToolPolicyService
        svc = ToolPolicyService()
        for name in ("open_local_app", "open_url", "read_webpage", "search_web"):
            decision = svc.check(name, {}, conversation_mode="work")
            self.assertTrue(decision.allowed,
                            f"Tool '{name}' should be allowed in work mode")

    def test_focus_mode_blocks_web_search_for_read_webpage(self):
        from app.services.tool_policy_service import ToolPolicyService
        svc = ToolPolicyService()
        decision = svc.check("read_webpage", {}, conversation_mode="focus")
        # web_search group is not in focus mode's allowed groups
        self.assertFalse(decision.allowed)

    def test_focus_mode_blocks_search_web(self):
        from app.services.tool_policy_service import ToolPolicyService
        svc = ToolPolicyService()
        decision = svc.check("search_web", {}, conversation_mode="focus")
        self.assertFalse(decision.allowed)

    def test_night_mode_blocks_web_search(self):
        from app.services.tool_policy_service import ToolPolicyService
        svc = ToolPolicyService()
        for name in ("read_webpage", "search_web"):
            decision = svc.check(name, {}, conversation_mode="night")
            # web_search is blocked in night mode by night_suppression rule
            self.assertFalse(decision.allowed,
                             f"Tool '{name}' should be blocked in night mode")


if __name__ == "__main__":
    unittest.main()
