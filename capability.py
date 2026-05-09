from flask import Blueprint, render_template, request
import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objs as go
import os
import time

from werkzeug.utils import secure_filename

capability_bp = Blueprint('capability', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================
# Capability Home
# =========================

@capability_bp.route('/capability')
def capability_home():

    return render_template('capability.html')


# =========================
# Capability Analysis
# =========================

@capability_bp.route('/capability/analyze', methods=['POST'])
def capability_analysis():

    file = request.files['file']

    lsl = float(request.form['lsl'])
    usl = float(request.form['usl'])

    # Save file

    filename = secure_filename(file.filename)

    unique_name = str(int(time.time())) + "_" + filename

    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

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

        return "❌ Unsupported file format"

    # Clean numeric data

    df = df.apply(pd.to_numeric, errors='coerce')

    df = df.dropna()

    data = df.iloc[:, 0].values

    if len(data) == 0:

        return "❌ No valid numeric data found"

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

    # =========================
    # Insights
    # =========================

    insight_messages = []

    # Capability interpretation

    if cpk < 1:

        capability_rating = "❌ POOR"

        capability_message = (
            "Process capability is below minimum acceptable level."
        )

    elif cpk < 1.33:

        capability_rating = "⚠️ ACCEPTABLE"

        capability_message = (
            "Process is acceptable but improvement is recommended."
        )

    elif cpk < 1.67:

        capability_rating = "✅ GOOD"

        capability_message = (
            "Process meets common industrial capability standards."
        )

    else:

        capability_rating = "🔥 EXCELLENT"

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

    insight = "<br>".join(insight_messages)

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
            opacity=0.75
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
            line=dict(width=3)
        )
    )

    # Spec lines

    fig.add_vline(
        x=lsl,
        line_color='red',
        line_dash='dash',
        annotation_text=f"LSL = {lsl}"
    )

    fig.add_vline(
        x=usl,
        line_color='red',
        line_dash='dash',
        annotation_text=f"USL = {usl}"
    )

    fig.add_vline(
        x=mean,
        line_color='green',
        annotation_text=f"Mean = {mean:.2f}"
    )

    fig.update_layout(
        title='Process Capability Histogram',
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=500,
        bargap=0.05
    )

    graph_html = fig.to_html(full_html=False)

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
    'capability_message': capability_message
}

    return render_template(
        'capability.html',
        results=results,
        insight=insight,
        graph=graph_html
    )