"""
AI CHATBOT - Xotira + Internet + Hujjat qidiruv (v3)
========================================================
ISHLASH TARTIBI:
1. Avval MAHALLIY XOTIRADAN javob qidiradi (tezkor indeks orqali)
2. Topilmasa - INTERNETDAN (Vikipediya) qidiradi
3. Topilmasa - siz o'rgatgan HUJJATLAR ichidan qidiradi (xotiraning bir qismi)
4. Aniq mos ma'lumot - "aniq" deb, mos kelmasa - "taxminiy/menimcha" deb
   OCHIQ belgilanadi.

XOTIRA TUZILISHI (yangi, v3):
Har bir MANBA turi uchun ALOHIDA fayl:
    xotira_data/foydalanuvchi.json   <- siz qo'lda o'rgatgan narsalar
    xotira_data/internet.json        <- internetdan topib olingan narsalar
    xotira_data/hujjat.json          <- hujjatlardan o'qib olingan narsalar
    xotira_data/indeks.json          <- TEZKOR QIDIRUV uchun ko'rsatkich

Nega alohida fayllarga bo'lingan?
- Har bir manba alohida boshqarilishi, tozalanishi, tahlil qilinishi mumkin
- Kelajakda yangi "qobiliyat" (masalan: rasm tanish, ovoz) qo'shilsa,
  unga ham osongina alohida fayl ochiladi - boshqalarga tegmasdan

INDEKS nima uchun kerak?
Yozuvlar soni minglab bo'lganda, har safar HAMMASINI bittalab tekshirish
(fuzzy matching) juda SEKINLASHADI. Indeks - bu so'zning birinchi 3 harfi
bo'yicha oldindan tayyorlangan "xarita" - kitobning oxiridagi alifbo
ko'rsatkichi kabi. Qidiruvda avval shu xaritadan NOMZODLARNI tezda topamiz,
keyin FAQAT o'sha nomzodlarga aniqroq (fuzzy) solishtirish qilamiz.
Natija: minglab yozuv bo'lsa ham qidiruv tez ishlaydi.

MUHIM CHEKLOV (halol ogohlantirish):
Bu oddiy qidiruv dasturi, HAQIQIY sun'iy intellekt (LLM) EMAS.
Faqat: qidiradi -> topadi -> mos kelish darajasini o'lchaydi -> shunga qarab
"aniq" yoki "taxminiy/menimcha" deb belgilab, natijani ko'rsatadi.

TALABLAR:
    pip install requests          (internetdan qidirish uchun - majburiy)
    pip install pypdf             (PDF o'qish uchun - ixtiyoriy)
    pip install python-docx       (Word o'qish uchun - ixtiyoriy)
"""

import json
import os
from datetime import datetime
from difflib import SequenceMatcher

try:
    import requests
except ImportError:
    print("⚠️  'requests' kutubxonasi topilmadi.")
    print("   Termux'da shuni yozing: pip install requests")
    raise SystemExit(1)


# ============ SOZLAMALAR ============

XOTIRA_DIR = "xotira_data"
INDEKS_FAYL = os.path.join(XOTIRA_DIR, "indeks.json")
SINONIM_FAYL = os.path.join(XOTIRA_DIR, "sinonimlar.json")
OBUNA_FAYL = os.path.join(XOTIRA_DIR, "obuna_mavzular.json")
ESKI_XOTIRA_FAYL = "memory.json"          # eski (v1/v2) format - migratsiya uchun
ESKI_MATN_FAYL = "bilimlar.txt"

# Har bir manba turi -> fayl nomi. Yangi manba turi kelsa, shu yerga
# qo'shish kifoya - dastur avtomatik alohida fayl yaratadi.
MANBA_FAYLLARI = {
    "foydalanuvchi": os.path.join(XOTIRA_DIR, "foydalanuvchi.json"),
    "internet": os.path.join(XOTIRA_DIR, "internet.json"),
    "hujjat": os.path.join(XOTIRA_DIR, "hujjat.json"),
}

ANIQ_CHEGARA = 0.72       # shundan yuqori bo'lsa - "aniq mos"
TAXMINIY_CHEGARA = 0.45   # shundan past bo'lsa - natija umuman ko'rsatilmaydi


def manba_faylini_ol(manba):
    """Manba turi uchun fayl yo'lini qaytaradi. Agar bu YANGI manba turi
    bo'lsa (masalan, kelajakda 'rasm' yoki 'ovoz' qobiliyati qo'shilsa),
    avtomatik ravishda ro'yxatga va diskka yangi fayl sifatida qo'shiladi."""
    if manba not in MANBA_FAYLLARI:
        MANBA_FAYLLARI[manba] = os.path.join(XOTIRA_DIR, f"{manba}.json")
    return MANBA_FAYLLARI[manba]


def bazani_ornat(yangi_papka):
    """Xotira papkasini BOSHQA joyga ko'chiradi. Bu ASOSAN Android/Kivy
    ilovasida ishlatiladi - chunki Android'da har bir ilova FAQAT o'zining
    maxsus (ichki) papkasiga yoza oladi, tasodifiy joyga emas.

    main.py (Kivy ilovasi) shu funksiyani ISHGA TUSHGANDA DARHOL chaqiradi:
        backend.bazani_ornat(App.get_running_app().user_data_dir + '/xotira_data')
    """
    global XOTIRA_DIR, INDEKS_FAYL, SINONIM_FAYL, OBUNA_FAYL
    XOTIRA_DIR = yangi_papka
    INDEKS_FAYL = os.path.join(XOTIRA_DIR, "indeks.json")
    SINONIM_FAYL = os.path.join(XOTIRA_DIR, "sinonimlar.json")
    OBUNA_FAYL = os.path.join(XOTIRA_DIR, "obuna_mavzular.json")

    MANBA_FAYLLARI["foydalanuvchi"] = os.path.join(XOTIRA_DIR, "foydalanuvchi.json")
    MANBA_FAYLLARI["internet"] = os.path.join(XOTIRA_DIR, "internet.json")
    MANBA_FAYLLARI["hujjat"] = os.path.join(XOTIRA_DIR, "hujjat.json")

    os.makedirs(XOTIRA_DIR, exist_ok=True)


