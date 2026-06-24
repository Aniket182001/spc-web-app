from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle
)
from reportlab.lib import colors

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter


def generate_spc_pdf(
    chart_title,
    insight,
    chart_path,
    output_path
):

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "SPC Analysis Report",
            styles["Title"]
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    elements.append(
        Paragraph(
            chart_title,
            styles["Heading2"]
        )
    )

    elements.append(
        Spacer(1, 10)
    )

    elements.append(
        Paragraph(
            insight.replace("<br>", "<br/>"),
            styles["BodyText"]
        )
    )

    elements.append(
        Spacer(1, 20)
    )

    elements.append(
        Image(
            chart_path,
            width=500,
            height=320
        )
    )

    doc.build(elements)

def generate_check_sheet_pdf(counters_data, output_path):
    """
    Generates a PDF report for the Check Sheet data.
    counters_data: list of dicts with 'name' and 'count'
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter
    )

    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("Check Sheet Report", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Calculate Total
    total_count = sum(c.get('count', 0) for c in counters_data)

    # Table Data
    table_data = [["Counter Name", "Count"]]
    for c in counters_data:
        table_data.append([c.get('name', 'Unknown'), str(c.get('count', 0))])
    
    # Append Total row
    table_data.append(["TOTAL", str(total_count)])

    # Create Table
    t = Table(table_data, colWidths=[300, 100])
    
    # Apply Styles
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor('#FFFFFF')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#334155')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -2), 1, colors.HexColor('#E2E8F0')),
        
        # Total Row styling
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#0F172A')),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#94A3B8')),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 20))

    doc.build(elements)