"""
XOTIRA AI - MOBIL ILOVA (Kivy)
=================================
Bu fayl ai_chatbot.py dagi mantiqni ANDROID ILOVASI ko'rinishida
taqdim etadi. Kivy - Python bilan mobil interfeys yaratish kutubxonasi.

MUHIM: bu fayl ai_chatbot.py bilan BIR PAPKADA bo'lishi SHART,
chunki u undagi funksiyalarni to'g'ridan-to'g'ri ishlatadi.

Bu faylni o'zingiz kompyuteringizda ishga tushirmaysiz - buildozer
uni APK ichiga "quyadi" va telefonda ishlaydigan qilib beradi.
"""

import os
import threading

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.utils import platform

import ai_chatbot as backend


class XotiraAIApp(App):
    title = "Xotira AI"

    def build(self):
        # ANDROID/OBB PAPKASINI ANIQLASH:
        # Bu - ilovaga tegishli, lekin TASHQI (ochiq) xotiradagi maxsus papka.
        # Ruxsat so'ramaydi (Android buni ilovaning "o'ziniki" deb biladi),
        # lekin Android 11+ da boshqa fayl menejerlari uni ko'ra olmasligi
        # mumkin (bu Android'ning o'zining maxfiylik cheklovi).
        xotira_yoli = self._xotira_papkasini_aniqla()
        backend.bazani_ornat(xotira_yoli)
        backend.eski_formatdan_kochir()
        backend.fayllarni_avtomatik_aniqlash()

        # ---- Asosiy joylashuv ----
        asosiy = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))

        sarlavha = Label(
            text="[b]Xotira AI[/b]", markup=True, font_size=dp(24),
            size_hint_y=None, height=dp(40), color=(0.88, 0.64, 0.22, 1)
        )
        asosiy.add_widget(sarlavha)

        # ---- Qidiruv qatori ----
        qidiruv_qatori = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.savol_input = TextInput(
            hint_text="Nimani bilmoqchisiz?", multiline=False,
            size_hint_x=0.75,
        )
        self.savol_input.bind(on_text_validate=self.izlash)
        self.izlash_tugma = Button(text="Izlash", size_hint_x=0.25)
        self.izlash_tugma.bind(on_release=self.izlash)
        qidiruv_qatori.add_widget(self.savol_input)
        qidiruv_qatori.add_widget(self.izlash_tugma)
        asosiy.add_widget(qidiruv_qatori)

        # ---- Natija ko'rsatish (aylantiriladigan) ----
        self.natija_label = Label(
            text="Savolingizni yozing va 'Izlash' tugmasini bosing.",
            size_hint_y=None, valign="top", halign="left",
            text_size=(None, None),
        )
        self.natija_label.bind(
            width=lambda inst, w: setattr(inst, "text_size", (w, None))
        )
        self.natija_label.bind(
            texture_size=lambda inst, ts: setattr(inst, "height", ts[1])
        )
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self.natija_label)
        asosiy.add_widget(scroll)

        # ---- O'rgatish paneli (ochiladi/yopiladi) ----
        ogret_tugma = Button(
            text="+ Yangi ma'lumot o'rgatish", size_hint_y=None, height=dp(42)
        )
        ogret_tugma.bind(on_release=self.panelni_almashtir)
        asosiy.add_widget(ogret_tugma)

        self.ogret_panel = BoxLayout(
            orientation="vertical", size_hint_y=None, height=0,
            spacing=dp(6), opacity=0,
        )
        self.kalit_input = TextInput(
            hint_text="Kalit so'z (masalan: poytaxt)",
            multiline=False, size_hint_y=None, height=dp(42),
        )
        self.malumot_input = TextInput(
            hint_text="Ma'lumot matni",
            multiline=True, size_hint_y=None, height=dp(80),
        )
        saqlash_tugma = Button(text="Xotiraga saqlash", size_hint_y=None, height=dp(42))
        saqlash_tugma.bind(on_release=self.ogret)

        self.ogret_panel.add_widget(self.kalit_input)
        self.ogret_panel.add_widget(self.malumot_input)
        self.ogret_panel.add_widget(saqlash_tugma)
        asosiy.add_widget(self.ogret_panel)

        # ---- Pastki holat qatori ----
        self.holat_label = Label(
            text=self._holat_matni(), size_hint_y=None, height=dp(22),
            font_size=dp(12), color=(0.7, 0.7, 0.7, 1),
        )
        asosiy.add_widget(self.holat_label)

        return asosiy

    def _xotira_papkasini_aniqla(self):
        """Android qurilmada Android/obb/<paket_nomi>/xotira_data papkasini
        qaytaradi. Agar biror sababdan bu ishlamasa (masalan, kompyuterda
        sinab ko'rilayotgan bo'lsa, yoki Android OBB'ga ruxsat bermasa),
        xavfsiz variant sifatida ilovaning ichki papkasiga qaytadi -
        shunda ilova baribir ISHLASHDAN TO'XTAMAYDI."""
        if platform == "android":
            try:
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                faoliyat = PythonActivity.mActivity
                obb_papka = faoliyat.getObbDir().getAbsolutePath()
                return os.path.join(obb_papka, "xotira_data")
            except Exception as xato:
                print(f"⚠️ OBB papkasiga kira olmadim ({xato}), ichki xotiraga o'tamiz.")
                return os.path.join(self.user_data_dir, "xotira_data")
        else:
            # Android emas (masalan, siz kompyuteringizda sinab ko'ryapsiz)
            return os.path.join(self.user_data_dir, "xotira_data")

    def _holat_matni(self):
        return f"{len(backend.barcha_xotiralar())} ta ma'lumot xotirada"

    # ---- Amallar ----

    def izlash(self, instance):
        # Agar allaqachon qidiruv ketayotgan bo'lsa - yangisini BOSHLAMAYMIZ
        # (aks holda ikkita natija bir-birini "quvib", chalkashlik keltirib chiqaradi)
        if self.izlash_tugma.disabled:
            return

        savol = self.savol_input.text.strip()
        if not savol:
            return

        self.natija_label.text = "🔍 Qidirilmoqda..."
        self.izlash_tugma.disabled = True
        self.izlash_tugma.text = "..."
        threading.Thread(target=self._izlash_fon, args=(savol,), daemon=True).start()

    def _izlash_fon(self, savol):
        javob = backend.javob_ber(savol)
        Clock.schedule_once(lambda dt: self._natijani_yangila(javob))

    def _natijani_yangila(self, javob):
        self.natija_label.text = javob
        self.holat_label.text = self._holat_matni()
        # Qidiruv tugadi - tugmani qayta yoqamiz
        self.izlash_tugma.disabled = False
        self.izlash_tugma.text = "Izlash"

    def panelni_almashtir(self, instance):
        if self.ogret_panel.height == 0:
            self.ogret_panel.height = dp(180)
            self.ogret_panel.opacity = 1
        else:
            self.ogret_panel.height = 0
            self.ogret_panel.opacity = 0

    def ogret(self, instance):
        kalit_soz = self.kalit_input.text.strip()
        malumot = self.malumot_input.text.strip()
        if kalit_soz and malumot:
            backend.yangi_xotira_qoshish(kalit_soz, malumot, manba="foydalanuvchi", ishonch="aniq")
            self.kalit_input.text = ""
            self.malumot_input.text = ""
            self.holat_label.text = self._holat_matni() + " (yangi qo'shildi ✅)"


if __name__ == "__main__":
    XotiraAIApp().run()
