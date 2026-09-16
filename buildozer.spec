[app]

# Ilova nomi - telefoningizda shu nom bilan ko'rinadi
title = Xotira AI

# Ichki paket nomi (o'zgartirmasangiz ham bo'ladi)
package.name = xotiraai
package.domain = org.xotiraai

# Qaysi fayllarni APK ichiga qo'shish kerak
source.dir = .
source.include_exts = py,json,png,jpg,kv,atlas

# Ilova versiyasi
version = 0.1

# KERAKLI KUTUBXONALAR
# Diqqat: pypdf va python-docx BU YERGA ATAYLAB QO'SHILMAGAN, chunki ular
# ba'zan buildozer'da murakkab qurilish xatolariga sabab bo'ladi. Shuning
# uchun BIRINCHI versiyada hujjat (PDF/Word) o'qish ISHLAMAYDI - faqat
# qidiruv, o'rgatish va internetdan izlash ishlaydi. Keyinroq qo'shish mumkin.
requirements = python3,kivy==2.3.0,requests,certifi,chardet,idna,urllib3

# Ilova ikonkasi (ixtiyoriy - agar icon.png qo'ysangiz shu yerga yo'lini yozing)
# icon.filename = %(source.dir)s/icon.png

# Ilova qaysi yo'nalishda ochilishi (portrait = tik, landscape = yotiq)
orientation = portrait

# Android sozlamalari
fullscreen = 0

# Kerakli ruxsatlar - faqat INTERNET (chunki Vikipediyadan qidiradi)
# Fayl saqlash uchun maxsus ruxsat KERAK EMAS, chunki biz ilovaning
# O'ZIGA TEGISHLI ichki papkasidan foydalanamiz (user_data_dir).
android.permissions = INTERNET

# Minimal va maqsadli Android versiyalari
android.minapi = 21
android.api = 33
android.ndk_api = 21

# Arxitekturalar (aksariyat zamonaviy telefonlar uchun)
android.archs = arm64-v8a, armeabi-v7a

[buildozer]

# Qurilish jarayonida ko'rsatiladigan xabarlar darajasi (2 = batafsil)
log_level = 2

# Ildiz papkasi tozalanmasin (qayta qurishda tezroq bo'lishi uchun)
warn_on_root = 1
