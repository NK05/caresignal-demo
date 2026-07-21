from app.content import PATIENT_TEXT, patient_text
from app.models import Language


def test_all_patient_templates_have_matching_keys_and_nonempty_values() -> None:
    expected = set(PATIENT_TEXT[Language.ENGLISH])
    assert set(PATIENT_TEXT) == {Language.ENGLISH, Language.SHONA, Language.NDEBELE}
    for messages in PATIENT_TEXT.values():
        assert set(messages) == expected
        assert all(value.strip() for value in messages.values())


def test_patient_text_uses_requested_supported_language() -> None:
    assert patient_text(Language.SHONA, "confirmed") == "Kuverengwa kwasimbiswa."
    assert patient_text(Language.NDEBELE, "confirmed") == "Ukubalwa sekuqinisekisiwe."
