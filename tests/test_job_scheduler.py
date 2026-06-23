"""JobScheduler semi-integration tests with in-memory SQLite (Phase 3 fix).

Covers: disabled jobs not registered, success/failure logging, failure isolation.
"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.job_run_log import JobRunLog
from app.services.jobs.job_base import BaseJob, JobResult
from app.services.jobs.job_run_log_service import JobRunLogService
from app.services.jobs.job_scheduler import JobScheduler


class SuccessJob(BaseJob):
    name = "success_job"
    interval_seconds = 1
    enabled = True

    def run_once(self):
        return JobResult(status="success", summary="ok")


class FailingJob(BaseJob):
    name = "failing_job"
    interval_seconds = 1
    enabled = True

    def run_once(self):
        raise RuntimeError("boom")


class DisabledJob(BaseJob):
    name = "disabled_job"
    interval_seconds = 1
    enabled = False

    def run_once(self):
        return JobResult(status="success", summary="should not run")


class JobSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _make_scheduler(self, jobs):
        return JobScheduler(
            jobs=jobs,
            log_service_class=JobRunLogService,
            session_factory=self.Session,
        )

    def test_disabled_job_not_registered(self):
        scheduler = self._make_scheduler([SuccessJob(), DisabledJob()])
        names = [job.name for job in scheduler.jobs]
        self.assertIn("success_job", names)
        self.assertNotIn("disabled_job", names)

    def test_run_once_success_records_log(self):
        scheduler = self._make_scheduler([SuccessJob()])
        scheduler.run_once_for_test(SuccessJob())

        db = self.Session()
        row = db.query(JobRunLog).filter(JobRunLog.job_name == "success_job").first()
        db.close()

        self.assertIsNotNone(row)
        self.assertEqual(row.status, "success")
        self.assertEqual(row.result_summary, "ok")

    def test_run_once_failure_records_log(self):
        scheduler = self._make_scheduler([FailingJob()])
        scheduler.run_once_for_test(FailingJob())

        db = self.Session()
        row = db.query(JobRunLog).filter(JobRunLog.job_name == "failing_job").first()
        db.close()

        self.assertIsNotNone(row)
        self.assertEqual(row.status, "failed")
        self.assertIn("boom", row.error_message)

    def test_run_once_failure_does_not_raise(self):
        """Failing job must not propagate exception to caller."""
        scheduler = self._make_scheduler([FailingJob()])
        try:
            scheduler.run_once_for_test(FailingJob())
        except Exception as exc:
            self.fail(f"run_once_for_test should not raise, but got: {exc}")

    def test_one_failed_job_does_not_block_success_job(self):
        scheduler = self._make_scheduler([FailingJob(), SuccessJob()])

        scheduler.run_once_for_test(FailingJob())
        scheduler.run_once_for_test(SuccessJob())

        db = self.Session()
        failed = db.query(JobRunLog).filter(JobRunLog.job_name == "failing_job").first()
        success = db.query(JobRunLog).filter(JobRunLog.job_name == "success_job").first()
        db.close()

        self.assertEqual(failed.status, "failed")
        self.assertEqual(success.status, "success")

    def test_run_once_for_test_records_duration(self):
        scheduler = self._make_scheduler([SuccessJob()])
        scheduler.run_once_for_test(SuccessJob())

        db = self.Session()
        row = db.query(JobRunLog).filter(JobRunLog.job_name == "success_job").first()
        db.close()

        self.assertIsNotNone(row.started_at)
        self.assertIsNotNone(row.finished_at)
        self.assertGreaterEqual(row.duration_ms, 0)
