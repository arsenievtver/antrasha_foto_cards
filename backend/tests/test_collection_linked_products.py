from types import SimpleNamespace

from app.services.moysklad_image import collection_product_ids


def test_collection_product_ids_single():
    job = SimpleNamespace(
        moysklad_product_id="aaa",
        linked_products=None,
    )
    assert collection_product_ids(job) == ["aaa"]


def test_collection_product_ids_bundle():
    job = SimpleNamespace(
        moysklad_product_id="aaa",
        linked_products=[
            {"product_id": "bbb", "barcode": "2"},
            {"product_id": "ccc", "barcode": "3"},
        ],
    )
    assert collection_product_ids(job) == ["aaa", "bbb", "ccc"]


def test_collection_product_ids_dedup():
    job = SimpleNamespace(
        moysklad_product_id="aaa",
        linked_products=[{"product_id": "aaa"}],
    )
    assert collection_product_ids(job) == ["aaa"]
