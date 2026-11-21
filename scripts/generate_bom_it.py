#!/usr/bin/env python3
"""
Genera la Lista della Spesa Completa (BOM) & Link ai Negozi in Italiano (PDF A4)
per Smart E-Paper Calendar 7.5" 3-Colori (Configurazione Plug-and-Play HAT),
aggiornata con disponibilità reale verificata, alternative in stock e offerte Black Friday 2026.
"""

from pathlib import Path
from fpdf import FPDF


# Percorsi principali (dinamici rispetto alla posizione dello script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_REPO = PROJECT_ROOT / "docs" / "lista_spesa_bom_it.pdf"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")

# Palette colori (RGB) - coerente con manuale_assemblaggio_it.pdf
C_RED = (198, 30, 30)
C_BLACK = (26, 29, 33)
C_SLATE = (85, 93, 102)
C_LIGHT_BG = (244, 245, 247)
C_ALT_ROW = (249, 250, 251)
C_BORDER = (209, 213, 219)
C_WHITE = (255, 255, 255)
C_INFO_BG = (239, 246, 255)
C_INFO_BORDER = (37, 99, 235)
C_WARN_BG = (254, 242, 242)
C_WARN_BORDER = (198, 30, 30)
C_SUCCESS_BG = (236, 253, 245)
C_SUCCESS_BORDER = (5, 150, 105)
C_BF_BG = (255, 247, 237)
C_BF_BORDER = (217, 119, 6)
C_LINK = (29, 78, 216)


class BomPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(15, 18, 15)
        self.alias_nb_pages()

        # Caricamento font Unicode DejaVu
        self.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVuMono", "", str(FONT_DIR / "DejaVuSansMono.ttf"))
        self.add_font("DejaVuMono", "B", str(FONT_DIR / "DejaVuSansMono-Bold.ttf"))

    def header(self):
        if self.page_no() == 1:
            return
        self.set_y(9)
        self.set_font("DejaVu", "B", 8)
        self.set_text_color(*C_SLATE)
        self.cell(105, 5, 'Smart E-Paper Calendar 7.5"  •  Lista della Spesa (BOM) Aggiornata')
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*C_RED)
        self.cell(0, 5, "Stock Verificato Nov 2026 + Black Friday", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(15, 14.5, 195, 14.5)
        self.set_y(18)

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.3)
        self.line(15, self.get_y() - 1.5, 195, self.get_y() - 1.5)
        self.set_font("DejaVu", "", 7.5)
        self.set_text_color(*C_SLATE)
        self.cell(145, 5, "Smart E-Paper Calendar  •  BOM Verificata il 21 Nov 2026 (Alternative In Stock + Black Friday)")
        self.set_font("DejaVu", "B", 7.5)
        self.cell(0, 5, f"Pagina {self.page_no()} / {{nb}}", align="R")

    def section_heading(self, badge: str, title: str, badge_color=None):
        self.ln(2)
        b_col = badge_color or C_RED
        if badge:
            self.set_fill_color(*b_col)
            self.set_text_color(*C_WHITE)
            self.set_font("DejaVu", "B", 8)
            bw = self.get_string_width(badge) + 6
            self.cell(bw, 5.5, badge, fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(1.5)
        self.set_text_color(*C_BLACK)
        self.set_font("DejaVu", "B", 12.5)
        self.cell(0, 6.5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*b_col)
        self.set_line_width(0.6)
        self.line(15, self.get_y() + 0.5, 48, self.get_y() + 0.5)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.25)
        self.line(48, self.get_y() + 0.5, 195, self.get_y() + 0.5)
        self.ln(3.5)

    def callout_box(self, title: str, body: str, bg_color, border_color):
        self.set_font("DejaVu", "", 8.2)
        lines = self.multi_cell(172, 4.1, body, dry_run=True, output="LINES")
        box_h = 8 + len(lines) * 4.1 + 3
        if self.get_y() + box_h > self.page_break_trigger:
            self.add_page()

        x0 = 15
        y0 = self.get_y()
        self.set_fill_color(*bg_color)
        self.rect(x0, y0, 180, box_h, style="F")
        self.set_fill_color(*border_color)
        self.rect(x0, y0, 1.5, box_h, style="F")

        self.set_xy(x0 + 4.5, y0 + 2.5)
        self.set_font("DejaVu", "B", 8.8)
        self.set_text_color(*border_color)
        self.cell(170, 4.5, title, new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 4.5)
        self.set_font("DejaVu", "", 8.2)
        self.set_text_color(*C_BLACK)
        self.multi_cell(172, 4.1, body, align="L")
        self.set_y(y0 + box_h + 2.5)


