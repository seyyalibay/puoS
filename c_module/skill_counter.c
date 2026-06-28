/*
 * skill_counter.c — Beceri frekans sayımı (C katmanı).
 *
 * DERS PROJESİ ŞARTI: En az 1 satır C kodu. Frekans sayımı burada,
 * Python'a ctypes ile bağlanıyor (bkz. processors/skill_counter_bridge.py).
 *
 * Derleme (macOS / Linux):
 *   cc -O2 -shared -fPIC -o skill_counter.so skill_counter.c
 *
 * Fonksiyonlar:
 *   count_occurrences(haystack, needle)
 *     -> substring sayımı (strstr tabanlı, kelime sınırı yok).
 *   count_word_boundary(haystack, needle)
 *     -> kelime sınırı zorunlu sayım: eşleşmeden önce/sonra [a-z0-9] gelmemeli.
 *      Kısa/belirsiz skill kısaltmaları için kullanılır (defi, bim, ios vb.).
 *   Çağıran taraf her iki metni de küçük harfe normalize ETMİŞ olmalı.
 */
#include <string.h>

/* Kelime karakteri: küçük harf veya rakam (normalize edilmiş metin varsayılır). */
static int is_word_char(char c)
{
    return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

long count_occurrences(const char *haystack, const char *needle)
{
    if (haystack == NULL || needle == NULL)
        return 0;

    size_t nlen = strlen(needle);
    if (nlen == 0)
        return 0;

    long count = 0;
    const char *p = haystack;
    const char *hit;

    while ((hit = strstr(p, needle)) != NULL) {
        count++;
        p = hit + nlen;
    }
    return count;
}

long count_word_boundary(const char *haystack, const char *needle)
{
    if (haystack == NULL || needle == NULL)
        return 0;

    size_t nlen = strlen(needle);
    if (nlen == 0)
        return 0;

    long count = 0;
    const char *p = haystack;
    const char *hit;

    while ((hit = strstr(p, needle)) != NULL) {
        char before = (hit > haystack) ? *(hit - 1) : '\0';
        char after  = *(hit + nlen);
        if (!is_word_char(before) && !is_word_char(after)) {
            count++;
        }
        p = hit + nlen;
    }
    return count;
}
