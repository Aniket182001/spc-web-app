from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image
)

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