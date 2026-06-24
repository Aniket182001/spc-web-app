from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objs as go
import os
import time
from werkzeug.utils import secure_filename
from pdf_generator import generate_capability_pdf
from utils import allowed_file

capability_bp = Blueprint('capability', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base directories
UPLOAD_BASE = os.path.join(BASE_DIR, 'uploads')
CHARTS_BASE = os.path.join(BASE_DIR, 'static', 'charts')
REPORTS_BASE = os.path.join(BASE_DIR, 'static', 'reports')


# =========================
# Capability Home
# =========================

@capability_bp.route('/capability')
@login_required
def capability_home():

    return render_template(
        'capability.html',
        system_status="ready"
    )


# =========================
# Capability Analysis
# =========================

@capability_bp.route('/capability/analyze', methods=['POST'])
@login_required
def capability_analysis():

    file = request.files['file']

    if file.filename == '':

        return render_template(
            'capability.html',
            insight="❌ Please select a file.",
            system_status="error"
        )

    if not allowed_file(file.filename):

        return render_template(
            'capability.html',
            insight="❌ Invalid file type. Please upload CSV, TXT, XLSX, or XLS file.",
            system_status="error"
        )


    # Save file

    filename = secure_filename(file.filename)

    unique_name = str(int(time.time())) + "_" + filename
    
    user_upload_dir = os.path.join(UPLOAD_BASE, f"user_{current_user.id}")
    os.makedirs(user_upload_dir, exist_ok=True)

    filepath = os.path.join(user_upload_dir, unique_name)

    file.save(filepath)

    # Read file

    extension = os.path.splitext(filename)[1].lower()

    if extension == '.csv':

        df = pd.read_csv(filepath, header=None, encoding='latin1')

    elif extension == '.txt':

        df = pd.read_csv(filepath, header=None, encoding='latin1')

    elif extension in ['.xlsx', '.xls']:

        df = pd.read_excel(filepath, header=None)

    else:

        return render_template(
            'capability.html',
            insight="❌ Unsupported file format",
            system_status="error"
        )

    # Clean numeric data

    df = df.apply(pd.to_numeric, errors='coerce')

    df = df.dropna()

    data = df.iloc[:, 0].values

    if len(data) == 0:

        return render_template(
            'capability.html',
            insight="❌ No valid numeric data found.",
            system_status="error"
        )

    # Parse USL and LSL from form request
    lsl = float(request.form.get('lsl'))
    usl = float(request.form.get('usl'))

    if lsl >= usl:
        if os.path.exists(filepath):
            os.remove(filepath)
        return render_template(
            'capability.html',
            insight="❌ LSL must be smaller than USL.",
            system_status="error"
        )

    # =========================
    # Capability Calculations
    # =========================


    mean = np.mean(data)

    std_dev = np.std(data, ddof=1)


    # Cp / Cpk calculations

    cp = (usl - lsl) / (6 * std_dev)

    cpu = (usl - mean) / (3 * std_dev)

    cpl = (mean - lsl) / (3 * std_dev)

    cpk = min(cpu, cpl)

    # Pp / Ppk calculations

    pp = (usl - lsl) / (6 * std_dev)

    ppu = (usl - mean) / (3 * std_dev)

    ppl = (mean - lsl) / (3 * std_dev)

    ppk = min(ppu, ppl)

    # Sigma level estimation

    sigma_level = 3 * cpk

    # Yield estimation

    defect_probability = (
        norm.cdf(lsl, mean, std_dev)
        + (1 - norm.cdf(usl, mean, std_dev))
    )

    yield_percent = (1 - defect_probability) * 100

    defect_percent = defect_probability * 100
    dpmo = defect_probability * 1_000_000

    # =========================
    # Insights
    # =========================

    insight_messages = []

    # Capability interpretation

    if cpk < 1:

        capability_rating = "POOR"

        capability_message = (
            "Process capability is below minimum acceptable level."
        )

    elif cpk < 1.33:

        capability_rating = "ACCEPTABLE"

        capability_message = (
            "Process is acceptable but improvement is recommended."
        )

    elif cpk < 1.67:

        capability_rating = "GOOD"

        capability_message = (
            "Process meets common industrial capability standards."
        )

    else:

        capability_rating = "EXCELLENT"

        capability_message = (
            "Process capability is excellent with very low expected defects."
        )

    #

    if cpk >= 1.33:

        insight_messages.append(
            "✅ Process is capable and meets industry standards"
        )

    elif cpk >= 1:

        insight_messages.append(
            "⚠️ Process is acceptable but improvement is recommended"
        )

    else:

        insight_messages.append(
            "❌ Process capability is poor"
        )

    if abs(cpu - cpl) > 0.2:

        insight_messages.append(
            "⚠️ Process appears off-centered"
        )

    else:

        insight_messages.append(
            "✅ Process is properly centered"
        )

    # =========================
    # Histogram + Normal Curve
    # =========================

    fig = go.Figure()

    # Histogram

    fig.add_trace(
        go.Histogram(
        x=data,
        nbinsx=20,
        histnorm='probability density',
        name='Process Data',
        opacity=0.75,
        marker=dict(
            color='#60a5fa',
            line=dict(
                color='white',
                width=1
                )
            )
        )
    )

    # Normal distribution curve

    x_values = np.linspace(min(data), max(data), 200)

    y_values = (
        1 / (std_dev * np.sqrt(2 * np.pi))
    ) * np.exp(
        -((x_values - mean) ** 2) / (2 * std_dev ** 2)
    )

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode='lines',
            name='Normal Curve',
            line=dict(
            color='#1e3a8a',
            width=4
             )
        )
    )

    # Spec lines

    fig.add_vline(
        x=lsl,
        line_color='#dc2626',
        line_dash='dash',
        annotation_text=f"LSL = {lsl}"
    )

    fig.add_vline(
        x=usl,
        line_color='#dc2626',
        line_dash='dash',
        annotation_text=f"USL = {usl}"
    )

    fig.add_vline(
        x=mean,
        line_color='#16a34a',
        annotation_text=f"Mean = {mean:.2f}"
    )

    fig.add_vrect(
        x0=lsl,
        x1=usl,
        fillcolor='green',
        opacity=0.08,
        line_width=0
    )

    fig.update_layout(
        title='Process Capability Analysis',
        title_x=0.5,
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=550,
        bargap=0.05,
        font=dict(size=14),
        xaxis_title='Measurement Values',
        yaxis_title='Density'
    )

    graph_html = fig.to_html(full_html=False)
    user_charts_dir = os.path.join(CHARTS_BASE, f"user_{current_user.id}")
    os.makedirs(user_charts_dir, exist_ok=True)
    
    chart_image_path = os.path.join(user_charts_dir, "capability_chart.png")

    try:
        fig.write_image(chart_image_path)
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        return render_template(
            'capability.html',
            insight="❌ Chart generation failed. Please check the server chart export setup.",
            system_status="error"
        )

    # Delete uploaded file

    os.remove(filepath)

    results = {
    'mean': round(mean, 4),
    'std_dev': round(std_dev, 4),
    'cp': round(cp, 4),
    'cpk': round(cpk, 4),
    'pp': round(pp, 4),
    'ppk': round(ppk, 4),
    'sigma_level': round(sigma_level, 2),
    'yield_percent': round(yield_percent, 4),
    'defect_percent': round(defect_percent, 4),
    'capability_rating': capability_rating,
    'capability_message': capability_message,
    'dpmo': round(dpmo, 2)
}
    
    user_reports_dir = os.path.join(REPORTS_BASE, f"user_{current_user.id}")
    os.makedirs(user_reports_dir, exist_ok=True)
    
    pdf_path = os.path.join(user_reports_dir, "capability_report.pdf")

    generate_capability_pdf(
        results,
        chart_image_path,
        pdf_path
    )
    
    report_url = f"/static/reports/user_{current_user.id}/capability_report.pdf"

    return render_template(
        'capability.html',
        results=results,
        insight_messages=insight_messages,
        graph=graph_html,
        system_status="processing",
        report_url=report_url
    )
