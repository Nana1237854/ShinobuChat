"""Rewrite imports to use new app.domains.* paths.

Run after each migration batch. Only touches .py files.
Check git diff after each run.
"""

from pathlib import Path

IMPORT_MAP = {
    # Step 2: Browser / Download / Web domain
    "app.services.browser.browser_facade_service": "app.domains.browser.browser_facade_service",
    "app.services.browser.browser_action_log_service": "app.domains.browser.logs.browser_action_log_service",
    "app.services.browser.trusted_download_source_service": "app.domains.browser.trusted_sources.trusted_download_source_service",
    "app.services.browser_automation_service": "app.domains.browser.browser_automation_service",
    "app.services.web_reader_service": "app.domains.browser.web_reader_service",
    "app.services.web_search_service": "app.domains.browser.web_search_service",
    "app.services.web_summarizer_service": "app.domains.browser.web_summarizer_service",
    "app.services.download_service": "app.domains.browser.download.download_service",
    "app.services.download_candidate_extractor": "app.domains.browser.download.download_candidate_extractor",
    "app.services.download_risk_classifier": "app.domains.browser.download.download_risk_classifier",
    # Step 3: Local Agent
    "app.services.local_agent_settings_service": "app.domains.local_agent.local_agent_settings_service",
    "app.services.local_app_service": "app.domains.local_agent.local_app_service",
    # Step 4: MCP (only non-wrapper references)
    # Step 5: Tasks
    "app.services.tasks.task_event_store": "app.domains.tasks.task_event_store",
    "app.services.tasks.task_event_service": "app.domains.tasks.task_event_service",
    "app.services.tasks.task_run_service": "app.domains.tasks.task_run_service",
    # Step 6: Jobs
    "app.services.jobs.job_base": "app.domains.jobs.job_base",
    "app.services.jobs.job_scheduler": "app.domains.jobs.job_scheduler",
    "app.services.jobs.job_registry": "app.domains.jobs.job_registry",
    "app.services.jobs.job_run_log_service": "app.domains.jobs.job_run_log_service",
    "app.services.jobs.reminder_scan_job": "app.domains.jobs.reminder_scan_job",
    "app.services.jobs.goal_checkin_job": "app.domains.jobs.goal_checkin_job",
    "app.services.jobs.diary_generation_job": "app.domains.jobs.diary_generation_job",
    # Step 7: Capabilities / BehaviorEngine
    "app.services.behavior_engine": "app.domains.agent.behavior_engine",
    "app.services.capabilities.capability_registry": "app.domains.capabilities.capability_registry",
    "app.services.capabilities.capability_policy_service": "app.domains.capabilities.capability_policy_service",
    # Step 8: Observability
    "app.services.action_audit_service": "app.domains.observability.action_audit_service",
    "app.services.prompt_trace_service": "app.domains.observability.prompt_trace_service",
    "app.services.skill_run_log_service": "app.domains.observability.skill_run_log_service",
}

ROOTS = [
    Path("app"),
    Path("tests"),
]

SKIP_PATTERNS = [
    # Skip compat wrappers (old service files that are now wrappers)
    "app/services/browser/browser_action_log_service.py",
    "app/services/browser/trusted_download_source_service.py",
    "app/services/browser/browser_facade_service.py",
    "app/services/browser_automation_service.py",
    "app/services/web_reader_service.py",
    "app/services/web_search_service.py",
    "app/services/web_summarizer_service.py",
    "app/services/download_service.py",
    "app/services/download_candidate_extractor.py",
    "app/services/download_risk_classifier.py",
    "app/services/local_agent_settings_service.py",
    "app/services/local_app_service.py",
    # Will be wrappers later
    "app/mcp/server.py",
    "app/mcp/config.py",
    "app/mcp/tool_adapter.py",
]


def should_skip(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    for skip in SKIP_PATTERNS:
        if path_str.endswith(skip):
            return True
    return False


def main():
    updated = 0
    for root in ROOTS:
        for path in root.rglob("*.py"):
            if should_skip(path):
                continue
            text = path.read_text(encoding="utf-8")
            old_text = text

            for old_mod, new_mod in IMPORT_MAP.items():
                text = text.replace(f"from {old_mod} import", f"from {new_mod} import")
                text = text.replace(f"import {old_mod}", f"import {new_mod}")

            if text != old_text:
                path.write_text(text, encoding="utf-8")
                updated += 1
                print(f"  updated {path}")

    print(f"\n{updated} files updated.")


if __name__ == "__main__":
    main()