def fayllarni_avtomatik_aniqlash():
    """xotira_data papkasini SKANERLAYDI va u yerdagi BARCHA .json
    fayllarni (indeks.json dan tashqari) topib, MANBA_FAYLLARI ro'yxatiga
    qo'shadi.

    Bu - agar siz O'ZINGIZ qo'lda yangi .json fayl yaratib shu papkaga
    tashlasangiz (masalan, 'sport.json' yoki 'dasturlash.json'), dastur
    uni keyingi ishga tushishda AVTOMATIK TOPIB, xuddi boshqa xotira
    fayllari kabi qidiruvga qo'shib olishini ta'minlaydi.

    Fayl mazmuni quyidagi ko'rinishda bo'lishi kerak (JSON ro'yxat,
    har bir element kamida 'kalit_soz' va 'malumot' maydonlariga ega):
        [
          {"kalit_soz": "futbol", "malumot": "Futbol - 11 kishilik o'yin"},
          {"kalit_soz": "basketbol", "malumot": "Basketbol - 5 kishilik o'yin"}
        ]

    Qaytaradi: yangi topilgan manba nomlari ro'yxati.
    """
    if not os.path.isdir(XOTIRA_DIR):
        return []

    yangi_manbalar = []
    for fayl_nomi in sorted(os.listdir(XOTIRA_DIR)):
        if not fayl_nomi.endswith(".json") or fayl_nomi == "indeks.json":
            continue
        manba_nomi = fayl_nomi[:-len(".json")]
        if manba_nomi not in MANBA_FAYLLARI:
            MANBA_FAYLLARI[manba_nomi] = os.path.join(XOTIRA_DIR, fayl_nomi)
            yangi_manbalar.append(manba_nomi)
    return yangi_manbalar


def yozuv_yaroqlimi(yozuv):
    """Yozuv minimal talab qilingan maydonlarga ega ekanini tekshiradi
    ('kalit_soz' va 'malumot'). Qo'lda yaratilgan fayllarda xato/yetishmagan
    maydon bo'lsa, dastur qulamasin, shunchaki o'sha yozuvni o'tkazib yuboradi."""
    return (
        isinstance(yozuv, dict)
        and isinstance(yozuv.get("kalit_soz"), str)
        and isinstance(yozuv.get("malumot"), str)
        and yozuv["kalit_soz"].strip() != ""
    )


# ============ MATNNI NORMALLASHTIRISH ============
# Muammo: apostrof turli xil belgi bo'lishi mumkin, yoki foydalanuvchi
# ba'zan kirill klaviaturada yozadi ("салом" / "salom"). Bu funksiyalar
# ikkalasini bir xil ko'rinishga keltiradi.

APOSTROF_VARIANTLARI = ["'", "’", "ʻ", "`", "´", "ʼ"]

KIRILL_LOTIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "'", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def normalize(matn):
    """Matnni qidiruv uchun bir xil ko'rinishga keltiradi."""
    matn = matn.lower().strip()
    matn = "".join(KIRILL_LOTIN.get(harf, harf) for harf in matn)
    for variant in APOSTROF_VARIANTLARI:
        matn = matn.replace(variant, "'")
    return " ".join(matn.split())


# ============ FAYL BILAN ASOSIY ISHLASH ============

