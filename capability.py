from flask import Blueprint, render_template, request
import pandas as pd
import numpy as np
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

    cp = (usl - lsl) / (6 * std_dev)

    cpu = (usl - mean) / (3 * std_dev)

    cpl = (mean - lsl) / (3 * std_dev)

    cpk = min(cpu, cpl)

    # =========================
    # Insights
    # =========================

    insight_messages = []

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
    # Histogram
    # =========================

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=data,
            nbinsx=20,
            name='Process Data'
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
        height=500
    )

    graph_html = fig.to_html(full_html=False)

    # Delete uploaded file

    os.remove(filepath)

    results = {
        'mean': round(mean, 4),
        'std_dev': round(std_dev, 4),
        'cp': round(cp, 4),
        'cpk': round(cpk, 4)
    }

    return render_template(
        'capability.html',
        results=results,
        insight=insight,
        graph=graph_html
    )