#!/usr/bin/env python3
"""
Genera la Lista della Spesa Completa (BOM) & Link ai Negozi in Italiano (PDF A4)
per Smart E-Paper Calendar 7.5" 3-Colori (Configurazione Plug-and-Play HAT).
"""

import shutil
from pathlib import Path
from fpdf import FPDF


# Percorsi principali
PROJECT_ROOT = Path("/home/antigravity/smart-epaper-calendar")
BRAIN_DIR = Path(
    "/home/antigravity/.gemini/jetski/brain/v1/default/jetski_remote_agents_3p/"
    "5f82617e-f5dc-440f-87fc-403adb078613"
)

OUT_REPO = PROJECT_ROOT / "docs" / "lista_spesa_bom_it.pdf"
OUT_BRAIN = BRAIN_DIR / "lista_spesa_bom_it.pdf"

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
        self.cell(95, 5, 'Smart E-Paper Calendar 7.5" 3-Colori  •  Lista della Spesa (BOM)')
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*C_RED)
        self.cell(0, 5, "Configurazione Plug-and-Play HAT", align="R", new_x="LMARGIN", new_y="NEXT")
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
        self.cell(140, 5, "Smart E-Paper Calendar  •  Reparto Hardware (Marco Rossi) & Procurement (Sofia Patel)")
        self.set_font("DejaVu", "B", 7.5)
        self.cell(0, 5, f"Pagina {self.page_no()} / {{nb}}", align="R")

    def section_heading(self, badge: str, title: str):
        self.ln(2)
        if badge:
            self.set_fill_color(*C_RED)
            self.set_text_color(*C_WHITE)
            self.set_font("DejaVu", "B", 8)
            bw = self.get_string_width(badge) + 6
            self.cell(bw, 5.5, badge, fill=True, new_x="LMARGIN", new_y="NEXT")
            self.ln(1.5)
        self.set_text_color(*C_BLACK)
        self.set_font("DejaVu", "B", 13)
        self.cell(0, 6.5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*C_RED)
        self.set_line_width(0.6)
        self.line(15, self.get_y() + 0.5, 48, self.get_y() + 0.5)
        self.set_draw_color(*C_BORDER)
        self.set_line_width(0.25)
        self.line(48, self.get_y() + 0.5, 195, self.get_y() + 0.5)
        self.ln(3.5)

    def callout_box(self, title: str, body: str, bg_color, border_color):
        # Calcola altezza approssimativa con split_only
        self.set_font("DejaVu", "", 8.5)
        lines = self.multi_cell(172, 4.3, body, dry_run=True, output="LINES")
        box_h = 8 + len(lines) * 4.3 + 3
        if self.get_y() + box_h > self.page_break_trigger:
            self.add_page()

        x0 = 15
        y0 = self.get_y()
        self.set_fill_color(*bg_color)
        self.rect(x0, y0, 180, box_h, style="F")
        self.set_fill_color(*border_color)
        self.rect(x0, y0, 1.5, box_h, style="F")

        self.set_xy(x0 + 4.5, y0 + 2.5)
        self.set_font("DejaVu", "B", 9)
        self.set_text_color(*border_color)
        self.cell(170, 4.5, title, new_x="LMARGIN", new_y="NEXT")

        self.set_x(x0 + 4.5)
        self.set_font("DejaVu", "", 8.5)
        self.set_text_color(*C_BLACK)
        self.multi_cell(172, 4.3, body, align="L")
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
    pdf.rect(x0, y0 + 2.2, w, 33.5, style="F")
    pdf.set_draw_color(*C_BORDER)
    pdf.set_line_width(0.3)
    pdf.rect(x0, y0 + 2.2, w, 33.5, style="D")

    pdf.set_xy(x0 + 5, y0 + 5)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*C_RED)
    pdf.cell(0, 4.5, "DOCUMENTO DI APPROVVIGIONAMENTO  •  LISTA DELLA SPESA UFFICIALE (BOM)", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "B", 14.5)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(0, 7.5, 'Smart E-Paper Calendar 7.5" 3-Colori (B/W/R, 800×480)', new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(*C_SLATE)
    pdf.cell(0, 5.5, "Configurazione Plug-and-Play HAT (Zero Saldature)", new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(x0 + 5)
    pdf.set_font("DejaVu", "", 8.5)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(
        0,
        5,
        "Approvata dal Reparto Hardware (Marco Rossi) e Procurement (Sofia Patel)  •  Link cliccabili verificati EU",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.set_y(y0 + 39.5)


def draw_bom_table(pdf: BomPDF):
    """Tabella completa BOM Plug-and-Play con link cliccabili."""
    pdf.section_heading("SEZIONE 1", "Tabella Completa BOM — Configurazione Plug-and-Play (Zero Saldature)")

    pdf.set_font("DejaVu", "", 8.5)
    pdf.set_text_color(*C_SLATE)
    pdf.multi_cell(
        0,
        4.3,
        "Tutti i componenti elencati di seguito si assemblano ad incastro tramite header GPIO da 40 pin e cavi standard: "
        "non è richiesto alcun saldatore. Clicca sui link blu nella colonna dedicata per aprire direttamente le pagine prodotto.",
        align="L",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

    # Definizione colonne (totale = 180 mm)
    col_w = [34, 62, 62, 22]
    headers = ["Categoria", "Componente & Specifiche", "Link Negozio (Cliccabili)", "Prezzo"]

    def draw_table_header():
        pdf.set_fill_color(*C_BLACK)
        pdf.set_text_color(*C_WHITE)
        pdf.set_font("DejaVu", "B", 8.2)
        for i, h in enumerate(headers):
            align = "R" if i == 3 else "L"
            pdf.cell(col_w[i], 7, h, border=0, align=align, fill=True)
        pdf.ln()

    draw_table_header()

    # Dati BOM
    rows = [
        {
            "cat": 'Display 7.5"\n3-Colori',
            "comp": 'Waveshare 7.5" e-Paper HAT (B)',
            "desc": "Pannello E-Ink 800×480 Nero/Bianco/Rosso + Driver HAT SPI con connettore 40-pin.",
            "links": [
                ("Kiwi Electronics EU", "https://www.kiwi-electronics.com/en/7-5inch-e-ink-display-hat-for-raspberry-pi-800x480-3-color-4022"),
                ("Waveshare Official", "https://www.waveshare.com/7.5inch-e-paper-hat-b.htm"),
            ],
            "price": "~€55–€64",
        },
        {
            "cat": "Compute",
            "comp": "Raspberry Pi Zero 2 WH",
            "desc": "Quad-core 64-bit, Wi-Fi/BLE integrato, header GPIO 40-pin già pre-saldato in fabbrica.",
            "links": [
                ("BerryBase EU", "https://www.berrybase.de/raspberry-pi-zero-2-wh"),
            ],
            "price": "~€20–€22",
        },
        {
            "cat": "Gestione Batteria\n& RTC Wake-Up",
            "comp": "UUGear Witty Pi 4 Mini",
            "desc": "Real-Time Clock DS3231 + taglio totale alimentazione (0.01 mA in sleep) + ingresso 5V/Li-Po.",
            "links": [
                ("UUGear Direct", "https://www.uugear.com/product/witty-pi-4-mini/"),
                ("The Pi Hut", "https://thepihut.com/products/witty-pi-4-mini-realtime-clock-and-power-management-for-raspberry-pi"),
            ],
            "price": "~€20–€24",
        },
        {
            "cat": "Batteria\nRicaricabile",
            "comp": "Li-Po 3.7V 3000–5000 mAh\noppure Power Bank USB-C",
            "desc": "Cella Li-Po con connettore JST-PH 2.0 protetto (PCM) o Power Bank compatto (senza auto-off).",
            "links": [
                ("BerryBase EU", "https://www.berrybase.de/"),
                ("The Pi Hut", "https://thepihut.com/"),
            ],
            "price": "~€10–€15",
        },
        {
            "cat": "Storage",
            "comp": "microSD 32GB Classe A1",
            "desc": "SanDisk Ultra / Kingston Canvas Select Plus (32GB A1 per Raspberry Pi OS Lite 64-bit).",
            "links": [
                ("Acquisto locale / Amazon / Store tech", None),
            ],
            "price": "~€6–€7",
        },
        {
            "cat": "Cornice /\nEnclosure",
            "comp": "IKEA SANNAHED 21×30 cm",
            "desc": "Include passe-partout su misura + cavità posteriore profonda per alloggiare elettronica e batteria.",
            "links": [
                ("IKEA Nero (504.449.57)", "https://www.ikea.com/pt/en/p/sannahed-frame-black-50444957/"),
                ("IKEA Bianco (504.591.14)", "https://www.ikea.com/pt/en/p/sannahed-frame-white-50459114/"),
            ],
            "price": "~€7.99",
        },
        {
            "cat": "Cavi &\nFissaggio",
            "comp": "Cavo ad angolo retto +\nNastro carta / biadesivo",
            "desc": "Cavo USB-C / Micro-USB corto ad angolo retto (20–30 cm) + nastro carta/biadesivo per fissaggio interno.",
            "links": [
                ("Ferramenta / Store elettronica", None),
            ],
            "price": "~€3",
        },
    ]

    for idx, row in enumerate(rows):
        # Calcola altezza riga dinamicamente
        pdf.set_font("DejaVu", "B", 8.2)
        comp_lines = pdf.multi_cell(col_w[1] - 3, 4.0, row["comp"], dry_run=True, output="LINES")
        pdf.set_font("DejaVu", "", 7.5)
        desc_lines = pdf.multi_cell(col_w[1] - 3, 3.6, row["desc"], dry_run=True, output="LINES")
        cat_lines = row["cat"].split("\n")

        h_col0 = len(cat_lines) * 4.2 + 4
        h_col1 = len(comp_lines) * 4.0 + len(desc_lines) * 3.6 + 5
        h_col2 = len(row["links"]) * 4.8 + 4
        row_h = max(h_col0, h_col1, h_col2, 13.5)

        if pdf.get_y() + row_h > pdf.page_break_trigger:
            pdf.add_page()
            draw_table_header()

        x0 = 15
        y0 = pdf.get_y()
        bg = C_ALT_ROW if idx % 2 == 1 else C_WHITE

        # Sfondo e bordi riga
        pdf.set_fill_color(*bg)
        pdf.rect(x0, y0, sum(col_w), row_h, style="F")
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.2)
        cx = x0
        for w in col_w:
            pdf.rect(cx, y0, w, row_h, style="D")
            cx += w

        # Col 0: Categoria
        pdf.set_xy(x0 + 1.8, y0 + 2.2)
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*C_RED)
        pdf.multi_cell(col_w[0] - 3.6, 4.0, row["cat"], align="L")

        # Col 1: Componente + descrizione
        pdf.set_xy(x0 + col_w[0] + 1.8, y0 + 2.0)
        pdf.set_font("DejaVu", "B", 8.2)
        pdf.set_text_color(*C_BLACK)
        pdf.multi_cell(col_w[1] - 3.6, 4.0, row["comp"], align="L")
        pdf.set_x(x0 + col_w[0] + 1.8)
        pdf.set_font("DejaVu", "", 7.4)
        pdf.set_text_color(*C_SLATE)
        pdf.multi_cell(col_w[1] - 3.6, 3.6, row["desc"], align="L")

        # Col 2: Link cliccabili
        ly = y0 + 2.2
        lx = x0 + col_w[0] + col_w[1] + 2.0
        for label, url in row["links"]:
            pdf.set_xy(lx, ly)
            if url:
                pdf.set_font("DejaVu", "U", 7.8)
                pdf.set_text_color(*C_LINK)
                pdf.cell(col_w[2] - 4.0, 4.4, f"↗ {label}", link=url)
            else:
                pdf.set_font("DejaVu", "", 7.6)
                pdf.set_text_color(*C_SLATE)
                pdf.cell(col_w[2] - 4.0, 4.4, f"• {label}")
            ly += 4.8

        # Col 3: Prezzo
        pdf.set_xy(x0 + col_w[0] + col_w[1] + col_w[2], y0 + 2.2)
        pdf.set_font("DejaVu", "B", 8.5)
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
    pdf.set_font("DejaVu", "B", 9.5)
    pdf.set_text_color(*C_RED)
    pdf.cell(132, 5, "TOTALE STIMATO PLUG-AND-PLAY (IVA incl., spedizione esclusa)")
    pdf.set_font("DejaVu", "B", 10.5)
    pdf.cell(43, 5, "~€122 – €135", align="R")
    pdf.set_y(y0 + 13)


def draw_hardware_notes(pdf: BomPDF):
    """Note Tecniche del Reparto Hardware (Marco Rossi)."""
    pdf.add_page()
    pdf.section_heading("SEZIONE 2", "Note Tecniche del Reparto Hardware (Marco Rossi)")

    pdf.callout_box(
        "1. Perché Raspberry Pi Zero 2 WH (e non Pi Zero W originale)",
        "• Energia totale inferiore per ciclo di sync: grazie ai 4 core ARM Cortex-A53 a 64-bit, la generazione "
        "dell'immagine e il trasferimento dati completano il refresh in ~15–20 secondi invece di >60 secondi del "
        "vecchio Zero W. Anche se il picco di corrente è leggermente più alto, il tempo attivo ridotto abbassa "
        "l'energia totale consumata per singolo aggiornamento.\n"
        "• Supporto completo a 64-bit (Raspberry Pi OS Lite 64-bit) e header GPIO 40-pin già pre-saldato (suffisso WH).",
        C_INFO_BG,
        C_INFO_BORDER,
    )

    pdf.callout_box(
        "2. Autonomia Stimata con Witty Pi 4 Mini (Taglio Alimentazione Totale)",
        "• A differenza dello standby software di Linux, Witty Pi 4 Mini scollega fisicamente l'alimentazione al "
        "Raspberry Pi tra una sincronizzazione e l'altra (assorbimento residuo ~0.01 mA per il solo RTC).\n"
        "• Con una programmazione standard di 4 sincronizzazioni al giorno e una batteria Li-Po da 3000 mAh (3.7V), "
        "l'autonomia stimata raggiunge ~4–6 mesi con una singola ricarica.",
        C_SUCCESS_BG,
        C_SUCCESS_BORDER,
    )

    pdf.callout_box(
        "3. Verifica Compatibilità GPIO (Zero Conflitti)",
        "• Display Waveshare 7.5\" HAT (B): utilizza il bus SPI0 (GPIO 8/CE0, 9/MISO, 10/MOSI, 11/SCLK) più i pin "
        "di controllo RST (GPIO 17), DC (GPIO 25), BUSY (GPIO 24) e PWR (GPIO 18).\n"
        "• UUGear Witty Pi 4 Mini: comunica sul bus I2C1 (GPIO 2/SDA, GPIO 3/SCL) per l'RTC DS3231 e usa GPIO 4 "
        "per il segnale di wake-up/shutdown.\n"
        "• Risultato: nessuna sovrapposizione di pin tra i due HAT. L'impilamento su header 40-pin è pienamente compatibile.",
        C_INFO_BG,
        C_INFO_BORDER,
    )


def draw_budget_diy_section(pdf: BomPDF):
    """Riferimento Rapido Opzione Ultra-Budget DIY (con saldatura)."""
    pdf.section_heading("SEZIONE 3", "Riferimento Rapido — Opzione Ultra-Budget DIY (Richiede Saldatura)")

    pdf.set_font("DejaVu", "", 8.5)
    pdf.set_text_color(*C_BLACK)
    pdf.multi_cell(
        0,
        4.3,
        "Per maker esperti che dispongono già di saldatore e preferiscono ridurre al minimo il costo dei componenti "
        "acquistando pannello nudo e moduli discreti (senza HAT pre-assemblati):",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)

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
        ("Raspberry Pi Zero 2 W", "Senza header pre-saldato (richiede saldatura pin o cavi diretti).", "~€17–€19"),
        ("18650 + TP4056 + DS3231", "Cella Li-Ion 18650, caricatore USB-C TP4056 e modulo RTC DS3231.", "~€7–€9"),
        ("IKEA SANNAHED + microSD", "Cornice 21×30 cm + microSD 32GB A1 (come versione Plug-and-Play).", "~€14"),
    ]

    for idx, (comp, note, price) in enumerate(diy_rows):
        bg = C_ALT_ROW if idx % 2 == 1 else C_WHITE
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*C_BORDER)
        pdf.set_line_width(0.2)

        pdf.set_font("DejaVu", "B", 7.8)
        pdf.set_text_color(*C_BLACK)
        pdf.cell(col_w[0], 6.8, comp, border=1, fill=True)

        pdf.set_font("DejaVu", "", 7.5)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(col_w[1], 6.8, note, border=1, fill=True)

        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(*C_BLACK)
        pdf.cell(col_w[2], 6.8, price, border=1, align="R", fill=True)
        pdf.ln()

    # Totale DIY
    pdf.set_fill_color(*C_LIGHT_BG)
    pdf.set_draw_color(*C_SLATE)
    pdf.set_line_width(0.35)
    pdf.set_font("DejaVu", "B", 8.5)
    pdf.set_text_color(*C_BLACK)
    pdf.cell(col_w[0] + col_w[1], 7.5, "TOTALE STIMATO OPZIONE ULTRA-BUDGET DIY (richiede saldatura)", border=1, fill=True)
    pdf.set_text_color(*C_RED)
    pdf.cell(col_w[2], 7.5, "~€70 – €82", border=1, align="R", fill=True)
    pdf.ln(10)


def main():
    pdf = BomPDF()
    pdf.add_page()

    draw_header_banner(pdf)
    draw_bom_table(pdf)
    draw_hardware_notes(pdf)
    draw_budget_diy_section(pdf)

    OUT_REPO.parent.mkdir(parents=True, exist_ok=True)
    OUT_BRAIN.parent.mkdir(parents=True, exist_ok=True)

    pdf.output(str(OUT_REPO))
    shutil.copyfile(OUT_REPO, OUT_BRAIN)

    print(f"PDF generato con successo:\n - {OUT_REPO}\n - {OUT_BRAIN}")


if __name__ == "__main__":
    main()
