import uuid
from types import SimpleNamespace

from app.services.brand_match import apply_supplier_link, match_supplier


def _brand(name, moysklad_id=None):
    return SimpleNamespace(id=uuid.uuid4(), name=name, moysklad_id=moysklad_id)


def test_linked_by_id_when_names_differ():
    brand = _brand("MaxMara", "abc")
    match = match_supplier([brand], "ABC", "MAX MARA (жен)")
    assert match.confidence == "linked"
    assert match.brand_id == brand.id
    assert match.warning
    assert "MaxMara" in match.warning


def test_linked_same_name_has_no_warning():
    brand = _brand("Max Mara", "abc")
    match = match_supplier([brand], "abc", "max mara (жен)")
    assert match.confidence == "linked"
    assert match.warning is None


def test_name_match_warns_until_id_is_saved():
    brand = _brand("Max Mara")
    match = match_supplier([brand], "abc", "MAX MARA (муж)")
    assert match.confidence == "name"
    assert match.brand_id == brand.id
    assert "Id ещё не записан" in (match.warning or "")


def test_name_of_already_linked_brand_is_not_suggested():
    brand = _brand("Max Mara", "other")
    match = match_supplier([brand], "abc", "Max Mara")
    assert match.confidence == "none"
    assert match.brand_id is None
    assert "другой id" in (match.warning or "")


def test_unknown_supplier_asks_to_choose():
    match = match_supplier([_brand("Другой")], "abc", "Неизвестный")
    assert match.confidence == "none"
    assert "Неизвестный" in (match.warning or "")


def test_apply_link_writes_id_once():
    brand = _brand("Max Mara")
    other = _brand("Other")
    assert apply_supplier_link(brand, "ABC", [brand, other]) is None
    assert brand.moysklad_id == "abc"
    assert apply_supplier_link(brand, "abc", [brand, other]) is None
    err = apply_supplier_link(other, "abc", [brand, other])
    assert err and "Max Mara" in err


def test_apply_link_refuses_second_supplier_on_same_brand():
    brand = _brand("Max Mara", "kept")
    err = apply_supplier_link(brand, "new", [brand])
    assert err
    assert brand.moysklad_id == "kept"
