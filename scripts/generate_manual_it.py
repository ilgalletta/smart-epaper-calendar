#!/usr/bin/env python3
"""
Genera il Manuale di Assemblaggio e Configurazione in Italiano (PDF A4)
per Smart E-Paper Calendar 7.5" 3-Colori.
"""

import os
import shutil
from pathlib import Path
from fpdf import FPDF


# Percorsi principali
PROJECT_ROOT = Path("/home/antigravity/smart-epaper-calendar")
BRAIN_DIR = Path(
    "/home/antigravity/.gemini/jetski/brain/v1/default/jetski_remote_agents_3p/"
    "5f82617e-f5dc-440f-87fc-403adb078613"
)

IMG_HARDWARE = BRAIN_DIR / "hardware_stack_diagram_1794936338427.jpg"
IMG_FRAME = BRAIN_DIR / "ikea_frame_mount_1794936336854.jpg"
IMG_PREVIEW = PROJECT_ROOT / "data" / "preview.png"

OUT_REPO = PROJECT_ROOT / "docs" / "manuale_assemblaggio_it.pdf"
OUT_BRAIN = BRAIN_DIR / "manuale_assemblaggio_it.pdf"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

# Palette colori (RGB)
C_RED = (198, 30, 30)
C_BLACK = (26, 29, 33)
C_SLATE = (85, 93, 102)
C_LIGHT_BG = (244, 245, 247)
C_BORDER = (209, 213, 219)
C_WHITE = (255, 255, 255)
C_INFO_BG = (239, 246, 255)
C_INFO_BORDER = (37, 99, 235)
C_WARN_BG = (254, 242, 242)
C_WARN_BORDER = (198, 30, 30)
C_CODE_BG = (30, 34, 40)
C_CODE_FG = (235, 240, 245)


class ManualPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 20, 18)
        self.current_section = "Introduzione"
        self.alias_nb_pages()

        # Caricamento font Unicode DejaVu
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVuMono", "", str(FONT_DIR / "DejaVuSansMono.ttf"))
        self.add_font("DejaVuMono", "B", str(FONT_DIR / "DejaVuSansMono-Bold.ttf"))

    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(10)
        self.set_font("DejaVu", "B", 8.5)
        self.set_text_color(*C_SLATE)
        self.cell(72, 5, 'Smart E-Paper Calendar 7.5" (IT)')
        self.set_font("DejaVu", "", 8.5)
        self.set_text_color(*C_RED)
        self.cell(0, 5, self.current_section, align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(18, 16, 192, 16)
        self.set_y(20)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-13)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(18, self.get_y() - 1.5, 192, self.get_y() - 1.5)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*C_SLATE)
        self.cell(130, 5, "Progetto Open Source  •  github.com/ilgalletta/smart-epaper-calendar")
        self.set_font("DejaVu", "B", 8)
        self.cell(0, 5, f"Pagina {self.page_no()} / {{nb}}", align="R")

    def section_title(self, badge: str, title: str, subtitle: str = ""):
        self.current_section = f"{badge} — {title}" if badge else title
        # Badge rosso
        if badge:
            self.set_fill_color(*C_RED)
            self.set_text_color(*C_WHITE)
            self.set_font("DejaVu", "B", 8.5)
            badge_w = self.get_string_width(badge) + 7
            self.cell(badge_w, 6, badge, fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
        # Titolo sezione
        self.set_text_color(*C_BLACK)
        self.set_font("DejaVu", "B", 16)
        self.multi_cell(0, 7.5, title, new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self.set_font("DejaVu", "", 9.5)
            self.set_text_color(*C_SLATE)
            self.multi_cell(0, 5, subtitle, new_x="LMARGIN", new_y="NEXT")
        # Linea separatrice
        self.ln(1.5)
        self.set_draw_color(*C_RED)
        self.set_line_width(0.6)
        self.line(18, self.get_y(), 52, self.get_y())
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.25)
        self.line(52, self.get_y(), 192, self.get_y())
        self.ln(4.5)

    def subheading(self, text: str):
        self.ln(2)
        self.set_font("DejaVu", "B", 11)
        self.set_text_color(*C_BLACK)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str, space_after: float = 2.5):
        self.set_font("DejaVu", "", 9.5)
        self.set_text_color(*C_BLACK)
        self.multi_cell(0, 5.2, text, new_x="LMARGIN", new_y="NEXT")
        if space_after > 0:
            self.ln(space_after)

    def step_item(self, num: str, title: str, desc: str):
        # Evita di spezzare il titolo dallo step
        if self.get_y() > 258:
            self.add_page()
        start_y = self.get_y()
        # Cerchio/riquadro numero
        self.set_fill_color(*C_RED)
        self.set_text_color(*C_WHITE)
        self.set_font("DejaVu", "B", 9)
        self.cell(7, 6, num, align="C", fill=True)
        self.set_x(27.5)
        self.set_text_color(*C_BLACK)
        self.set_font("DejaVu", "B", 10)
        self.multi_cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(27.5)
        self.set_font("DejaVu", "", 9.2)
        self.set_text_color(*C_SLATE)
        self.multi_cell(164.5, 4.8, desc, new_x="LMARGIN", new_y="NEXT")
        self.ln(2.0)

    def callout(self, title: str, text: str, kind: str = "info"):
        bg = C_INFO_BG if kind == "info" else C_WARN_BG
        border = C_INFO_BORDER if kind == "info" else C_WARN_BORDER
        if self.get_y() > 250:
            self.add_page()
        y0 = self.get_y()
        # Calcola altezza approssimativa con dry run o padding sicuro
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        self.set_x(18)
        self.set_font("DejaVu", "B", 9.5)
        # Misuriamo righe
        lines_t = self.multi_cell(166, 5, title, dry_run=True, output="LINES")
        self.set_font("DejaVu", "", 9)
        lines_b = self.multi_cell(166, 4.8, text, dry_run=True, output="LINES")
        box_h = 4 + len(lines_t) * 5 + 1 + len(lines_b) * 4.8 + 3.5

        self.rect(18, y0, 174, box_h, style="F")
        self.set_fill_color(*border)
        self.rect(18, y0, 1.8, box_h, style="F")

        self.set_xy(23, y0 + 2.5)
        self.set_text_color(*border)
        self.set_font("DejaVu", "B", 9.5)
        self.multi_cell(165, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(23)
        self.set_text_color(*C_BLACK)
        self.set_font("DejaVu", "", 9)
        self.multi_cell(165, 4.8, text, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + box_h + 3.5)

    def code_block(self, code: str):
        lines = code.strip().split("\n")
        box_h = len(lines) * 5.0 + 5.0
        if self.get_y() + box_h > 275:
            self.add_page()
        y0 = self.get_y()
        self.set_fill_color(*C_CODE_BG)
        self.rect(18, y0, 174, box_h, style="F")
        self.set_xy(22, y0 + 2.5)
        self.set_font("DejaVuMono", "", 8.8)
        self.set_text_color(*C_CODE_FG)
        for line in lines:
            self.set_x(22)
            self.cell(166, 5.0, line, new_x="LMARGIN", new_y="NEXT")
        self.set_y(y0 + box_h + 3.5)

    def embed_figure(self, img_path: Path, caption: str, max_w: float = 166, max_h: float = 95):
        from PIL import Image

        with Image.open(img_path) as im:
            px_w, px_h = im.size
        ratio = px_w / px_h
        w = max_w
        h = w / ratio
        if h > max_h:
            h = max_h
            w = h * ratio

        if self.get_y() + h + 12 > 277:
            self.add_page()

        x = 18 + (174 - w) / 2
        y = self.get_y()
        # Cornice leggera intorno all'immagine
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.rect(x - 1, y - 1, w + 2, h + 2)
        self.image(str(img_path), x=x, y=y, w=w, h=h)
        self.set_y(y + h + 2.5)
        self.set_font("DejaVu", "", 8.2)
        self.set_text_color(*C_SLATE)
        self.multi_cell(0, 4.2, caption, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)


def build_manual():
    pdf = ManualPDF()

    # =========================================================================
    # PAGINA 1: COPERTINA & INTRODUZIONE
    # =========================================================================
    pdf.add_page()

    # Barra superiore decorativa
    pdf.set_fill_color(*C_RED)
    pdf.rect(0, 0, 210, 6, style="F")

    pdf.set_y(16)
    pdf.set_fill_color(*C_BLACK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("DejaVu", "B", 8.5)
    badge_txt = "  MANUALE DI ASSEMBLAGGIO & SETUP  •  EDIZIONE PLUG-AND-PLAY  "
    pdf.cell(pdf.get_string_width(badge_txt) + 4, 6.5, badge_txt, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)
    pdf.set_text_color(*C_BLACK)
    pdf.set_font("DejaVu", "B", 25)
    pdf.multi_cell(0, 10.5, "Smart E-Paper Calendar", new_x="LMARGIN", new_y="NEXT")

    pdf.set_text_color(*C_RED)
    pdf.set_font("DejaVu", "B", 13)
    pdf.multi_cell(
        0,
        6.5,
        'Calendario da Parete Open-Source 7.5" a 3 Colori (Nero / Bianco / Rosso)',
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(2)
    pdf.set_text_color(*C_SLATE)
    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(
        0,
        5.5,
        "Guida passo-passo per principianti: zero saldature, montaggio nella cornice IKEA SANNAHED "
        "e configurazione completa via browser locale e Telegram.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(4)
    # Anteprima Hero del calendario
    pdf.embed_figure(
        IMG_PREVIEW,
        "Anteprima reale dell'interfaccia a 3 colori (800×480 px) sul display e-Paper da 7.5 pollici.",
        max_w=154,
        max_h=84,
    )

    # Box specifiche rapide (4 colonne)
    specs = [
        ("DISPLAY", '7.5" 800×480\n3 Colori (B/W/R)'),
        ("ASSEMBLAGGIO", "Plug-and-Play\nZero Saldature"),
        ("AUTONOMIA", "Settimane a batteria\ncon Witty Pi 4 Mini"),
        ("CONFIGURAZIONE", "Web UI Locale (LAN)\n+ Bot Telegram"),
    ]
    y_spec = pdf.get_y()
    col_w = 42
    gap = 2
    for idx, (k, v) in enumerate(specs):
        x_box = 18 + idx * (col_w + gap)
        pdf.set_fill_color(*C_LIGHT_BG)
        pdf.set_draw_color(*C_BORDER)
        pdf.rect(x_box, y_spec, col_w, 18, style="FD")
        pdf.set_xy(x_box + 2.5, y_spec + 2.5)
        pdf.set_font("DejaVu", "B", 7.5)
        pdf.set_text_color(*C_RED)
        pdf.cell(col_w - 5, 4, k, new_x="LMARGIN", new_y="NEXT")
        pdf.set_xy(x_box + 2.5, y_spec + 7)
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*C_BLACK)
        pdf.multi_cell(col_w - 5, 4.2, v)

    pdf.set_y(y_spec + 23)

    # Introduzione
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(0, 6, "Introduzione al Progetto", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)
    pdf.body_text(
        "Lo Smart E-Paper Calendar è una bacheca digitale da parete progettata per offrire tutte le informazioni "
        "essenziali della giornata a colpo d'occhio, con l'aspetto elegante della carta stampata e senza retroilluminazione "
        "fastidiosa. Grazie alla tecnologia E-Ink a 3 colori (Nero, Bianco e Rosso), l'immagine rimane nitida anche a "
        "dispositivo completamente spento.",
        space_after=2.5,
    )
    pdf.body_text(
        "Il sistema integra automaticamente i tuoi calendari iCal (.ics), le previsioni meteo locali (Open-Meteo), "
        "i tempi di percorrenza casa-ufficio, il menu giornaliero della mensa scolastica (es. Milano Ristorazione / "
        "I.C. Gattamelata), le ultime notizie RSS e una Lista della Spesa condivisa aggiornabile istantaneamente "
        "tramite un Bot Telegram. Ogni componente è pensato per essere assemblato senza saldatore e gestito comodamente "
        "dal telefono tramite l'interfaccia web locale.",
        space_after=2,
    )

    pdf.set_auto_page_break(auto=False)
    pdf.set_y(278)
    pdf.set_font("DejaVu", "", 8)
    pdf.set_text_color(*C_SLATE)
    pdf.cell(
        0,
        5,
        "Repository ufficiale: https://github.com/ilgalletta/smart-epaper-calendar  •  Licenza Open Source MIT",
        align="C",
    )
    pdf.set_auto_page_break(auto=True, margin=18)

    # =========================================================================
    # PAGINA 2: LISTA DELLA SPESA (BOM PLUG-AND-PLAY)
    # =========================================================================
    pdf.current_section = "BOM — Lista della Spesa"
    pdf.add_page()
    pdf.section_title(
        "BOM",
        "Lista della Spesa (Plug-and-Play)",
        "Tutti i componenti necessari per costruire il calendario senza alcuna saldatura.",
    )
    pdf.current_section = "BOM — Lista della Spesa"

    pdf.body_text(
        "Prima di iniziare, verifica di avere tutti i componenti elencati nella tabella seguente. "
        "La configurazione è studiata per garantire il montaggio meccanico ed elettrico ad incastro, "
        "senza dover usare il saldatore a stagno."
    )

    # Tabella BOM
    bom_rows = [
        (
            "Display E-Paper 7.5\"",
            "Waveshare 7.5\" e-Paper HAT (B)",
            "Risoluzione 800×480, 3 colori (B/W/R). Include il pannello raw, il Driver HAT e il cavo flat FPC.",
        ),
        (
            "Mini Computer",
            "Raspberry Pi Zero 2 WH",
            "Versione \"WH\" con Wi-Fi integrato e connettore GPIO a 40 pin già saldato in fabbrica.",
        ),
        (
            "Gestione Energia & RTC",
            "UUGear Witty Pi 4 Mini",
            "Scheda RTC per sveglia programmata e taglio totale dell'alimentazione tra un refresh e l'altro.",
        ),
        (
            "Batteria",
            "Li-Po 3.7V o Power Bank USB-C",
            "Batteria Li-Po (2500–4000 mAh, connettore JST-PH) oppure Power Bank USB-C compatto senza auto-spegnimento.",
        ),
        (
            "Scheda di Memoria",
            "microSD 32 GB (Classe 10 / A1)",
            "Es. SanDisk Ultra o Samsung EVO. Ospita Raspberry Pi OS Lite e il software del calendario.",
        ),
        (
            "Cornice da Parete",
            "IKEA SANNAHED 21×30 cm",
            "Cornice profonda con distanziatore interno e passe-partout, ideale per nascondere l'elettronica.",
        ),
        (
            "Cavi & Fissaggio",
            "Cavo USB-C corto + Nastro",
            "Cavo corto USB-C / micro-USB per ricarica, nastro carta o biadesivo leggero, taglierino per passe-partout.",
        ),
    ]

    col_widths = [40, 52, 82]
    headers = ["Componente", "Modello Consigliato", "Funzione & Note"]

    pdf.set_fill_color(*C_BLACK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("DejaVu", "B", 9)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=0, fill=True)
    pdf.ln()

    for idx, (comp, model, note) in enumerate(bom_rows):
        bg = C_LIGHT_BG if idx % 2 == 1 else C_WHITE
        pdf.set_font("DejaVu", "", 8.6)
        # Calcola altezza riga
        l1 = len(pdf.multi_cell(col_widths[0] - 3, 4.6, comp, dry_run=True, output="LINES"))
        l2 = len(pdf.multi_cell(col_widths[1] - 3, 4.6, model, dry_run=True, output="LINES"))
        l3 = len(pdf.multi_cell(col_widths[2] - 3, 4.6, note, dry_run=True, output="LINES"))
        row_h = max(l1, l2, l3) * 4.6 + 4.5

        y_row = pdf.get_y()
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_BORDER)
        pdf.rect(18, y_row, sum(col_widths), row_h, style="F")
        pdf.line(18, y_row + row_h, 192, y_row + row_h)

        # Col 1
        pdf.set_xy(19.5, y_row + 2.2)
        pdf.set_font("DejaVu", "B", 8.6)
        pdf.set_text_color(*C_BLACK)
        pdf.multi_cell(col_widths[0] - 3, 4.6, comp)

        # Col 2
        pdf.set_xy(18 + col_widths[0] + 1.5, y_row + 2.2)
        pdf.set_font("DejaVu", "B", 8.5)
        pdf.set_text_color(*C_RED)
        pdf.multi_cell(col_widths[1] - 3, 4.6, model)

        # Col 3
        pdf.set_xy(18 + col_widths[0] + col_widths[1] + 1.5, y_row + 2.2)
        pdf.set_font("DejaVu", "", 8.5)
        pdf.set_text_color(*C_SLATE)
        pdf.multi_cell(col_widths[2] - 3, 4.6, note)

        pdf.set_y(y_row + row_h)

    pdf.ln(5)
    pdf.callout(
        "Perché scegliere il Raspberry Pi Zero 2 WH?",
        'La sigla "WH" indica Wireless + Header pre-saldato. Acquistando la versione WH avrai già i 40 pin GPIO '
        "pronti per innestare il Witty Pi 4 Mini e il Driver HAT Waveshare senza dover effettuare alcuna saldatura.",
        kind="info",
    )

    pdf.callout(
        "Nota sulla scelta della batteria",
        "Se usi un Power Bank USB-C comune, verifica che non si spenga automaticamente con assorbimenti bassi "
        "(oppure usa la porta di ricarica/alimentazione dedicata del Witty Pi 4 Mini con una batteria Li-Po 3.7V "
        "dotata di circuito di protezione PCM).",
        kind="warn",
    )

    # =========================================================================
    # PAGINA 3: FASE 1 — PREPARAZIONE MICROSD & SOFTWARE
    # =========================================================================
    pdf.current_section = "Fase 1 — microSD & Software"
    pdf.add_page()
    pdf.section_title(
        "FASE 1",
        "Preparazione della microSD & Software",
        "Installazione di Raspberry Pi OS Lite (64-bit) e configurazione automatica tramite script.",
    )
    pdf.current_section = "Fase 1 — microSD & Software"

    pdf.body_text(
        "Puoi preparare la scheda microSD direttamente dal tuo computer (Windows, macOS o Linux) in meno di 10 minuti, "
        "preconfigurando Wi-Fi e accesso remoto SSH così da non dover collegare né monitor né tastiera al Raspberry Pi."
    )

    pdf.step_item(
        "1",
        "Scarica e avvia Raspberry Pi Imager",
        "Scarica il programma gratuito Raspberry Pi Imager dal sito ufficiale (raspberrypi.com/software) e inserisci "
        "la microSD da 32 GB nel lettore del tuo computer.",
    )
    pdf.step_item(
        "2",
        "Seleziona Dispositivo, Sistema Operativo e Memoria",
        '• Dispositivo Raspberry Pi: seleziona "Raspberry Pi Zero 2 W".\n'
        '• Sistema Operativo: scegli "Raspberry Pi OS (other)" → "Raspberry Pi OS Lite (64-bit)" (versione leggera senza desktop).\n'
        "• Archiviazione: seleziona la tua microSD da 32 GB.",
    )
    pdf.step_item(
        "3",
        "Preconfigura Wi-Fi e SSH (Modifica Impostazioni)",
        'Prima di avviare la scrittura, clicca su "Avanti" e poi su "Modifica Impostazioni" (OS Customisation):\n'
        "• Generale: imposta hostname (es. epaper-calendar), nome utente (es. pi) e password.\n"
        "• Rete Wi-Fi: inserisci nome rete (SSID), password del Wi-Fi di casa e Paese wireless IT.\n"
        "• Servizi: attiva la spunta su Abilita SSH usando l'autenticazione con password.",
    )
    pdf.step_item(
        "4",
        "Scrivi la microSD e avvia il Raspberry Pi",
        "Conferma la scrittura e attendi il completamento della verifica. Inserisci la microSD nel Raspberry Pi Zero 2 WH "
        "(puoi alimentarlo temporaneamente via USB per eseguire il setup software prima di chiuderlo nella cornice, "
        "oppure dopo aver completato la Fase 2). Attendi circa 60–90 secondi per il primo avvio.",
    )
    pdf.step_item(
        "5",
        "Collegati via SSH e lancia lo script di installazione",
        "Apri il Terminale (su Windows PowerShell o Prompt dei Comandi, su Mac/Linux Terminale) e collegati al Pi "
        "con: ssh pi@epaper-calendar.local. Poi esegui i seguenti comandi in sequenza:",
    )

    pdf.code_block(
        "git clone https://github.com/ilgalletta/smart-epaper-calendar.git\n"
        "cd smart-epaper-calendar\n"
        "sudo bash scripts/setup_pi.sh"
    )

    pdf.callout(
        "Cosa fa automaticamente lo script setup_pi.sh?",
        "Lo script è idempotente e sicurissimo: abilita le interfacce hardware SPI e I2C, installa i pacchetti di sistema, "
        "crea l'ambiente Python (.venv), scarica la libreria ufficiale Waveshare (epd7in5b_V2), crea il file config.yaml "
        "di partenza e registra i servizi systemd (smart-calendar-web.service sulla porta 8080 e smart-calendar-sync.service). "
        "Al termine, esegui un riavvio con: sudo reboot",
        kind="info",
    )

    # =========================================================================
    # PAGINA 4: FASE 2 — ASSEMBLAGGIO ELETTRONICO (SENZA SALDATURE)
    # =========================================================================
    pdf.current_section = "Fase 2 — Assemblaggio Elettronico"
    pdf.add_page()
    pdf.section_title(
        "FASE 2",
        "Assemblaggio Elettronico (Senza Saldature)",
        "Collegamento a sandwich delle schede e connessione del pannello e-Paper 7.5\".",
    )
    pdf.current_section = "Fase 2 — Assemblaggio Elettronico"

    pdf.embed_figure(
        IMG_HARDWARE,
        "Schema di impilamento hardware: Raspberry Pi Zero 2 WH → Witty Pi 4 Mini → Waveshare Driver HAT → Display 7.5\".",
        max_w=145,
        max_h=64,
    )

    pdf.step_item(
        "1",
        "Inserisci la microSD nel Raspberry Pi Zero 2 WH",
        "Con il Raspberry Pi scollegato da qualsiasi alimentazione, inserisci la scheda microSD preparata nella Fase 1 "
        "nello slot metallico sul lato sinistro della scheda finché non è ben inserita.",
    )
    pdf.step_item(
        "2",
        "Allinea e premi il Witty Pi 4 Mini sui 40 pin GPIO",
        "Prendi il Witty Pi 4 Mini e allinea con molta attenzione il connettore femmina nero a 40 pin con i 40 pin GPIO "
        "maschi del Raspberry Pi Zero 2 WH (assicurati che nessun pin resti fuori dai bordi). Premi delicatamente "
        "in modo uniforme fino a completo innesto.",
    )
    pdf.step_item(
        "3",
        "Monta il Waveshare e-Paper Driver HAT",
        "Allinea il connettore GPIO del Waveshare e-Paper Driver HAT sopra i pin passanti superiori del Witty Pi 4 Mini "
        "e premi delicatamente fino a battuta. In alternativa, se preferisci ridurre lo spessore totale dentro la cornice, "
        "puoi collegare il Driver HAT al Witty Pi tramite cavetti jumper femmina-femmina o pogo pin.",
    )
    pdf.step_item(
        "4",
        "Inserisci il cavo flat arancione (FPC) nel connettore ZIF",
        "Sul Waveshare Driver HAT individua il connettore ZIF bianco/nero per il cavo piatto. Solleva con delicatezza la "
        "linguetta di blocco (circa 90°), inserisci fino in fondo il cavo flat arancione del display 7.5\" facendo "
        "molta attenzione al verso dei contatti metallici (i contatti dorati devono appoggiare sui pin interni del "
        "connettore, generalmente rivolti verso il basso/la scheda PCB), poi richiudi la linguetta finché non scatta.",
    )
    pdf.step_item(
        "5",
        "Collega la batteria al Witty Pi 4 Mini",
        "Collega il connettore bianco JST della batteria Li-Po all'apposita presa sul Witty Pi 4 Mini, oppure collega "
        "il Power Bank USB-C tramite cavo corto alla porta di ingresso alimentazione del Witty Pi 4 Mini.",
    )

    pdf.callout(
        "Attenzione al pannello e al cavo flat (FPC)",
        "Il display e-Paper da 7.5\" è realizzato su un substrato in vetro molto sottile: maneggialo sempre dai bordi "
        "senza torcerlo e non piegare mai ad angolo retto il cavo flat arancione.",
        kind="warn",
    )

    # =========================================================================
    # PAGINA 5: FASE 3 — MONTAGGIO NELLA CORNICE IKEA SANNAHED
    # =========================================================================
    pdf.current_section = "Fase 3 — Cornice IKEA SANNAHED"
    pdf.add_page()
    pdf.section_title(
        "FASE 3",
        "Montaggio nella Cornice IKEA SANNAHED (21×30 cm)",
        "Integrazione pulita di display, schede e batteria all'interno della cornice.",
    )
    pdf.current_section = "Fase 3 — Cornice IKEA SANNAHED"

    pdf.embed_figure(
        IMG_FRAME,
        "Vista esplosa del montaggio nella cornice IKEA SANNAHED 21×30 cm con passe-partout, elettronica e pannello MDF.",
        max_w=168,
        max_h=88,
    )

    pdf.step_item(
        "1",
        "Apertura della cornice e pulizia del vetro",
        "Appoggia la cornice IKEA SANNAHED (21×30 cm) a faccia in giù su un panno morbido. Ruota le linguette metalliche "
        "posteriori e rimuovi il pannello MDF di chiusura, il distanziatore interno nero e il passe-partout bianco. "
        "Pulisci accuratamente la superficie interna del vetro con un panno in microfibra.",
    )
    pdf.step_item(
        "2",
        "Adattamento del passe-partout (ritaglio 163 × 98 mm)",
        "Verifica l'apertura del passe-partout in cartoncino: l'area attiva visibile del display Waveshare 7.5\" misura "
        "esattamente 163 × 98 mm. Se necessario, traccia un rettangolo centrato di 163 × 98 mm con matita e righello "
        "e rifila il cartoncino con un taglierino affilato su un piano da taglio.",
    )
    pdf.step_item(
        "3",
        "Fissaggio del pannello e-Paper dietro al passe-partout",
        "Posiziona il passe-partout sopra il vetro dentro la cornice. Appoggia il pannello e-Paper 7.5\" centrato nella "
        "finestra (schermo rivolto verso il vetro). Fissa i quattro bordi posteriori del pannello al retro del passe-partout "
        "con strisce di nastro carta o nastro biadesivo leggero, lasciando libero il cavo flat arancione.",
    )
    pdf.step_item(
        "4",
        "Fissaggio di Pi + Witty Pi + Batteria nella cavità posteriore",
        "Inserisci il distanziatore nero della cornice SANNAHED: crea una cavità profonda circa 2 cm dietro il display. "
        "Fissa il blocco Raspberry Pi + Witty Pi + Driver HAT e la batteria (o Power Bank piatto) sul retro del "
        "passe-partout o su un cartoncino di supporto usando nastro biadesivo resistente o velcro adesivo.",
    )
    pdf.step_item(
        "5",
        "Chiusura del pannello MDF e accesso a pulsante & USB-C",
        "Richiudi il pannello posteriore in MDF ruotando le linguette metalliche. Prima di chiudere definitivamente, "
        "assicurati di aver lasciato accessibile (tramite un piccolo intaglio sul bordo inferiore del pannello MDF o "
        "posizionando i componenti vicino al bordo) il pulsante di risveglio del Witty Pi 4 Mini e la porta USB-C di ricarica.",
    )

    # =========================================================================
    # PAGINA 6: FASE 4 — CONFIGURAZIONE REMOTA VIA LAN WEB UI & TELEGRAM
    # =========================================================================
    pdf.current_section = "Fase 4 — Web UI LAN & Telegram"
    pdf.add_page()
    pdf.section_title(
        "FASE 4",
        "Configurazione Remota via LAN Web UI & Telegram",
        "Personalizzazione di calendari, indirizzi, mensa scolastica e lista della spesa dal browser.",
    )
    pdf.current_section = "Fase 4 — Web UI LAN & Telegram"

    pdf.embed_figure(
        IMG_PREVIEW,
        "Risultato finale sul display dopo la configurazione: calendario settimanale, mensa, meteo, lista spesa e notizie.",
        max_w=148,
        max_h=78,
    )

    pdf.step_item(
        "1",
        "Accedi al portale Web locale (porta 8080)",
        "Assicurati che il Raspberry Pi sia acceso e connesso al Wi-Fi. Da smartphone, tablet o PC sulla stessa rete "
        "locale, apri il browser e vai all'indirizzo:\n"
        "http://<ip-del-pi>:8080   (oppure http://epaper-calendar.local:8080)",
    )
    pdf.step_item(
        "2",
        "Effettua il login e cambia la password iniziale",
        'Inserisci la password predefinita "changeme". Per sicurezza, cambia subito la password modificando il campo '
        "web_ui.password nel file config.yaml (o direttamente dalle impostazioni) prima di lasciare il calendario attivo.",
    )
    pdf.step_item(
        "3",
        "Imposta Indirizzi Casa / Ufficio e Meteo",
        "Inserisci l'indirizzo di Casa e quello dell'Ufficio (usati per calcolare il tempo di percorrenza mattutino) "
        "e verifica la località e le coordinate per le previsioni meteo Open-Meteo (es. Milano — nessuna API key richiesta).",
    )
    pdf.step_item(
        "4",
        "Collega i tuoi calendari iCal (.ics)",
        "Nella sezione Calendari aggiungi uno o più link .ics (es. Google Calendar → Impostazioni calendario → "
        '"Indirizzo segreto in formato iCal"). Imposta highlight: true sui calendari principali per evidenziarli in rosso.',
    )
    pdf.step_item(
        "5",
        "Configura la Mensa Scolastica (Gattamelata / Milano Ristorazione)",
        'Attiva milanoristorazione.enabled: true e imposta la ricerca scuola su "Gattamelata" (o la tua scuola di '
        "Milano Ristorazione). Il sistema scarica in automatico il menu del giorno (o del giorno successivo la sera), "
        "con menu settimanale di fallback offline in caso di assenza di rete.",
    )
    pdf.step_item(
        "6",
        "Collega il Bot Telegram per la Lista della Spesa",
        "Su Telegram cerca @BotFather, crea un nuovo bot con /newbot e copia il Token ricevuto nella sezione Telegram "
        "della Web UI insieme al tuo chat_id (puoi ottenerlo scrivendo a @userinfobot). Ogni articolo inviato al bot "
        "comparirà automaticamente nella sezione Lista della Spesa del calendario!",
    )

    # =========================================================================
    # PAGINA 7: MANUTENZIONE, RICARICA & RISOLUZIONE PROBLEMI
    # =========================================================================
    pdf.current_section = "Manutenzione & Ricarica"
    pdf.add_page()
    pdf.section_title(
        "MANUTENZIONE",
        "Ricarica & Funzionamento Witty Pi 4 Mini",
        "Come funziona il risparmio energetico estremo, come ricaricare la batteria e risolvere eventuali imprevisti.",
    )
    pdf.current_section = "Manutenzione & Ricarica"

    pdf.subheading("Come funziona la sveglia programmata (Witty Pi 4 Mini)")
    pdf.body_text(
        "A differenza di un tablet tradizionale, uno schermo e-Paper consuma energia esclusivamente durante i 15–20 secondi "
        "in cui cambia immagine; una volta disegnato il calendario, l'immagine resta visibile a consumo zero. "
        "Il Witty Pi 4 Mini sfrutta questo principio grazie al suo orologio RTC (Real-Time Clock) integrato:"
    )

    pdf.step_item(
        "A",
        "Ciclo automatico di risveglio e spegnimento",
        "All'orario programmato (secondo le fasce Mattina 06:30–12:00, Pomeriggio 12:00–18:00 e Sera 18:00–23:00), "
        "il Witty Pi 4 Mini fornisce corrente al Raspberry Pi. Il servizio smart-calendar-sync.service scarica meteo, "
        "eventi, mensa e lista della spesa, aggiorna il display e dopo circa 120 secondi il Witty Pi toglie nuovamente "
        "corrente portando il consumo quasi a zero.",
    )
    pdf.step_item(
        "B",
        "Risveglio manuale per configurazione (Pulsante fisico)",
        "Quando il Raspberry Pi è spento in attesa del prossimo aggiornamento, la Web UI (porta 8080) non è raggiungibile. "
        "Per accedere alle impostazioni in qualsiasi momento, premi il pulsante fisico sul Witty Pi 4 Mini: il Pi si "
        "accenderà entrando in modalità manutenzione per circa 15 minuti (maintenance_timeout_minutes: 15).",
    )

    pdf.subheading("Come ricaricare la batteria")
    pdf.body_text(
        "Quando la batteria è scarica (indicata dall'icona batteria in alto a destra sul display), collega un normale "
        "alimentatore da smartphone USB-C (5V / 2A) alla porta di ricarica lasciata accessibile sul retro della cornice. "
        "Non è necessario smontare la cornice né spegnere il dispositivo: una carica completa con batteria Li-Po da "
        "3000–4000 mAh garantisce diverse settimane di funzionamento continuo."
    )

    pdf.subheading("Risoluzione rapida dei problemi (Troubleshooting)")

    trouble_rows = [
        (
            "Lo schermo resta bianco o non si aggiorna",
            "Cavo flat FPC inserito al contrario nel connettore ZIF, oppure interfaccia SPI non abilitata.",
            "Scollega la batteria, verifica che i contatti dorati del cavo FPC tocchino i pin del Driver HAT e controlla raspi-config (SPI attivo).",
        ),
        (
            "Web UI (:8080) non raggiungibile dal browser",
            "Il Raspberry Pi è spento dal Witty Pi 4 Mini tra un ciclo e l'altro (normale funzionamento a batteria).",
            "Premi il pulsante di risveglio sul Witty Pi 4 Mini, attendi 40 secondi che si connetta al Wi-Fi e ricarica la pagina.",
        ),
        (
            "Errori di sincronizzazione o meteo vuoto",
            "Wi-Fi assente al risveglio o URL iCal (.ics) non valido.",
            "Verifica la copertura Wi-Fi nella stanza e testa un ciclo manuale via SSH: .venv/bin/python -m src.main --sync-once",
        ),
    ]

    t_widths = [50, 56, 68]
    t_headers = ["Sintomo", "Causa Probabile", "Soluzione"]
    pdf.set_fill_color(*C_BLACK)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("DejaVu", "B", 8.8)
    for w, h in zip(t_widths, t_headers):
        pdf.cell(w, 7.5, h, fill=True)
    pdf.ln()

    for idx, (s, c, sol) in enumerate(trouble_rows):
        bg = C_LIGHT_BG if idx % 2 == 1 else C_WHITE
        pdf.set_font("DejaVu", "", 8.3)
        l1 = len(pdf.multi_cell(t_widths[0] - 3, 4.5, s, dry_run=True, output="LINES"))
        l2 = len(pdf.multi_cell(t_widths[1] - 3, 4.5, c, dry_run=True, output="LINES"))
        l3 = len(pdf.multi_cell(t_widths[2] - 3, 4.5, sol, dry_run=True, output="LINES"))
        row_h = max(l1, l2, l3) * 4.5 + 4

        y_row = pdf.get_y()
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_BORDER)
        pdf.rect(18, y_row, sum(t_widths), row_h, style="F")
        pdf.line(18, y_row + row_h, 192, y_row + row_h)

        pdf.set_xy(19.5, y_row + 2)
        pdf.set_font("DejaVu", "B", 8.3)
        pdf.set_text_color(*C_RED)
        pdf.multi_cell(t_widths[0] - 3, 4.5, s)

        pdf.set_xy(18 + t_widths[0] + 1.5, y_row + 2)
        pdf.set_font("DejaVu", "", 8.3)
        pdf.set_text_color(*C_BLACK)
        pdf.multi_cell(t_widths[1] - 3, 4.5, c)

        pdf.set_xy(18 + t_widths[0] + t_widths[1] + 1.5, y_row + 2)
        pdf.set_font("DejaVu", "", 8.3)
        pdf.set_text_color(*C_SLATE)
        pdf.multi_cell(t_widths[2] - 3, 4.5, sol)

        pdf.set_y(y_row + row_h)

    # Salvataggio su entrambi i percorsi richiesti
    OUT_REPO.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT_REPO))
    shutil.copyfile(OUT_REPO, OUT_BRAIN)

    print(f"PDF generato con successo:")
    print(f"  1) {OUT_REPO} ({OUT_REPO.stat().st_size} bytes)")
    print(f"  2) {OUT_BRAIN} ({OUT_BRAIN.stat().st_size} bytes)")


if __name__ == "__main__":
    build_manual()