def draw_header_banner(pdf: BomPDF):
    """Intestazione principale della pagina 1."""
    x0, y0 = 15, 14
    w = 180

    # Barra superiore rossa
    pdf.set_fill_color(*C_RED)
    pdf.rect(x0, y0, w, 2.2, style="F")

    # Box intestazione
    pdf.set_fill_color(*C_LIGHT_BG)
    pdf.rect(x0, y0 + 2.2, w, 35.5, style="F")
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.3)
    pdf.rect(x0, y0 + 2.2, w, 35.5, style="D")

    pdf.set_xy(x0 + 5, y0 + 5)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*C_RED)
    pdf.cell(0, 4.5, "LISTA DELLA SPESA REALISTICA (BOM)  •  VERIFICATA IL 21 NOVEMBRE 2026", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(0, 7.5, 'Smart E-Paper Calendar 7.5" (B/W/R, 800×480)', new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "B", 9.5)
    pdf.set_text_color(*C_SLATE)
    pdf.cell(0, 5.5, "Configurazione Plug-and-Play (Zero Saldature) + Alternative In Stock + Black Friday", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "", 8.2)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(
        0,
        5,
        "Include correzione Witty Pi 4 L3V7 (Li-Po), sostituzione IKEA RÖDALM 21×30 e offerte Black Friday attive.",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_y(y0 + 41.5)


def draw_bom_table(pdf: BomPDF):
    """Tabella completa BOM Plug-and-Play con disponibilità verificata e alternative reali."""
    pdf.section_heading("SEZIONE 1", "Tabella BOM Realistica — Componenti In Stock & Alternative Verificate")

    pdf.set_font("DejaVu", "", 8.3)
    pdf.set_text_color(*C_SLATE)
    pdf.multi_cell(
        0,
        4.1,
        "Molti componenti della vecchia BOM (Pi Zero 2 WH su BerryBase/Melopero, Waveshare HAT (B) su Kiwi Electronics, "
        "IKEA SANNAHED 21×30) risultano esauriti o fuori catalogo. Qui sotto trovi solo fonti verificate IN STOCK al "
        "21/11/2026 e alternative plug-and-play pronte all'acquisto.",
        align="L",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

    # Definizione colonne (totale = 180 mm)
    col_w = [30, 62, 66, 22]
    headers = ["Categoria", "Componente Primario (In Stock)", "Alternative Verificate & Link", "Prezzo"]

    def draw_table_header():
        pdf.set_fill_color(*C_BLACK)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("DejaVu", "B", 8.0)
        for i, h in enumerate(headers):
            align = "R" if i == 3 else "L"
            pdf.cell(col_w[i], 7, h, border=0, align=align, fill=True)
        pdf.ln()

    draw_table_header()

    # Dati BOM verificati al 21 Novembre 2026
    rows = [
        {
            "cat": 'Display 7.5"\n800×480',
            "comp": 'Waveshare 7.5" e-Paper HAT (B)',
            "desc": "3 colori (B/W/R, SKU 13505) + Driver HAT SPI. In stock su Waveshare Direct ($54.99); restock Kiwi Electronics il 26/11.",
            "links": [
                ("Waveshare Official (In Stock)", "https://www.waveshare.com/7.5inch-e-paper-hat-b.htm"),
                ("ALT B/W -6.3%: BerryBase €59.90", "https://www.berrybase.de/en/7.5-800-480-epaper-display-hat-for-raspberry-pi-v2"),
                ("ALT 4-Col (H): The Pi Hut £56", "https://thepihut.com/products/7-5-four-colour-epaper-display-h-with-driver-hat-for-raspberry-pi"),
            ],
            "price": "~€52–€66",
        },
        {
            "cat": "Compute",
            "comp": "Raspberry Pi Zero 2 W\n(con Header Pre-saldato)",
            "desc": "Esaurito su BerryBase/Melopero/Kubii. IN STOCK su The Pi Hut (£17.30, IVA EU/IOSS inclusa). Alternativa zero-saldature: Zero 2 W + Hammer Header.",
            "links": [
                ("The Pi Hut Zero 2 W/H (In Stock)", "https://thepihut.com/products/raspberry-pi-zero-2"),
                ("ALT: Pimoroni Hammer Header (£7.20)", "https://thepihut.com/products/gpio-hammer-header-solderless"),
                ("ALT EU: Pi Zero WH BerryBase €18.90", "https://www.berrybase.de/"),
            ],
            "price": "~€19–€26",
        },
        {
            "cat": "Gestione Energia\n& RTC Wake-Up",
            "comp": "UUGear Witty Pi 4 L3V7\n(per Batteria Li-Po 3.7V)",
            "desc": "FIX TECNICO: Witty Pi 4 Mini accetta solo 5V USB-C! L3V7 integra caricatore Li-Po TP4056 + boost 5V/3A + cavo PH2.0. 111 pz in stock EU.",
            "links": [
                ("UUGear L3V7 Direct EU (€25.50)", "https://www.uugear.com/product/witty-pi-4-l3v7/"),
                ("ALT 5V USB-C: Witty Pi 4 Mini (€20)", "https://www.uugear.com/product/witty-pi-4-mini/"),
                ("ALT All-in-One: PiSugar 3 (Tindie)", "https://www.tindie.com/products/pisugar/pisugar-3-battery-for-raspberry-pi-zero/"),
            ],
            "price": "~€20–€26",
        },
        {
            "cat": "Batteria /\nAlimentazione",
            "comp": "Li-Po 3.7V 3000 mAh\n(JST-PH 2.0 + PCM)",
            "desc": "Ultra-sottile (5.7 mm, entra nella cornice). 31 pz in stock su BerryBase EU (€12). Controllare polarità +/- prima di collegare a L3V7!",
            "links": [
                ("BerryBase Soldered 3000mAh (€12)", "https://www.berrybase.de/soldered-li-ion-akku-lithium-polymer-605080-3-7v-3000mah-mit-2-pin-jst-stecker"),
                ("ALT BF: Power Bank USB-C (Anker/UGREEN)", None),
                ("ALT Rete: Alimentatore 5V 2.5A (€7.90)", None),
            ],
            "price": "~€8–€15",
        },
        {
            "cat": "Storage",
            "comp": "microSD 32GB o 64GB A1\n(SanDisk / Kingston / Lexar)",
            "desc": "Offerte Black Friday attive su Amazon.it (19–30 Nov). A causa dei rincari NAND Q4 2026, le 64GB A1 costano quasi quanto le 32GB.",
            "links": [
                ("Amazon.it Black Friday (19–30 Nov)", None),
                ("BerryBase Verbatim 32GB (€9.90)", "https://www.berrybase.de/"),
            ],
            "price": "~€8–€15",
        },
        {
            "cat": "Cornice /\nEnclosure",
            "comp": "IKEA RÖDALM 21×30 cm\n(Sostituisce SANNAHED 21×30)",
            "desc": "SANNAHED 21×30 non è più a catalogo IKEA Italia (solo 25×25). RÖDALM 21×30 ha passe-partout e distanziatore profondo rimovibile!",
            "links": [
                ("IKEA Italia RÖDALM (€7.50)", "https://www.ikea.com/it/it/cat/roedalm-serie-700545/"),
                ("ALT Quadrata: IKEA SANNAHED 25×25", None),
            ],
            "price": "€7.50",
        },
        {
            "cat": "Cavi &\nFissaggio",
            "comp": "Cavo USB-C ad angolo retto +\nNastro carta / Velcro 3M",
            "desc": "Cavo corto 20–30 cm ad angolo retto per ricarica comoda + nastro biadesivo/velcro per fissare Pi e batteria sul retro.",
            "links": [
                ("Amazon.it Black Friday / Ferramenta", None),
            ],
            "price": "~€3–€5",
        },
    ]

    for idx, row in enumerate(rows):
        pdf.set_font("DejaVu", "B", 8.0)
        comp_lines = pdf.multi_cell(col_w[1] - 3, 3.8, row["comp"], dry_run=True, output="LINES")
        pdf.set_font("DejaVu", "", 7.2)
        desc_lines = pdf.multi_cell(col_w[1] - 3, 3.4, row["desc"], dry_run=True, output="LINES")
        cat_lines = row["cat"].split("\n")

        h_col0 = len(cat_lines) * 4.0 + 4
        h_col1 = len(comp_lines) * 3.8 + len(desc_lines) * 3.4 + 5
        h_col2 = len(row["links"]) * 4.5 + 4
        row_h = max(h_col0, h_col1, h_col2, 14.0)

        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()
            draw_table_header()

        x0 = 15
        y0 = pdf.get_y()
        bg = C_ALT_ROW if idx % 2 == 1 else C_WHITE

        pdf.set_fill_color(*bg)
        pdf.rect(x0, y0, sum(col_w), row_h, style="F")
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.2)
        cx = x0
        for w in col_w:
            pdf.rect(cx, y0, w, row_h, style="D")
            cx += w

        # Col 0: Categoria
        pdf.set_xy(x0 + 1.5, y0 + 2.0)
        pdf.set_font("DejaVu", "B", 7.8)
        pdf.set_text_color(*C_RED)
        pdf.multi_cell(col_w[0] - 3.0, 3.8, row["cat"], align="L")

        # Col 1: Componente + descrizione
        pdf.set_xy(x0 + col_w[0] + 1.5, y0 + 1.8)
        pdf.set_font("DejaVu", "B", 8.0)
        pdf.set_text_color(*C_BLACK)
        pdf.multi_cell(col_w[1] - 3.0, 3.8, row["comp"], align="L")
        pdf.set_x(x0 + col_w[0] + 1.5)
        pdf.set_font("DejaVu", "", 7.2)
        pdf.set_text_color(*C_SLATE)
        pdf.multi_cell(col_w[1] - 3.0, 3.4, row["desc"], align="L")

        # Col 2: Link cliccabili
        ly = y0 + 2.0
        lx = x0 + col_w[0] + col_w[1] + 1.8
        for label, url in row["links"]:
            pdf.set_xy(lx, ly)
            if url:
                pdf.set_font("DejaVu", "U", 7.4)
                pdf.set_text_color(*C_LINK)
                pdf.cell(col_w[2] - 3.2, 4.2, f"↗ {label}", link=url)
            else:
                pdf.set_font("DejaVu", "", 7.3)
                pdf.set_text_color(*C_SLATE)
                pdf.cell(col_w[2] - 3.2, 4.2, f"• {label}")
            ly += 4.5

        # Col 3: Prezzo
        pdf.set_xy(x0 + col_w[0] + col_w[1] + col_w[2], y0 + 2.0)
        pdf.set_font("DejaVu", "B", 8.2)
        pdf.set_text_color(*C_BLACK)
        pdf.cell(col_w[3] - 1.5, 4.5, row["price"], align="R")

        pdf.set_y(y0 + row_h)

    # Riga Totale Stimato
    y0 = pdf.get_y()
    pdf.set_fill_color(*C_WARN_BG)
    pdf.set_draw_color(*C_RED)
    pdf.set_line_width(0.4)
    pdf.rect(15, y0, 180, 9.5, style="FD")

    pdf.set_xy(17.5, y0 + 2.2)
    pdf.set_font("DejaVu", "B", 9.2)
    pdf.set_text_color(*C_RED)
    pdf.cell(132, 5, "TOTALE STIMATO PLUG-AND-PLAY (IVA incl., spedizione esclusa)")
    pdf.set_font("DejaVu", "B", 10.2)
    pdf.cell(43, 5, "~€118 – €150", align="R")
    pdf.set_y(y0 + 13)


def draw_black_friday_section(pdf: BomPDF):
    """Sezione dedicata alle offerte Black Friday 2026."""
    pdf.add_page()
    pdf.section_heading(
        "BLACK FRIDAY 2026",
        "Offerte Attive (21 Nov) & Sconti Da Monitorare (27–30 Nov 2026)",
        badge_color=C_BF_BORDER,
    )

    pdf.callout_box(
        "OFFERTE GIA' ATTIVE OGGI (21 Novembre 2026)",
        "• BerryBase EU (Sale%): Waveshare 7.5\" e-Paper HAT v2 (Bianco/Nero, refresh 4s) scontato a €59.90 "
        "invece di €63.90 (-6.3%, 80 pezzi disponibili subito).\n"
        "• Amazon.it Black Friday Week (19–30 Nov 2026): Sconti attivi su microSD A1/A2 (SanDisk Ultra/Extreme, "
        "Lexar, Samsung EVO), Power Bank USB-C Anker/UGREEN (fino al -30% / -46% su gamma Anker), cavi USB-C "
        "ad angolo retto e velcro 3M Command.\n"
        "• LaskaKit EU (laskakit.cz/en/black-friday/): Sconto Black Friday -7% / -8% su oltre 1.650 componenti "
        "maker (display, cavi, moduli alimentazione) + spedizione EU gratuita sopra €100.\n"
        "• MediaWorld / Saturn / Unieuro: Sconti tra -21% e -44% su microSD 32GB/64GB (es. SanDisk Ultra Plus 32GB -21%).",
        C_BF_BG,
        C_BF_BORDER,
    )

    pdf.callout_box(
        "DA MONITORARE IL 27 NOVEMBRE (BLACK FRIDAY) & 30 NOVEMBRE (CYBER MONDAY)",
        "• The Pi Hut & Pimoroni: Storicamente lanciano promozioni lampo 24h–72h (-10% / -20%) su HAT, display e "
        "accessori (le schede Raspberry Pi nude raramente vengono scontate: conviene bloccare subito lo Zero 2 W "
        "mentre è disponibile!).\n"
        "• Kiwi Electronics EU: Nuovo arrivo previsto il 26 Novembre 2026 per il Waveshare 7.5\" e-Paper HAT (B) "
        "3-colori (€51.49 IVA escl.), giusto in tempo per il Black Friday.",
        C_INFO_BG,
        C_INFO_BORDER,
    )


def draw_hardware_notes(pdf: BomPDF):
    """Note Tecniche e Avvertenze di Compatibilità."""
    pdf.section_heading("SEZIONE 2", "Note Tecniche & Avvertenze di Compatibilità (Aggiornate)")

    pdf.callout_box(
        "1. ATTENZIONE: Witty Pi 4 L3V7 vs Witty Pi 4 Mini (Errore Corretto!)",
        "• Witty Pi 4 Mini accetta SOLO alimentazione 5V via USB-C: NON ha circuito boost né caricatore per celle "
        "Li-Po da 3.7V! Usalo solo con alimentatore a muro 5V o Power Bank USB-C senza auto-spegnimento.\n"
        "• Per alimentare il calendario con una batteria Li-Po 3.7V, acquista UUGear Witty Pi 4 L3V7 (€25.50, "
        "111 pz in stock diretto EU): integra TP4056 + boost 5V/3A + cavo JST-PH 2.0.\n"
        "• VERIFICA POLARITA' JST-PH: Prima di collegare la batteria Li-Po da 3000mAh al Witty Pi 4 L3V7, controlla "
        "che filo Rosso (+) e filo Nero (-) coincidano con le serigrafie + e - sulla scheda!",
        C_WARN_BG,
        C_WARN_BORDER,
    )

    pdf.callout_box(
        "2. Display Alternativi — Differenze Software",
        "• Waveshare 7.5\" HAT (B) 3-Colori (B/W/R): 100% plug-and-play con il codice attuale (driver epd7in5b_V2).\n"
        "• Waveshare 7.5\" HAT v2 (Solo B/N, €59.90 su BerryBase): refresh rapidissimo (4s invece di 26s) e più "
        "economico; richiede una modifica di 1 riga in src/display/waveshare_7in5_b.py per usare epd7in5_V2.\n"
        "• Waveshare 7.5\" HAT (H) 4-Colori (R/Y/B/W, The Pi Hut): stessa risoluzione 800×480 e stesse dimensioni "
        "meccaniche (163.2 × 97.9 mm), richiede il driver Waveshare epd7in5g / epd7in5h.",
        C_INFO_BG,
        C_INFO_BORDER,
    )

    pdf.callout_box(
        "3. Compatibilità GPIO (Zero Conflitti) & Alternativa Zero Saldature",
        "• Display Waveshare 7.5\" HAT: usa SPI0 (GPIO 8, 9, 10, 11) + RST (17), DC (25), BUSY (24), PWR (18).\n"
        "• Witty Pi 4 L3V7 / Mini: usa I2C1 (GPIO 2/SDA, 3/SCL) + GPIO 4 per wake-up/shutdown. Zero conflitti!\n"
        "• Se trovi solo Raspberry Pi Zero 2 W senza pin, il kit Pimoroni GPIO Hammer Header (+ dima acrilica) "
        "permette di montare i 40 pin a pressione con un martelletto, sempre senza saldatore.",
        C_SUCCESS_BG,
        C_SUCCESS_BORDER,
    )


def draw_budget_diy_section(pdf: BomPDF):
    """Riferimento Rapido Opzione Ultra-Budget DIY (con saldatura)."""
    pdf.add_page()
    pdf.section_heading("SEZIONE 3", "Opzione Ultra-Budget DIY (Richiede Saldatura)")

    pdf.set_font("DejaVu", "", 8.2)
    pdf.set_text_color(*C_BLACK)
    pdf.multi_cell(
        0,
        4.1,
        "Per maker esperti con saldatore che vogliono minimizzare la spesa usando pannello raw e moduli discreti:",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(1.5)

    col_w = [52, 100, 28]
    headers = ["Componente DIY", "Note Tecniche & Ruolo", "Costo Indicativo"]

    pdf.set_fill_color(*C_SLATE)
    pdf.set_text_color(*C_WHITE)
    pdf.set_font("DejaVu", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 6.5, h, align="R" if i == 2 else "L", fill=True)
    pdf.ln()

    diy_rows = [
        ("Good Display GDEY075Z08", 'Pannello e-Paper 7.5" 3-colori (800×480) nudo senza driver HAT.', "~€35–€42"),
        ("Adattatore DESPI-C02", "Scheda adattatore FPC 24-pin -> SPI per collegamento al Pi.", "~€6–€8"),
        ("Raspberry Pi Zero 2 W", "Senza header pre-saldato (The Pi Hut £14.40, in stock).", "~€17"),
        ("18650 + TP4056 + DS3231", "Cella Li-Ion 18650, caricatore USB-C TP4056 e modulo RTC DS3231.", "~€7–€9"),
        ("IKEA RÖDALM + microSD", "Cornice 21×30 cm (€7.50) + microSD 32GB/64GB A1 (~€8–€10).", "~€16–€18"),
    ]

    for idx, (comp, note, price) in enumerate(diy_rows):
        bg = C_ALT_ROW if idx % 2 == 1 else C_WHITE
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.2)

        pdf.set_font("DejaVu", "B", 7.8)
        pdf.set_text_color(*C_BLACK)
        pdf.cell(col_w[0], 6.5, comp, border=1, fill=True)

        pdf.set_font("DejaVu", "", 7.4)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(col_w[1], 6.5, note, border=1, fill=True)

        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*C_BLACK)
        pdf.cell(col_w[2], 6.5, price, border=1, align="R", fill=True)
        pdf.ln()

    pdf.set_fill_color(*C_LIGHT_BG)
    pdf.set_draw_color(*C_SLATE)
    pdf.set_line_width(0.35)
    pdf.set_font("DejaVu", "B", 8.3)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(col_w[0] + col_w[1], 7.2, "TOTALE STIMATO OPZIONE ULTRA-BUDGET DIY (richiede saldatura)", border=1, fill=True)
    pdf.set_text_color(*C_RED)
    pdf.cell(col_w[2], 7.2, "~€81 – €94", border=1, align="R", fill=True)
    pdf.ln(6)


def main():
    pdf = BomPDF()
    pdf.add_page()

    draw_header_banner(pdf)
    draw_bom_table(pdf)
    draw_black_friday_section(pdf)
    draw_hardware_notes(pdf)
    draw_budget_diy_section(pdf)

    OUT_REPO.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT_REPO))

    print(f"PDF generato con successo:\n - {OUT_REPO}")


if __name__ == "__main__":
    main()
