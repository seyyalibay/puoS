"""
skill_counter_bridge.py — C modülüne ctypes köprüsü.

c_module/skill_counter.so derlenmişse onu yükler ve sayım fonksiyonlarını
C'den çağırır (DERS PROJESİ ŞARTI: frekans sayımı C'de). Derlenmemişse
saf-Python fallback'e düşer.

Kullanım:
    from processors.skill_counter_bridge import count_occurrences, count_word_boundary
    count_occurrences("we use python", "python")   # -> 1 (substring)
    count_word_boundary("defi protocol", "defi")   # -> 1 (tam kelime)
    count_word_boundary("definitely", "defi")      # -> 0 (kelime sınırı ihlali)
"""
import ctypes
import os

_SO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "c_module",
    "skill_counter.so",
)

_lib = None
USING_C = False

try:
    _lib = ctypes.CDLL(_SO_PATH)
    _lib.count_occurrences.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.count_occurrences.restype = ctypes.c_long
    _lib.count_word_boundary.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    _lib.count_word_boundary.restype = ctypes.c_long
    USING_C = True
except OSError:
    _lib = None
    USING_C = False


def count_occurrences(haystack: str, needle: str) -> int:
    """needle'ın haystack içinde kaç kez (örtüşmeyen) geçtiğini döndürür.
    Kelime sınırı yok — genel substring sayımı.
    """
    if not needle:
        return 0
    if USING_C:
        return int(_lib.count_occurrences(haystack.encode("utf-8"), needle.encode("utf-8")))
    return haystack.count(needle)


def count_word_boundary(haystack: str, needle: str) -> int:
    """needle'ın haystack içinde tam kelime olarak kaç kez geçtiğini döndürür.
    Eşleşmeden önce/sonra [a-z0-9] gelmemelidir.
    C .so varsa C'den, yoksa Python regex fallback'inden.
    """
    if not needle:
        return 0
    if USING_C:
        return int(_lib.count_word_boundary(haystack.encode("utf-8"), needle.encode("utf-8")))
    import re
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
    return len(re.findall(pattern, haystack))
