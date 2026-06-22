import unittest


class AppImportTests(unittest.TestCase):
    def test_fastapi_application_imports(self) -> None:
        from app.main import app

        self.assertEqual(app.title, "ShinobuChat Core API")


if __name__ == "__main__":
    unittest.main()
