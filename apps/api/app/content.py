from app.models import Language


PATIENT_TEXT: dict[Language, dict[str, str]] = {
    Language.ENGLISH: {
        "ready": "Please check the extracted details and confirm or correct them.",
        "fallback": (
            "I could not safely prepare that reading. Please try again or use the "
            "structured reading form."
        ),
        "clarify": (
            "I need a little more information. Please include both BP numbers, when you "
            "measured them, and whether you took your medication."
        ),
        "ambiguous": (
            "I could not interpret that safely. Please rephrase it or use the structured "
            "reading form."
        ),
        "confirmed": "Reading confirmed.",
        "confirmed_notified": "Reading confirmed. Your care team has been notified for review.",
        "cancelled": "Reading cancelled. Nothing was added to your history.",
        "corrected": "The extracted reading was cancelled. Please send the corrected details.",
        "pending": (
            "Please confirm, correct, or cancel the extracted reading before sending another."
        ),
        "confirm_command": "Confirm reading",
        "cancel_command": "Cancel reading",
    },
    Language.SHONA: {
        "ready": "Ndapota tarisai zvakabviswa mumashoko enyu, mozvisimbisa kana kuzvigadzirisa.",
        "fallback": (
            "Handina kukwanisa kugadzira kuverengwa uku zvakachengeteka. Edzai zvakare "
            "kana kushandisa fomu rekuisa BP."
        ),
        "clarify": (
            "Ndinoda rumwe ruzivo. Nyorerai manhamba ese eBP, nguva yayakayerwa, uye "
            "kana makanwa mushonga wenyu."
        ),
        "ambiguous": (
            "Handina kukwanisa kunzwisisa izvi zvakachengeteka. Nyorerai zvakare kana "
            "kushandisa fomu rekuisa BP."
        ),
        "confirmed": "Kuverengwa kwasimbiswa.",
        "confirmed_notified": (
            "Kuverengwa kwasimbiswa. Chikwata chenyu cheutano chaziviswa kuti chiongorore."
        ),
        "cancelled": "Kuverengwa kwakanzurwa. Hapana chawedzerwa munhoroondo yenyu.",
        "corrected": (
            "Kuverengwa kwakabviswa mumashoko enyu kwakanzurwa. Tumirai mashoko akarurama."
        ),
        "pending": "Ndapota simbisa, gadzirisa, kana kanzura kuverengwa uku musati matumira kumwe.",
        "confirm_command": "Simbisa kuverengwa",
        "cancel_command": "Kanzura kuverengwa",
    },
    Language.NDEBELE: {
        "ready": "Sicela uhlole imininingwane ekhishiweyo, uyiqinisekise kumbe uyilungise.",
        "fallback": (
            "Angenelisanga ukulungisa lokhu kubalwa ngokuphepha. Zama futhi kumbe "
            "usebenzise ifomu lokufaka i-BP."
        ),
        "clarify": (
            "Ngidinga eminye imininingwane. Faka amanani womabili e-BP, isikhathi "
            "owayilinganisa ngaso, lokuthi wawuthatha yini umuthi wakho."
        ),
        "ambiguous": (
            "Angenelisanga ukukuzwisisa ngokuphepha. Bhala kutsha kumbe usebenzise "
            "ifomu lokufaka i-BP."
        ),
        "confirmed": "Ukubalwa sekuqinisekisiwe.",
        "confirmed_notified": (
            "Ukubalwa sekuqinisekisiwe. Ithimba lakho lezempilakahle selazisiwe ukuthi "
            "likuhlole."
        ),
        "cancelled": "Ukubalwa kukhanseleliwe. Akulalutho olufakwe embalini yakho.",
        "corrected": (
            "Ukubalwa obekukhitshwe emlayezweni kukhanseleliwe. Thumela imininingwane "
            "elungisiweyo."
        ),
        "pending": (
            "Sicela uqinisekise, ulungise, kumbe ukhansele ukubalwa lokhu ungakathumeli "
            "okunye."
        ),
        "confirm_command": "Qinisekisa ukubalwa",
        "cancel_command": "Khansela ukubalwa",
    },
}


def patient_text(language: Language, key: str) -> str:
    return PATIENT_TEXT.get(language, PATIENT_TEXT[Language.ENGLISH])[key]
