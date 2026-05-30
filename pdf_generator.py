from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

def generate_capability_pdf(results, chart_path, output_path):

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "<b>Process Capability Report</b>",
        styles['Title']
    )

    elements.append(title)
    elements.append(Spacer(1, 20))

    metrics_text = f"""
    <b>Mean:</b> {results['mean']}<br/>
    <b>Standard Deviation:</b> {results['std_dev']}<br/><br/>

    <b>Cp:</b> {results['cp']}<br/>
    <b>Cpk:</b> {results['cpk']}<br/>
    <b>Pp:</b> {results['pp']}<br/>
    <b>Ppk:</b> {results['ppk']}<br/><br/>

    <b>Sigma Level:</b> {results['sigma_level']}σ<br/>
    <b>Yield:</b> {results['yield_percent']}%<br/>
    <b>DPMO:</b> {results['dpmo']}<br/><br/>

    <b>Capability Rating:</b> {results['capability_rating']}<br/>
    {results['capability_message']}
    """

    metrics = Paragraph(
        metrics_text,
        styles['BodyText']
    )

    elements.append(metrics)
    elements.append(Spacer(1, 20))

    chart = Image(
        chart_path,
        width=500,
        height=300
    )

    elements.append(chart)

    doc.build(elements)

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

        title = Paragraph(
            "<b>SPC Analysis Report</b>",
            styles["Title"]
        )

        elements.append(title)

        elements.append(
            Spacer(1, 20)
        )

        chart_name = Paragraph(
            f"<b>{chart_title}</b>",
            styles["Heading2"]
        )

        elements.append(chart_name)

        elements.append(
            Spacer(1, 10)
        )

        insight_block = Paragraph(
            insight.replace("<br>", "<br/>"),
            styles["BodyText"]
        )

        elements.append(insight_block)

        elements.append(
            Spacer(1, 20)
        )

        chart = Image(
            chart_path,
            width=500,
            height=320
        )

        elements.append(chart)

        doc.build(elements)