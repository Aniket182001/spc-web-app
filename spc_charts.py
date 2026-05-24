from flask import Blueprint, render_template, request
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
import time
from utils import allowed_file

from werkzeug.utils import secure_filename

from spc_constants import (
    A2_TABLE,
    D3_TABLE,
    D4_TABLE,
    A3_TABLE,
    B3_TABLE,
    B4_TABLE
)

# Create Blueprint
spc_bp = Blueprint('spc', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def check_rule2(points, center_line):

    consecutive_above = 0
    consecutive_below = 0

    for point in points:

        if point > center_line:

            consecutive_above += 1
            consecutive_below = 0

        elif point < center_line:

            consecutive_below += 1
            consecutive_above = 0

        else:
            consecutive_above = 0
            consecutive_below = 0

        if consecutive_above >= 7:
            return True, "⚠️ Western Electric Rule 2 triggered: 7 consecutive points above center line"

        if consecutive_below >= 7:
            return True, "⚠️ Western Electric Rule 2 triggered: 7 consecutive points below center line"

    return False, None

# =========================
# HOME ROUTE
# =========================
@spc_bp.route('/')
def index():
    return render_template('index.html')


# =========================
# UPLOAD + PROCESS
# =========================
@spc_bp.route('/upload', methods=['POST'])
def upload_file():

    if 'file' not in request.files:
        return "❌ No file part in request"

    file = request.files['file']

    if file.filename == '':

        return render_template(
            'index.html',
            insight="❌ Please select a file."
        )

    if not allowed_file(file.filename):

        return render_template(
            'index.html',
            insight="❌ Invalid file type. Please upload CSV, TXT, XLSX, or XLS file."
        )

    chart_type = request.form['chart']
    chart_name = request.form.get('chart_name', '').strip()

    subgroup_size = int(request.form['subgroup_size'])

    lsl_input = request.form.get('lsl')

    usl_input = request.form.get('usl')

    # Save file
    filename = secure_filename(file.filename)
    unique_name = str(int(time.time())) + "_" + filename
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    try:
        file.save(filepath)

    except PermissionError:
        return "❌ Please close the Excel file before uploading"

    # =========================
    # READ FILE
    # =========================

    file_extension = os.path.splitext(filename)[1].lower()

    if file_extension == '.csv':
        df = pd.read_csv(filepath, header=None, encoding='latin1')

    elif file_extension == '.txt':
        df = pd.read_csv(filepath, header=None, encoding='latin1')

    elif file_extension in ['.xlsx', '.xls']:
        df = pd.read_excel(filepath, header=None)

    else:
        return "❌ Unsupported file format"

    # =========================
    # CLEAN DATA
    # =========================

    df = df.apply(pd.to_numeric, errors='coerce')
    df = df.dropna()

    data = df.iloc[:, 0].values

    if len(data) == 0:
        return "❌ No valid numeric data found"

    if len(data) < subgroup_size:
        return "❌ Not enough data for subgrouping"

    # =========================
    # HANDLE INCOMPLETE SUBGROUPS
    # =========================

    total_points = len(data)
    remainder = total_points % subgroup_size

    dropped_points = 0
    dropped_values = []

    if remainder != 0:

        dropped_points = remainder

        dropped_values = data[-remainder:]

        usable_length = total_points - remainder

        data = data[:usable_length]

    subgroups = data.reshape(-1, subgroup_size)

    n = subgroup_size

    warning = None

    if dropped_points > 0:

        clean_values = [int(x) for x in dropped_values]

        warning = (
            f"⚠️ Last {dropped_points} point(s) were excluded: "
            f"{clean_values} to form complete subgroups"
        )

    # =========================
    # XBAR-R CHART
    # =========================

    if chart_type == "xbar_r":

        if n not in A2_TABLE:
            return "❌ Unsupported subgroup size for Xbar-R"

        xbar = np.mean(subgroups, axis=1)

        R = np.max(subgroups, axis=1) - np.min(subgroups, axis=1)

        xbar_bar = np.mean(xbar)

        process_std = np.std(data, ddof=1)

        if usl_input and lsl_input:

            usl = float(usl_input)

            lsl = float(lsl_input)

        else:

            usl = xbar_bar + (3 * process_std)

            lsl = xbar_bar - (3 * process_std)

        R_bar = np.mean(R)

        A2 = A2_TABLE[n]
        D3 = D3_TABLE[n]
        D4 = D4_TABLE[n]

        UCL_xbar = xbar_bar + A2 * R_bar
        LCL_xbar = xbar_bar - A2 * R_bar

        UCL_R = D4 * R_bar
        LCL_R = D3 * R_bar

        # Out of control detection

        out_x = (xbar > UCL_xbar) | (xbar < LCL_xbar)

        out_r = (R > UCL_R) | (R < LCL_R)

        total_out = np.sum(out_x) + np.sum(out_r)

        analysis_messages = []

        rule2_triggered, rule2_message = check_rule2(xbar, xbar_bar)

        if rule2_triggered:
            analysis_messages.append(rule2_message)

        if np.sum(out_x) == 0:
            analysis_messages.append(
                "✅ Process average is stable within control limits"
            )
        else:
            analysis_messages.append(
                f"⚠️ {np.sum(out_x)} subgroup mean point(s) outside control limits"
            )

        if np.sum(out_r) == 0:
            analysis_messages.append(
                "✅ Process variation is stable"
            )
        else:
            analysis_messages.append(
                f"⚠️ {np.sum(out_r)} range point(s) outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total subgroups analyzed: {len(xbar)}"
        )

        analysis_messages.append(
            f"ℹ️ Subgroup size used: {n}"
        )

        insight = "<br>".join(analysis_messages) 

        subgroup_numbers = list(range(1, len(xbar) + 1))

        # =========================
        # PLOT
        # =========================

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("X̄ Chart", "R Chart")
        )
        chart_title = f"{chart_name} - X̄-R Control Chart" if chart_name else "X̄-R Control Chart"

        # XBAR TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=xbar,
                mode='lines+markers',
                name='Subgroup Mean',
                line=dict(color='black', width=2),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_x
                    ]
                )
            ),
            row=1,
            col=1
        )

        # R TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=R,
                mode='lines+markers',
                name='Range',
                line=dict(color='black', width=2),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_r
                    ]
                )
            ),
            row=2,
            col=1
        )

        # XBAR LIMITS

        fig.add_hline(
            y=xbar_bar,
            line_color="green",
            annotation_text=f"CL = {xbar_bar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=UCL_xbar,
            line_color="red",
            line_dash="dash",
            annotation_text=f"UCL = {UCL_xbar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=LCL_xbar,
            line_color="red",
            line_dash="dash",
            annotation_text=f"LCL = {LCL_xbar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
        y=usl,
        line_color="blue",
        line_dash="dot",
        annotation_text=f"USL = {usl:.2f}",
        row=1,
        col=1
        )

        fig.add_hline(
        y=lsl,
        line_color="blue",
        line_dash="dot",
        annotation_text=f"LSL = {lsl:.2f}",
        row=1,
        col=1
        )

        # R LIMITS

        fig.add_hline(
            y=R_bar,
            line_color="green",
            annotation_text=f"CL = {R_bar:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=UCL_R,
            line_color="red",
            line_dash="dash",
            annotation_text=f"UCL = {UCL_R:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=LCL_R,
            line_color="red",
            line_dash="dash",
            annotation_text=f"LCL = {LCL_R:.2f}",
            row=2,
            col=1
        )


    # =========================
    # XBAR-S CHART
    # =========================

    elif chart_type == "xbar_s":

        if n not in A3_TABLE:
            return "❌ Unsupported subgroup size for Xbar-S"

        xbar = np.mean(subgroups, axis=1)

        S = np.std(subgroups, axis=1, ddof=1)

        xbar_bar = np.mean(xbar)
        
        process_std = np.std(data, ddof=1)

        if usl_input and lsl_input:

            usl = float(usl_input)

            lsl = float(lsl_input)

        else:

            usl = xbar_bar + (3 * process_std)

            lsl = xbar_bar - (3 * process_std)

        S_bar = np.mean(S)

        A3 = A3_TABLE[n]
        B3 = B3_TABLE[n]
        B4 = B4_TABLE[n]

        UCL_xbar = xbar_bar + A3 * S_bar
        LCL_xbar = xbar_bar - A3 * S_bar

        UCL_S = B4 * S_bar
        LCL_S = B3 * S_bar

        # Out of control detection

        out_x = (xbar > UCL_xbar) | (xbar < LCL_xbar)

        out_s = (S > UCL_S) | (S < LCL_S)

        total_out = np.sum(out_x) + np.sum(out_s)

        analysis_messages = []

        rule2_triggered, rule2_message = check_rule2(xbar, xbar_bar)

        if rule2_triggered:
            analysis_messages.append(rule2_message)

        if np.sum(out_x) == 0:
            analysis_messages.append(
                "✅ Process average is stable within control limits"
            )
        else:
            analysis_messages.append(
                f"⚠️ {np.sum(out_x)} subgroup mean point(s) outside control limits"
            )

        if np.sum(out_s) == 0:
            analysis_messages.append(
                "✅ Process standard deviation is stable"
            )
        else:
            analysis_messages.append(
                f"⚠️ {np.sum(out_s)} standard deviation point(s) outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total subgroups analyzed: {len(xbar)}"
        )

        analysis_messages.append(
            f"ℹ️ Subgroup size used: {n}"
        )

        insight = "<br>".join(analysis_messages)

        subgroup_numbers = list(range(1, len(xbar) + 1))

        # =========================
        # PLOT
        # =========================

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("X̄ Chart", "S Chart")
        )
        chart_title = f"{chart_name} - X̄-S Control Chart" if chart_name else "X̄-S Control Chart"

        # XBAR TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=xbar,
                mode='lines+markers',
                name='Subgroup Mean',
                line=dict(color='black', width=2),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_x
                    ]
                )
            ),
            row=1,
            col=1
        )

        # S TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=S,
                mode='lines+markers',
                name='Std Dev',
                line=dict(color='black', width=2),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_s
                    ]
                )
            ),
            row=2,
            col=1
        )

        # XBAR LIMITS

        fig.add_hline(
            y=xbar_bar,
            line_color="green",
            annotation_text=f"CL = {xbar_bar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=UCL_xbar,
            line_color="red",
            line_dash="dash",
            annotation_text=f"UCL = {UCL_xbar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=LCL_xbar,
            line_color="red",
            line_dash="dash",
            annotation_text=f"LCL = {LCL_xbar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=usl,
            line_color="blue",
            line_dash="dot",
            annotation_text=f"USL = {usl:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=lsl,
            line_color="blue",
            line_dash="dot",
            annotation_text=f"LSL = {lsl:.2f}",
            row=1,
            col=1
        )

        # S LIMITS

        fig.add_hline(
            y=S_bar,
            line_color="green",
            annotation_text=f"CL = {S_bar:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=UCL_S,
            line_color="red",
            line_dash="dash",
            annotation_text=f"UCL = {UCL_S:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=LCL_S,
            line_color="red",
            line_dash="dash",
            annotation_text=f"LCL = {LCL_S:.2f}",
            row=2,
            col=1
        )

    else:
        return "❌ Invalid chart type selected"

    # =========================
    # COMMON LAYOUT
    # =========================

    fig.update_layout(
        title=chart_title,
        height=850,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=14),
        title_x=0.5
    )

    fig.update_xaxes(
        title_text="Subgroup Number",
        row=2,
        col=1
    )

    fig.update_yaxes(
        title_text="Subgroup Mean",
        row=1,
        col=1
    )

    if chart_type == "xbar_r":

        fig.update_yaxes(
            title_text="Range",
            row=2,
            col=1
        )

    else:

        fig.update_yaxes(
            title_text="Std Dev (s)",
            row=2,
            col=1
        )

    graph_html = fig.to_html(
        full_html=False,
        config={
            'displaylogo': False,
            'modeBarButtonsToRemove': [
            'lasso2d',
            'select2d',
            'autoScale2d',
            'toggleSpikelines',
            'hoverCompareCartesian',
            'hoverClosestCartesian'
        ]
        }
    )

    # Delete uploaded file after processing
    os.remove(filepath)

    return render_template(
        'index.html',
        graph=graph_html,
        insight=insight,
        warning=warning
    )