def fayl_yuklash(fayl_yoli):
    if not os.path.exists(fayl_yoli):
        return []
    with open(fayl_yoli, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def fayl_saqlash(fayl_yoli, malumot):
    os.makedirs(os.path.dirname(fayl_yoli) or ".", exist_ok=True)
    with open(fayl_yoli, "w", encoding="utf-8") as f:
        json.dump(malumot, f, ensure_ascii=False, indent=2)


# ============ TEZKOR QIDIRUV INDEKSI ============
# indeks tuzilishi: { "prefiks_3harf": [ {"manba": "...", "idx": 0}, ... ] }
# "idx" - o'sha manba faylidagi yozuvning ro'yxatdagi tartib raqami

def indeksni_yuklash():
    return fayl_yuklash(INDEKS_FAYL) or {}


def indeksni_saqlash(indeks):
    fayl_saqlash(INDEKS_FAYL, indeks)


def sozdan_prefikslar(matn_norm, uzunlik=3):
    """Matndagi har bir so'zning boshidan `uzunlik` harflik kalitni chiqaradi.
    Masalan: 'salom dunyo' -> {'sal', 'dun'}"""
    prefikslar = set()
    for soz in matn_norm.split():
        soz_tozalangan = soz.strip(".,!?;:")
        if len(soz_tozalangan) >= 2:
            prefikslar.add(soz_tozalangan[:uzunlik])
    return prefikslar


def indeksga_yozuv_qoshish(indeks, manba, idx, kalit_soz):
    """Yangi qo'shilgan yozuvni indeksga qayd etadi (tez qidiruv uchun)."""
    prefikslar = sozdan_prefikslar(normalize(kalit_soz))
    for prefiks in prefikslar:
        indeks.setdefault(prefiks, [])
        yozuv_havolasi = {"manba": manba, "idx": idx}
        if yozuv_havolasi not in indeks[prefiks]:
            indeks[prefiks].append(yozuv_havolasi)


def indeksdan_nomzodlarni_top(savol_norm):
    """Savol so'zlarining prefikslariga mos keladigan barcha yozuv
    havolalarini (manba + idx) qaytaradi - bular QIDIRUV NOMZODLARI."""
    indeks = indeksni_yuklash()
    prefikslar = sozdan_prefikslar(savol_norm)

    nomzodlar = set()
    for prefiks in prefikslar:
        for havola in indeks.get(prefiks, []):
            nomzodlar.add((havola["manba"], havola["idx"]))
    return nomzodlar


def indeksni_qaytadan_qurish():
    """Barcha manba fayllarini o'qib, indeksni noldan qayta yaratadi.
    Bu, jumladan, siz QO'LDA qo'shgan yangi .json fayllarni ham
    indekslash uchun ishlatiladi."""
    yangi_indeks = {}
    jami = 0
    for manba, fayl_yoli in MANBA_FAYLLARI.items():
        yozuvlar = fayl_yuklash(fayl_yoli)
        for idx, yozuv in enumerate(yozuvlar):
            if not yozuv_yaroqlimi(yozuv):
                continue
            indeksga_yozuv_qoshish(yangi_indeks, manba, idx, yozuv["kalit_soz"])
            jami += 1
    indeksni_saqlash(yangi_indeks)
    return jami


# ============ XOTIRAGA YOZUV QO'SHISH / O'QISH ============

def yangi_xotira_qoshish(kalit_soz, malumot, manba="foydalanuvchi", ishonch="aniq", manba_fayl=None):
    """Yangi ma'lumotni TEGISHLI MANBA FAYLIGA qo'shadi va indeksni yangilaydi.

    manba: 'foydalanuvchi', 'internet', 'hujjat' (yoki kelajakdagi yangi turlar)
    ishonch: 'aniq' yoki 'taxminiy'
    manba_fayl: hujjatdan olingan bo'lsa, asl fayl nomi (iqtibos uchun)
    """
    fayl_yoli = manba_faylini_ol(manba)
    yozuvlar = fayl_yuklash(fayl_yoli)

    yangi_yozuv = {
        "kalit_soz": kalit_soz.lower().strip(),
        "malumot": malumot.strip(),
        "sana": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "manba": manba,
        "ishonch": ishonch,
    }
    if manba_fayl:
        yangi_yozuv["manba_fayl"] = manba_fayl

    yozuvlar.append(yangi_yozuv)
    fayl_saqlash(fayl_yoli, yozuvlar)

    # Indeksni ham yangilaymiz (yangi yozuvning tartib raqami = eski uzunlik)
    indeks = indeksni_yuklash()
    indeksga_yozuv_qoshish(indeks, manba, len(yozuvlar) - 1, kalit_soz)
    indeksni_saqlash(indeks)


def kop_xotira_qoshish(yozuvlar_royxati):
    """Bir nechta yozuvni BIR VAQTDA, SAMARALI qo'shadi.
    Oddiy yangi_xotira_qoshish() har safar faylni qayta o'qib-yozadi -
    bu 100+ yozuv qo'shilganda (masalan, katta hujjat) SEKINLASHTIRADI.
    Bu funksiya faylni FAQAT BIR MARTA o'qiydi va BIR MARTA yozadi.

    yozuvlar_royxati: har biri {"kalit_soz", "malumot", "manba", "ishonch",
                                  "manba_fayl" (ixtiyoriy)} lug'atlaridan iborat ro'yxat
    """
    guruhlar = {}
    for y in yozuvlar_royxati:
        guruhlar.setdefault(y["manba"], []).append(y)

    indeks = indeksni_yuklash()
    for manba, royxat in guruhlar.items():
        fayl_yoli = manba_faylini_ol(manba)
        mavjud_yozuvlar = fayl_yuklash(fayl_yoli)
        boshlanish_idx = len(mavjud_yozuvlar)

        for i, y in enumerate(royxat):
            yangi_yozuv = {
                "kalit_soz": y["kalit_soz"].lower().strip(),
                "malumot": y["malumot"].strip(),
                "sana": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "manba": manba,
                "ishonch": y.get("ishonch", "aniq"),
            }
            if y.get("manba_fayl"):
                yangi_yozuv["manba_fayl"] = y["manba_fayl"]
            mavjud_yozuvlar.append(yangi_yozuv)
            indeksga_yozuv_qoshish(indeks, manba, boshlanish_idx + i, yangi_yozuv["kalit_soz"])

        fayl_saqlash(fayl_yoli, mavjud_yozuvlar)

    indeksni_saqlash(indeks)


# ============ AVTOMATIK YANGILANISH (OBUNA MAVZULAR) ============
# Muammo: Termux'da haqiqiy "background" fon jarayoni (cron) sozlash
# murakkab. Shuning uchun bu YENGIL yechim: siz "obuna" bo'lgan
# mavzular ro'yxatini saqlaymiz, dastur HAR ISHGA TUSHGANDA (yoki
# 'yangilash' buyrug'i bilan qo'lda) shu mavzularni internetdan qayta
# tekshirib, yangilab qo'yadi.

def obunalarni_yuklash():
    royxat = fayl_yuklash(OBUNA_FAYL)
    return royxat if isinstance(royxat, list) else []


def obunalarni_saqlash(royxat):
    fayl_saqlash(OBUNA_FAYL, royxat)


def obunaga_qoshish(mavzu):
    royxat = obunalarni_yuklash()
    mavzu = mavzu.strip()
    if mavzu and mavzu not in royxat:
        royxat.append(mavzu)
        obunalarni_saqlash(royxat)
        return True
    return False


def obuna_mavzularni_yangila():
    """Obunadagi har bir mavzuni internetdan qayta so'raydi va
    xotiradagi eski ma'lumotni YANGISI bilan almashtiradi."""
    royxat = obunalarni_yuklash()
    if not royxat:
        print("📭 Hozircha obuna bo'lgan mavzu yo'q.")
        print("   Qo'shish uchun: 'obuna' buyrug'ini ishlating.")
        return

    print(f"🔄 {len(royxat)} ta obuna mavzu yangilanmoqda...")
    for mavzu in royxat:
        natija = internetdan_qidir(mavzu)
        if natija is None:
            print(f"   ❌ '{mavzu}' - internetdan topilmadi (ulanish yo'qmi?)")
            continue

        qisqa = natija["matn"]
        if len(qisqa) > 600:
            qisqa = qisqa[:600].rsplit(".", 1)[0] + "."

        # Eski nusxasini o'chirib, yangisini qo'shamiz (eskirmasin uchun)
        eski_natijalar = xotiradan_qidir(mavzu)
        for ball, y in eski_natijalar:
            if y.get("manba") == "internet" and normalize(y["kalit_soz"]) == normalize(mavzu):
                # eski nusxani topib o'chiramiz
                fayl_yoli = manba_faylini_ol("internet")
                yozuvlar = fayl_yuklash(fayl_yoli)
                for idx, yz in enumerate(yozuvlar):
                    if yz is y:
                        yozuvni_ochir("internet", idx)
                        break
                break

        ishonch = "aniq" if natija["oxshashlik"] >= 0.55 else "taxminiy"
        yangi_xotira_qoshish(mavzu, qisqa, manba="internet", ishonch=ishonch)
        print(f"   ✅ '{mavzu}' yangilandi.")

    print("✨ Barcha obunalar yangilandi.")


# ============ UNUTISH MEXANIZMI ============
# Inson kabi: hamma narsani abadiy saqlash shart emas. Eskirgan yoki
# noto'g'ri chiqqan "taxminiy" ma'lumotlarni tozalash imkoniyati.

def yozuvni_ochir(manba, idx):
    """Berilgan manba faylidagi ma'lum tartib raqamli yozuvni o'chiradi.
    O'chirishdan keyin FAYLNI QAYTA SAQLAYDI va INDEKSNI QAYTA QURADI
    (chunki qolgan yozuvlarning tartib raqami bittaga siljiydi)."""
    fayl_yoli = manba_faylini_ol(manba)
    yozuvlar = fayl_yuklash(fayl_yoli)
    if idx < 0 or idx >= len(yozuvlar):
        return False, "Bunday tartib raqamli yozuv topilmadi."

    ochirilgan = yozuvlar.pop(idx)
    fayl_saqlash(fayl_yoli, yozuvlar)
    indeksni_qaytadan_qurish()  # tartib raqamlari siljigani uchun to'liq qayta qurish shart
    return True, ochirilgan


def eskirgan_taxminiylarni_top(kun_chegarasi=30):
    """'internet' manbasidan olingan va 'taxminiy' deb belgilangan,
    KUN_CHEGARASI kundan eski yozuvlarni topadi - bular tekshirib
    ko'rish/o'chirish uchun nomzodlar (chunki taxminiy va eski - ehtimol
    endi kerak emas yoki noto'g'ri bo'lishi mumkin)."""
    natijalar = []
    fayl_yoli = manba_faylini_ol("internet")
    yozuvlar = fayl_yuklash(fayl_yoli)
    bugun = datetime.now()

    for idx, y in enumerate(yozuvlar):
        if y.get("ishonch") != "taxminiy":
            continue
        try:
            sana = datetime.strptime(y["sana"], "%Y-%m-%d %H:%M")
        except (ValueError, KeyError):
            continue
        agar_kun = (bugun - sana).days
        if agar_kun >= kun_chegarasi:
            natijalar.append((idx, y, agar_kun))

    return natijalar


def tozalashni_boshqar():
    """Interaktiv: eskirgan taxminiy yozuvlarni ko'rsatib, foydalanuvchidan
    har birini o'chirish yoki qoldirishni so'raydi."""
    nomzodlar = eskirgan_taxminiylarni_top()
    if not nomzodlar:
        print("✨ Eskirgan taxminiy ma'lumot topilmadi - xotira toza!")
        return

    print(f"\n🗑️  {len(nomzodlar)} ta eskirgan (taxminiy, 30+ kunlik) yozuv topildi:\n")
    ochirilganlar = 0
    # Orqadan oldinga o'tamiz - shunda o'chirish paytida tartib raqamlari
    # boshqa yozuvlarga ta'sir qilmaydi
    for idx, y, agar_kun in sorted(nomzodlar, key=lambda x: -x[0]):
        qisqa = y['malumot'][:80] + ("..." if len(y['malumot']) > 80 else "")
        javob = input(f"  [{agar_kun} kun oldin] {qisqa}\n  O'chirilsinmi? (h/y): ").strip().lower()
        if javob == "h":
            yozuvni_ochir("internet", idx)
            ochirilganlar += 1
    print(f"\n✅ {ochirilganlar} ta yozuv o'chirildi.")


def barcha_xotiralar():
    """Barcha manbalardagi barcha yozuvlarni birlashtirib qaytaradi
    (asosan 'ro'yxat' buyrug'i uchun)."""
    hammasi = []
    for manba, fayl_yoli in MANBA_FAYLLARI.items():
        hammasi.extend(y for y in fayl_yuklash(fayl_yoli) if yozuv_yaroqlimi(y))
    return hammasi


# ============ SINONIMLAR (YENGIL "MA'NO BO'YICHA" QIDIRUV) ============
# To'liq semantik (embedding) qidiruv telefon uchun juda og'ir kutubxona
# talab qiladi. Buning o'rniga YENGIL, lekin foydali usul: sinonimlar
# lug'ati. Masalan "mashina" so'zi so'ralsa, "avtomobil" haqidagi
# ma'lumot ham topiladi - garchi harflari butunlay boshqa bo'lsa ham.
#
# xotira_data/sinonimlar.json faylini O'ZINGIZ ham to'ldirishingiz mumkin:
#   { "mashina": ["avtomobil", "transport"], "katta": ["ulkan", "gigant"] }

SINONIM_BOSHLANGICH = {
    "mashina": ["avtomobil", "transport", "unumdon"],
    "katta": ["ulkan", "gigant", "buyuk"],
    "kichik": ["mayda", "kichkina"],
    "chiroyli": ["go'zal", "ajoyib", "zebo"],
    "tez": ["shiddatli", "jadal"],
    "yordam": ["ko'mak", "yordamlashish"],
    "ish": ["mehnat", "faoliyat", "kasb"],
    "pul": ["mablag'", "moliya"],
    "uy": ["xonadon", "turar-joy"],
    "odam": ["inson", "shaxs", "kishi"],
}


def sinonimlarni_yuklash():
    """Diskdan sinonimlar lug'atini o'qiydi; bo'lmasa - boshlang'ich
    to'plamni faylga yozib, o'shani qaytaradi."""
    if not os.path.exists(SINONIM_FAYL):
        fayl_saqlash(SINONIM_FAYL, SINONIM_BOSHLANGICH)
        return dict(SINONIM_BOSHLANGICH)
    yuklangan = fayl_yuklash(SINONIM_FAYL)
    return yuklangan if isinstance(yuklangan, dict) else dict(SINONIM_BOSHLANGICH)


def savolni_sinonimlar_bilan_kengaytir(savol_norm):
    """Savoldagi har bir so'z uchun, agar sinonimlar lug'atida bo'lsa,
    ularni ham savolga QO'SHIB qo'yadi - shunda qidiruv nafaqat
    aynan so'zni, balki uning sinonimlarini ham topa oladi."""
    sinonimlar = sinonimlarni_yuklash()
    # Ikki yo'nalishli xarita quramiz: har bir so'z -> unga bog'liq barcha so'zlar
    bogliqlik = {}
    for asosiy, royxat in sinonimlar.items():
        barcha_guruh = [asosiy] + list(royxat)
        for soz in barcha_guruh:
            bogliqlik.setdefault(normalize(soz), set()).update(
                normalize(s) for s in barcha_guruh
            )

    savol_sozlar = savol_norm.split()
    kengaytirilgan = set(savol_sozlar)
    for soz in savol_sozlar:
        kengaytirilgan.update(bogliqlik.get(soz, set()))

    return " ".join(kengaytirilgan)


# ============ FUZZY (TAXMINIY) QIDIRUV MANTIG'I ============

def soz_oxshashligi(soz1, soz2):
    return SequenceMatcher(None, soz1, soz2).ratio()


def kalit_soz_mosligi(kalit_soz, savol_norm):
    if kalit_soz in savol_norm:
        return 1.0
    kalit_sozlar = kalit_soz.split()
    savol_sozlar = savol_norm.split()
    if not kalit_sozlar or not savol_sozlar:
        return 0.0
    ballar = [max(soz_oxshashligi(k, s) for s in savol_sozlar) for k in kalit_sozlar]
    return sum(ballar) / len(ballar)


def matn_ichida_soz_mosligi(malumot_norm, savol_norm):
    """Hujjat bo'laklari uchun: savoldagi so'zlar bo'lak matnida
    qancha uchrashini tekshiradi."""
    savol_sozlar = [s for s in savol_norm.split() if len(s) > 3]
    if not savol_sozlar:
        return 0.0
    topilgan = sum(1 for s in savol_sozlar if s in malumot_norm)
    return topilgan / len(savol_sozlar)


def xotiradan_qidir(savol):
    """
    TEZKOR qidiruv: avval indeks orqali NOMZODLARNI topadi (bu tez, chunki
    minglab yozuvni emas, faqat mos prefiksga ega yozuvlarni ko'radi),
    keyin faqat o'sha nomzodlarga to'liq fuzzy solishtirish qiladi.

    Natijalar (ball, yozuv) juftliklari sifatida, ball bo'yicha
    kamayish tartibida qaytariladi.
    """
    savol_norm = normalize(savol)
    savol_norm_kengaytirilgan = savolni_sinonimlar_bilan_kengaytir(savol_norm)
    nomzod_havolalari = indeksdan_nomzodlarni_top(savol_norm_kengaytirilgan)

    # Fayllarni bir marta xotiraga yuklab olamiz (bir necha nomzod bitta
    # fayldan bo'lishi mumkin - qayta-qayta diskdan o'qimaslik uchun)
    fayl_keshi = {}

    natijalar = []
    for manba, idx in nomzod_havolalari:
        fayl_yoli = manba_faylini_ol(manba)
        if fayl_yoli not in fayl_keshi:
            fayl_keshi[fayl_yoli] = fayl_yuklash(fayl_yoli)
        yozuvlar = fayl_keshi[fayl_yoli]

        if idx >= len(yozuvlar):
            continue  # indeks eskirgan bo'lishi mumkin - xavfsiz o'tkazib yuboramiz
        yozuv = yozuvlar[idx]
        if not yozuv_yaroqlimi(yozuv):
            continue  # qo'lda yaratilgan faylda noto'g'ri/yetishmagan maydon

        kalit_norm = normalize(yozuv["kalit_soz"])
        ball = kalit_soz_mosligi(kalit_norm, savol_norm)

        if yozuv.get("manba") == "hujjat":
            malumot_norm = normalize(yozuv["malumot"])
            ball = max(ball, matn_ichida_soz_mosligi(malumot_norm, savol_norm))

        if ball >= TAXMINIY_CHEGARA:
            natijalar.append((ball, yozuv))

    natijalar.sort(key=lambda x: x[0], reverse=True)
    return natijalar


# ============ HUJJATLARNI O'QISH ============

STOP_SOZLAR = {
    "va", "bu", "u", "bir", "uchun", "bilan", "ham", "yoki", "lekin", "esa",
    "ki", "deb", "edi", "bo'ladi", "qilib", "qiladi", "kerak", "mumkin",
    "shu", "o'sha", "har", "faqat", "juda", "ancha", "keyin", "endi",
    "the", "and", "is", "in", "to", "of", "a", "for", "on", "with", "as",
}


def txt_oqi(fayl_yoli):
    with open(fayl_yoli, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def pdf_oqi(fayl_yoli):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise RuntimeError("PDF o'qish uchun: pip install pypdf")
    reader = PdfReader(fayl_yoli)
    return "\n".join((sahifa.extract_text() or "") for sahifa in reader.pages)


def docx_oqi(fayl_yoli):
    try:
        import docx
    except ImportError:
        raise RuntimeError("Word o'qish uchun: pip install python-docx")
    d = docx.Document(fayl_yoli)
    return "\n".join(p.text for p in d.paragraphs)


def hujjatni_oqi(fayl_yoli):
    if not os.path.exists(fayl_yoli):
        raise FileNotFoundError(f"Fayl topilmadi: {fayl_yoli}")
    kengaytma = fayl_yoli.lower().rsplit(".", 1)[-1] if "." in fayl_yoli else ""
    if kengaytma == "txt":
        return txt_oqi(fayl_yoli)
    elif kengaytma == "pdf":
        return pdf_oqi(fayl_yoli)
    elif kengaytma == "docx":
        return docx_oqi(fayl_yoli)
    else:
        raise ValueError(f"Bu fayl turi qo'llab-quvvatlanmaydi: .{kengaytma}")


def matnni_boklarga_bol(matn, maks_hajm=500):
    paragraflar = [p.strip() for p in matn.split("\n") if p.strip()]
    boklar = []
    joriy_bok = ""
    for p in paragraflar:
        if len(joriy_bok) + len(p) <= maks_hajm:
            joriy_bok = (joriy_bok + " " + p).strip()
        else:
            if joriy_bok:
                boklar.append(joriy_bok)
            if len(p) > maks_hajm:
                for i in range(0, len(p), maks_hajm):
                    boklar.append(p[i:i + maks_hajm])
                joriy_bok = ""
            else:
                joriy_bok = p
    if joriy_bok:
        boklar.append(joriy_bok)
    return [b for b in boklar if len(b) > 20]


def kalit_sozlarni_chiqar(matn, soni=8):
    sozlar = normalize(matn).replace(",", " ").replace(".", " ").split()
    nomzodlar = [s for s in sozlar if len(s) > 3 and s not in STOP_SOZLAR]
    chastota, tartib = {}, []
    for s in nomzodlar:
        if s not in chastota:
            tartib.append(s)
        chastota[s] = chastota.get(s, 0) + 1
    tartib.sort(key=lambda s: chastota[s], reverse=True)
    tanlanganlar = tartib[:soni]
    return " ".join(tanlanganlar) if tanlanganlar else matn[:50]


def hujjatdan_ogren(fayl_yoli):
    try:
        matn = hujjatni_oqi(fayl_yoli)
    except Exception as e:
        return 0, str(e)

    if not matn or not matn.strip():
        return 0, "Hujjat bo'sh yoki matn chiqarib bo'lmadi (skanerlangan rasm bo'lishi mumkin)."

    boklar = matnni_boklarga_bol(matn)
    if not boklar:
        return 0, "Hujjatdan foydali matn topilmadi."

    fayl_nomi = os.path.basename(fayl_yoli)
    yangi_yozuvlar = [
        {
            "kalit_soz": kalit_sozlarni_chiqar(bok),
            "malumot": bok,
            "manba": "hujjat",
            "ishonch": "aniq",
            "manba_fayl": fayl_nomi,
        }
        for bok in boklar
    ]
    kop_xotira_qoshish(yangi_yozuvlar)
    return len(boklar), None


# ============ INTERNETDAN QIDIRISH (Vikipediya) ============

def internetdan_qidir(savol):
    for til in ["uz", "ru", "en"]:
        try:
            qidiruv_url = f"https://{til}.wikipedia.org/w/api.php"
            params = {"action": "opensearch", "search": savol, "limit": 3,
                      "namespace": 0, "format": "json"}
            r = requests.get(qidiruv_url, params=params, timeout=8)
            sarlavhalar = r.json()[1]
            if not sarlavhalar:
                continue

            eng_yaqin = max(sarlavhalar,
                             key=lambda t: SequenceMatcher(None, savol.lower(), t.lower()).ratio())
            oxshashlik = SequenceMatcher(None, savol.lower(), eng_yaqin.lower()).ratio()

            xulosa_url = f"https://{til}.wikipedia.org/api/rest_v1/page/summary/{eng_yaqin}"
            r2 = requests.get(xulosa_url, timeout=8)
            if r2.status_code != 200:
                continue
            summary = r2.json()
            matn = summary.get("extract", "")
            if not matn:
                continue

            return {
                "sarlavha": eng_yaqin, "matn": matn, "oxshashlik": oxshashlik,
                "til": til,
                "url": summary.get("content_urls", {}).get("desktop", {}).get("page", ""),
            }
        except requests.exceptions.RequestException:
            continue
    return None


# ============ ASOSIY JAVOB MANTIG'I ============

def javob_ber(savol):
    natijalar = xotiradan_qidir(savol)
    if natijalar:
        javob = "📚 Xotiramdan topdim:\n"
        for ball, y in natijalar[:3]:
            manba = y.get("manba", "foydalanuvchi")
            ishonch = y.get("ishonch", "aniq")
            mos_darajasi = "✅ aniq mos" if ball >= ANIQ_CHEGARA else f"🤏 taxminan mos ({int(ball*100)}%)"

            if manba == "foydalanuvchi":
                belgi = f"👤 siz o'rgatgansiz, {mos_darajasi}"
            elif manba == "hujjat":
                fayl = y.get("manba_fayl", "noma'lum fayl")
                belgi = f"📄 hujjatdan ({fayl}), {mos_darajasi}"
            elif ishonch == "aniq":
                belgi = f"🌐 avval internetdan olingan, {mos_darajasi}"
            else:
                belgi = f"🌐🤔 avval internetdan olingan (TAXMINIY edi), {mos_darajasi}"

            javob += f"\n  • {y['malumot']}\n    ({belgi})"
        return javob

    print("🔍 Xotirada yo'q, internetdan qidiryapman...")
    natija = internetdan_qidir(savol)

    if natija is None:
        return ("🤷 Xotirada ham, internetda ham hech narsa topa olmadim.\n"
                "   Savolni boshqacharoq so'rab ko'ring yoki 'o'rgat' orqali o'zingiz kiriting.")

    qisqa = natija["matn"]
    if len(qisqa) > 600:
        qisqa = qisqa[:600].rsplit(".", 1)[0] + "."

    if natija["oxshashlik"] >= 0.55:
        yangi_xotira_qoshish(savol, qisqa, manba="internet", ishonch="aniq")
        return (f"🌐 Internetdan aniq ma'lumot topdim — mavzu: \"{natija['sarlavha']}\"\n\n"
                f"{qisqa}\n\n🔗 Manba: {natija['url']}\n"
                f"💾 Keyingi safar tezroq javob berish uchun xotiraga saqladim.")
    else:
        yangi_xotira_qoshish(savol, qisqa, manba="internet", ishonch="taxminiy")
        return (f"🤔 Savolingizga aniq mos javob topa olmadim.\n"
                f"Lekin \"{natija['sarlavha']}\" mavzusi yaqin bo'lishi mumkin deb o'ylayman:\n\n"
                f"{qisqa}\n\n⚠️ MENIMCHA bu to'liq mos emas — ehtiyot bo'ling.\n"
                f"🔗 Manba: {natija['url']}")


# ============ ESKI FORMATDAN MIGRATSIYA (v1/v2 -> v3) ============

def eski_formatdan_kochir():
    """Agar diskda eski (bitta faylli) memory.json bo'lsa, uni yangi
    manba-bo'yicha-fayllar tizimiga ko'chiradi va indeksni quradi."""
    if not os.path.exists(ESKI_XOTIRA_FAYL):
        return 0

    eski_yozuvlar = fayl_yuklash(ESKI_XOTIRA_FAYL)
    if not eski_yozuvlar:
        os.rename(ESKI_XOTIRA_FAYL, ESKI_XOTIRA_FAYL + ".bak")
        return 0

    kochiriladigan_yozuvlar = [
        {
            "kalit_soz": y["kalit_soz"],
            "malumot": y["malumot"],
            "manba": y.get("manba", "foydalanuvchi"),
            "ishonch": y.get("ishonch", "aniq"),
            "manba_fayl": y.get("manba_fayl"),
        }
        for y in eski_yozuvlar
    ]
    kop_xotira_qoshish(kochiriladigan_yozuvlar)
    kochirildi = len(kochiriladigan_yozuvlar)

    os.rename(ESKI_XOTIRA_FAYL, ESKI_XOTIRA_FAYL + ".bak")
    if os.path.exists(ESKI_MATN_FAYL):
        os.rename(ESKI_MATN_FAYL, ESKI_MATN_FAYL + ".bak")

    return kochirildi


# ============ MENYU VA INTERFEYS ============

def yordam():
    print("""
╔════════════════════════════════════════════════╗
║        AI CHATBOT - Xotira + Internet           ║
╠════════════════════════════════════════════════╣
║  hujjat   - .txt/.pdf/.docx faylni o'qib,       ║
║             xotiraga o'rgatish                  ║
║  ro'yxat  - barcha xotirani ko'rish             ║
║  statistika - manbalar bo'yicha sonlarni ko'rish║
║  o'rgat   - qo'lda yangi ma'lumot qo'shish      ║
║  unut     - biror ma'lumotni xotiradan o'chirish║
║  tozalash - eskirgan taxminiy ma'lumotlarni     ║
║             ko'rib chiqib, kerak bo'lmaganini   ║
║             o'chirish                           ║
║  obuna    - mavzuni avtomatik yangilanadigan    ║
║             ro'yxatga qo'shish                  ║
║  yangilash - obunadagi mavzularni internetdan   ║
║              qayta yuklab, yangilash            ║
║  yordam   - shu ro'yxatni qayta ko'rsatish      ║
║  chiqish  - dasturdan chiqish                   ║
║  (boshqa matn - savol sifatida qabul qilinadi)  ║
╚════════════════════════════════════════════════╝

💡 Maslahat: xotira_data papkasiga o'zingiz .json fayl
   qo'shsangiz ({"kalit_soz":..,"malumot":..} ko'rinishida),
   dastur keyingi ishga tushishda uni AVTOMATIK taniydi.
""")


def xotiralarni_korsat():
    xotiralar = barcha_xotiralar()
    if not xotiralar:
        print("📭 Xotira hozircha bo'sh.")
        return
    print(f"\n📖 Jami {len(xotiralar)} ta ma'lumot:\n")
    for i, y in enumerate(xotiralar, 1):
        manba = y.get("manba", "foydalanuvchi")
        ishonch = y.get("ishonch", "aniq")
        qisqa = y['malumot'][:60] + ("..." if len(y['malumot']) > 60 else "")
        print(f"{i}. [{manba}/{ishonch}] {y['kalit_soz']} -> {qisqa}")
    print()


def statistikani_korsat():
    print("\n📊 Manbalar bo'yicha statistika:")
    jami = 0
    for manba, fayl_yoli in MANBA_FAYLLARI.items():
        soni = len(fayl_yuklash(fayl_yoli))
        jami += soni
        print(f"   {manba:15s}: {soni} ta yozuv  ({fayl_yoli})")
    print(f"   {'JAMI':15s}: {jami} ta yozuv\n")


def asosiy():
    print("=" * 55)
    print("  AI CHATBOT (Xotira + Internet + Hujjat, v3)")
    print("  Har bir manba alohida faylda, tezkor indeks bilan")
    print("=" * 55)

    os.makedirs(XOTIRA_DIR, exist_ok=True)

    kochirildi = eski_formatdan_kochir()
    if kochirildi:
        print(f"🔄 Eski xotiradan {kochirildi} ta yozuv yangi tizimga ko'chirildi.")

    yangi_manbalar = fayllarni_avtomatik_aniqlash()
    if yangi_manbalar:
        print(f"🆕 Yangi .json fayllar topildi va tanildi: {', '.join(yangi_manbalar)}")
        jami = indeksni_qaytadan_qurish()
        print(f"   Indeks qayta qurildi ({jami} ta yozuv indekslandi).")

    yordam()

    while True:
        kirish = input("\n👤 Siz: ").strip()
        if not kirish:
            continue

        if kirish.lower() in ["chiqish", "exit", "quit"]:
            print("👋 Xayr! Barcha yangi bilimlar xotirada saqlanib qoldi.")
            break

        elif kirish.lower() in ["yordam", "help"]:
            yordam()

        elif kirish.lower() in ["ro'yxat", "royxat", "list"]:
            xotiralarni_korsat()

        elif kirish.lower() in ["statistika", "stat"]:
            statistikani_korsat()

        elif kirish.lower() in ["hujjat", "document", "fayl"]:
            fayl_yoli = input("   📁 Fayl yo'lini kiriting: ").strip()
            if not fayl_yoli:
                print("⚠️  Fayl yo'li bo'sh bo'lmasligi kerak.")
                continue
            print("⏳ Hujjat o'qilmoqda...")
            soni, xato = hujjatdan_ogren(fayl_yoli)
            if xato:
                print(f"❌ Xatolik: {xato}")
            else:
                print(f"✅ {soni} ta bo'lak xotiraga saqlandi (hujjat.json fayliga).")

        elif kirish.lower() in ["o'rgat", "organ", "teach"]:
            k = input("   🔑 Kalit so'z: ").strip()
            m = input("   📝 Ma'lumot: ").strip()
            if k and m:
                yangi_xotira_qoshish(k, m, manba="foydalanuvchi", ishonch="aniq")
                print("✅ Saqlandi (foydalanuvchi.json fayliga).")
            else:
                print("⚠️  Bo'sh qoldirib bo'lmaydi.")

        elif kirish.lower() in ["unut", "ochir", "delete"]:
            savol = input("   🔍 Qaysi ma'lumotni o'chiramiz? (qidiruv so'zi): ").strip()
            natijalar = xotiradan_qidir(savol)
            if not natijalar:
                print("🤷 Hech narsa topilmadi.")
                continue
            print("\nTopilgan natijalar:")
            for i, (ball, y) in enumerate(natijalar[:5], 1):
                print(f"  {i}. [{y.get('manba')}] {y['malumot'][:70]}")
            tanlov = input("   Qaysi raqamni o'chiramiz? (bekor qilish uchun Enter): ").strip()
            if tanlov.isdigit() and 1 <= int(tanlov) <= len(natijalar[:5]):
                _, tanlangan_yozuv = natijalar[int(tanlov) - 1]
                # tanlangan yozuvning haqiqiy manba faylidagi tartib raqamini topamiz
                manba = tanlangan_yozuv.get("manba", "foydalanuvchi")
                fayl_yoli = manba_faylini_ol(manba)
                yozuvlar = fayl_yuklash(fayl_yoli)
                for idx, yz in enumerate(yozuvlar):
                    if yz == tanlangan_yozuv:
                        muvaffaqiyat, _ = yozuvni_ochir(manba, idx)
                        print("✅ O'chirildi." if muvaffaqiyat else "❌ O'chirib bo'lmadi.")
                        break
            else:
                print("⏹️  Bekor qilindi.")

        elif kirish.lower() in ["tozalash", "cleanup"]:
            tozalashni_boshqar()

        elif kirish.lower() in ["obuna", "subscribe"]:
            mavzu = input("   📌 Qaysi mavzuni avtomatik yangilab turaylik?: ").strip()
            if obunaga_qoshish(mavzu):
                print(f"✅ '{mavzu}' obunalar ro'yxatiga qo'shildi.")
                print("   'yangilash' buyrug'i bilan darhol yuklab olishingiz mumkin.")
            else:
                print("⚠️  Bo'sh yoki allaqachon mavjud.")

        elif kirish.lower() in ["yangilash", "update"]:
            obuna_mavzularni_yangila()

        else:
            javob = javob_ber(kirish)
            print(f"\n🤖 AI: {javob}")


if __name__ == "__main__":
    asosiy()
