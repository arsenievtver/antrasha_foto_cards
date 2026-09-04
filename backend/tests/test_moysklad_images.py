import unittest

from app.externals.http.moysklad import MoySkladClient


class MoySkladImagePreviewTests(unittest.TestCase):
    def test_preview_href_prefers_tiny(self):
        row = {
            "tiny": {"href": "https://api.moysklad.ru/tiny.png"},
            "miniature": {"href": "https://api.moysklad.ru/mini.png"},
            "meta": {"downloadHref": "https://api.moysklad.ru/full.png"},
        }
        self.assertEqual(
            MoySkladClient._preview_href_from_image_row(row),
            "https://api.moysklad.ru/tiny.png",
        )

    def test_preview_href_falls_back_to_download(self):
        row = {"meta": {"downloadHref": "https://api.moysklad.ru/full.png"}}
        self.assertEqual(
            MoySkladClient._preview_href_from_image_row(row),
            "https://api.moysklad.ru/full.png",
        )

    def test_preview_href_empty(self):
        self.assertIsNone(MoySkladClient._preview_href_from_image_row({}))


if __name__ == "__main__":
    unittest.main()
