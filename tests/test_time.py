import unittest
from datetime import datetime

from app.core.time import local_now


class LocalTimeTests(unittest.TestCase):
    def test_local_now_matches_system_timezone(self):
        now = local_now()

        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), datetime.now().astimezone().utcoffset())


if __name__ == "__main__":
    unittest.main()
