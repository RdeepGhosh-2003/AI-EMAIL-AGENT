from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "AI_Email_Agent_Setup_Guide.docx"


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=120, start=130, bottom=120, end=130):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color="D9D9D9", size="6"):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:color"), color)


def set_table_widths(table, widths):
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    layout = table._tbl.tblPr.first_child_found_in("w:tblLayout")
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        table._tbl.tblPr.append(layout)
    layout.set(qn("w:type"), "fixed")
    for column, width in zip(table.columns, widths):
        column.width = width
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = width


def keep_table_rows_together(table):
    header_properties = table.rows[0]._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    header_properties.append(repeat)
    for row in table.rows:
        properties = row._tr.get_or_add_trPr()
        properties.append(OxmlElement("w:cantSplit"))


def remove_paragraph_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is not None:
        p_pr.remove(borders)
    borders = OxmlElement("w:pBdr")
    for edge in ("top", "left", "bottom", "right", "between"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    p_pr.append(borders)


def add_body(doc, text, bold_lead=None):
    paragraph = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        paragraph.add_run(bold_lead).bold = True
        paragraph.add_run(text[len(bold_lead):])
    else:
        paragraph.add_run(text)
    return paragraph


def add_step(doc, title, body):
    paragraph = doc.add_paragraph(style="List Number")
    run = paragraph.add_run(title)
    run.bold = True
    paragraph.add_run(f"  {body}")
    return paragraph


def build():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.12
    for style_name, size, before, after in (
        ("Title", 26, 0, 14),
        ("Subtitle", 12, 0, 22),
        ("Heading 1", 18, 18, 8),
        ("Heading 2", 13, 12, 5),
    ):
        style = styles[style_name]
        style.font.name = "Aptos Display" if style_name != "Subtitle" else "Aptos"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    title = doc.add_paragraph("AI Email Agent Setup and Sharing Guide", style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    remove_paragraph_border(title)
    subtitle = doc.add_paragraph("Recipient installation and account connection instructions", style="Subtitle")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.LEFT

    add_body(doc, "This guide explains how to share the AI Email Agent safely, install it on another Windows computer, connect the recipient's Microsoft Outlook mailbox, configure the selected AI provider, and begin daily use. The recipient must approve Microsoft access to their own mailbox once; the app cannot bypass this consent.")

    doc.add_heading("What the recipient needs", level=1)
    table = doc.add_table(rows=1, cols=2)
    headers = ("Item", "Requirement")
    for index, text in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = text
        set_cell_shading(cell, "1F4E78")
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.bold = True
    rows = (
        ("Computer", "Windows 10 or Windows 11 with internet access"),
        ("Python", "Python 3.11 or newer installed from python.org with Add Python to PATH selected"),
        ("AI service", "An API key for one supported provider; the current shared configuration selects Google Gemini"),
        ("Email account", "A Microsoft Outlook or Microsoft 365 mailbox"),
        ("Permission", "Ability to approve mailbox access; work accounts may require an administrator"),
    )
    for row_index, values in enumerate(rows, start=1):
        cells = table.add_row().cells
        for column, value in enumerate(values):
            cells[column].text = value
            cells[column].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cells[column])
            if row_index % 2 == 0:
                set_cell_shading(cells[column], "EEF4F8")
    set_table_borders(table)
    for row in table.rows:
        for cell in row.cells:
            set_cell_margins(cell)
    set_table_widths(table, (Inches(1.65), Inches(4.95)))
    keep_table_rows_together(table)

    doc.add_heading("Create a safe sharing package", level=1)
    add_body(doc, "On the original computer, double-click Create_Sharing_Package. The app creates AI-Email-Agent-Share.zip in the project folder.")
    add_body(doc, "The package excludes private API keys, Microsoft authorization tokens, processed email data, the virtual environment, and runtime files. Do not copy the original project folder directly because it may contain private account material.", "The package excludes")

    doc.add_heading("Install and open the app", level=1)
    add_step(doc, "Extract the ZIP", "Move the ZIP to the recipient's computer and extract it to a normal folder such as Documents. Do not run the app from inside the ZIP.")
    add_step(doc, "Open the dashboard", "Double-click Open_Dashboard. On the first run, the setup window creates the Python environment and installs required packages. Later launches open silently and go directly to the dashboard.")
    add_step(doc, "Allow local startup", "If Windows asks about an unknown downloaded file, verify that the ZIP came directly from the person sharing the project. The dashboard itself listens only on this computer at 127.0.0.1 and does not require public firewall access.")
    add_step(doc, "Keep the agent running", "Closing the browser tab does not stop the agent. Reopen it by double-clicking Open_Dashboard again. Use Stop Agent inside the dashboard when you want the background process to end.")

    doc.add_heading("Configure the AI provider", level=1)
    add_step(doc, "Open Agent Settings", "Select the AI and Writing tab.")
    add_step(doc, "Choose a provider", "Select Google Gemini, OpenAI, or Anthropic as the AI engine.")
    add_step(doc, "Paste the API key", "Paste the matching provider key and save Settings. The key is stored only in the local .env file and is not displayed again.")
    add_body(doc, "The current configuration uses Google Gemini with the gemini-3.6-flash model. OpenAI and Anthropic settings remain available, but the app will use only the provider selected in Settings.")
    add_body(doc, "Use a separate API key for each recipient when possible. This makes usage easier to audit and lets one person's key be revoked without affecting everyone else.")

    doc.add_heading("Connect Microsoft Outlook", level=1)
    add_body(doc, "Microsoft requires a public desktop application registration. The application client ID is not a password, so the project owner may provide a suitable multi-tenant client ID to recipients. Each recipient still signs in and consents for their own mailbox.")
    add_step(doc, "Create or reuse an app registration", "In Microsoft Entra, register an application that supports personal Microsoft accounts and organizational accounts as appropriate.")
    add_step(doc, "Enable desktop authentication", "Under Authentication, add the Mobile and desktop applications platform with http://localhost as the redirect URI and allow public client flows.")
    add_step(doc, "Add delegated permissions", "Add Microsoft Graph delegated permissions Mail.ReadWrite and Mail.Send. Some organizations require an administrator to approve these permissions.")
    add_step(doc, "Save the app details", "In Agent Settings, select Accounts. Enter the Application client ID. Use common as the tenant unless the organization supplies a specific tenant ID, then select Save Microsoft details.")
    add_step(doc, "Connect Microsoft", "Select Connect Microsoft and complete the Microsoft sign-in and consent page. The authorization cache remains only on that computer.")

    permissions_heading = doc.add_heading("Permissions and privacy", level=1)
    permissions_heading.paragraph_format.page_break_before = True
    permissions = doc.add_table(rows=1, cols=2)
    for index, text in enumerate(("Permission", "Why it is used")):
        cell = permissions.rows[0].cells[index]
        cell.text = text
        set_cell_shading(cell, "1F4E78")
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.bold = True
    permission_rows = (
        ("Read mail", "Find unread messages that may need a reply and preserve conversation context"),
        ("Create and modify drafts", "Create proposed replies and update or remove provider drafts"),
        ("Send mail", "Send only after the configured approval rules allow it"),
        ("Local token storage", "Keep the recipient signed in without storing the mailbox password"),
    )
    for row_index, values in enumerate(permission_rows, start=1):
        cells = permissions.add_row().cells
        for column, value in enumerate(values):
            cells[column].text = value
            cells[column].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cells[column])
            if row_index % 2 == 0:
                set_cell_shading(cells[column], "EEF4F8")
    set_table_borders(permissions)
    for row in permissions.rows:
        for cell in row.cells:
            set_cell_margins(cell)
    set_table_widths(permissions, (Inches(1.9), Inches(4.7)))
    keep_table_rows_together(permissions)

    doc.add_heading("Daily use", level=1)
    add_step(doc, "Start", "Double-click Open_Dashboard. It starts the agent if needed and opens the dashboard.")
    add_step(doc, "Unlock", "If PIN protection is enabled, unlock the dashboard before viewing drafts or changing settings.")
    add_step(doc, "Review", "Open a proposed reply, check the recipient, facts, attachments, and commitments, then edit, send, discard, or delete it.")
    add_step(doc, "Close the browser safely", "Closing the tab leaves the agent running. Double-click Open_Dashboard whenever you want the page again.")
    add_step(doc, "Stop", "Select Stop Agent in the dashboard when you want monitoring and the local server to end.")

    doc.add_heading("Troubleshooting", level=1)
    issues = (
        ("Dashboard does not open", "Wait for first-run package installation to finish, then double-click Open_Dashboard again."),
        ("Microsoft Connect is disabled", "Save a valid Application client ID in Accounts first."),
        ("Microsoft needs admin approval", "Ask the organization's Microsoft 365 administrator to approve Mail.ReadWrite and Mail.Send, or use an account whose policy permits user consent."),
        ("Dashboard asks for a PIN", "Enter the local dashboard PIN. If the PIN is lost, reset it from the project owner or recreate the local configuration."),
        ("A connection expires", "Return to Agent Settings, open Accounts, and select the provider's Connect button again."),
    )
    for title_text, body in issues:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.keep_together = True
        paragraph.add_run(f"{title_text}. ").bold = True
        paragraph.add_run(body)

    doc.add_heading("Files that must remain private", level=1)
    for item in (
        ".env because it contains AI provider keys and Microsoft configuration",
        "outlook token_cache.json because it contains Microsoft authorization data",
        "the data folder because it may contain email content and processing history",
    ):
        doc.add_paragraph(item, style="List Bullet")
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
