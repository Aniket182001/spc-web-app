from flask import (
    Blueprint,
    render_template,
    request,
    session,
    send_from_directory
)
from flask_login import login_required, current_user
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
import time

from utils import allowed_file
from werkzeug.utils import secure_filename
from spc_pdf_generator import generate_spc_pdf

from spc_constants import (
    A2_TABLE,
    D3_TABLE,
    D4_TABLE,
    A3_TABLE,
    B3_TABLE,
    B4_TABLE
)

# =========================================================
# BLUEPRINT SETUP
# =========================================================

spc_bp = Blueprint('spc', __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base directories
UPLOAD_BASE = os.path.join(BASE_DIR, 'uploads')
CHARTS_BASE = os.path.join(BASE_DIR, 'static', 'charts')
REPORTS_BASE = os.path.join(BASE_DIR, 'static', 'reports')

# =========================================================
# WESTERN ELECTRIC RULE 2
# =========================================================

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
            return True, (
                "⚠️ Western Electric Rule 2 triggered: "
                "7 consecutive points above center line"
            )

        if consecutive_below >= 7:
            return True, (
                "⚠️ Western Electric Rule 2 triggered: "
                "7 consecutive points below center line"
            )

    return False, None


# =========================================================
# HOME ROUTE
# =========================================================

@spc_bp.route("/")
@login_required
def home():
    return render_template(
        "index.html",
        graph=None,
        insight=None,
        warning=None,
        system_status="ready",
    )


# =========================================================
# UPLOAD + PROCESS
# =========================================================

@spc_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    sample_size_input = request.form.get('sample_size')

    # =====================================================
    # FILE VALIDATION
    # =====================================================

    if 'file' not in request.files:
        return render_template(
            'index.html',
            insight="❌ No file part in request",
            system_status="error",
            selected_chart=chart_type
        )

    file = request.files['file']

    if file.filename == '':

        return render_template(
            'index.html',
            insight="❌ Please select a file.",
            system_status="error",
            selected_chart=chart_type
        )

    if not allowed_file(file.filename):

        return render_template(
            'index.html',
            insight=(
                "❌ Invalid file type. "
                "Please upload CSV, TXT, XLSX, or XLS file."
            ),
            system_status="error",
            selected_chart=chart_type
        )

    # =====================================================
    # FORM INPUTS
    # =====================================================

    chart_type = request.form['chart']

    chart_name = request.form.get(
        'chart_name',
        ''
    ).strip()

    subgroup_size_input = request.form.get(
    'subgroup_size'
    )

    subgroup_size = (
        int(subgroup_size_input)
        if subgroup_size_input
        else None
    )

    lsl_input = request.form.get('lsl')

    usl_input = request.form.get('usl')

    # =====================================================
    # SAVE FILE
    # =====================================================

    filename = secure_filename(file.filename)

    unique_name = (
        str(int(time.time())) + "_" + filename
    )

    user_upload_dir = os.path.join(UPLOAD_BASE, f"user_{current_user.id}")
    os.makedirs(user_upload_dir, exist_ok=True)

    filepath = os.path.join(
        user_upload_dir,
        unique_name
    )

    try:

        file.save(filepath)

    except PermissionError:

        return render_template(
            'index.html',
            insight="❌ Please close the Excel file before uploading",
            system_status="error",
            selected_chart=chart_type
        )

    # =====================================================
    # READ FILE
    # =====================================================

    file_extension = os.path.splitext(
        filename
    )[1].lower()

    if file_extension == '.csv':

        df = pd.read_csv(
            filepath,
            header=None,
            encoding='latin1'
        )

    elif file_extension == '.txt':

        df = pd.read_csv(
            filepath,
            header=None,
            encoding='latin1'
        )

    elif file_extension in ['.xlsx', '.xls']:

        df = pd.read_excel(
            filepath,
            header=None
        )

    else:

        return render_template(
            'index.html',
            insight="❌ Unsupported file format",
            system_status="error",
            selected_chart=chart_type
        )

    # =====================================================
    # CLEAN DATA
    # =====================================================

    df = df.apply(
        pd.to_numeric,
        errors='coerce'
    )

    df = df.dropna()

    if len(df) == 0:

        return render_template(
            'index.html',
            insight="❌ No valid numeric data found",
            system_status="error",
            selected_chart=chart_type
        )

    warning = None

    # =====================================================
    # XBAR-R CHART
    # =====================================================

    if chart_type == "xbar_r":

        data = df.iloc[:, 0].values

        if len(data) < subgroup_size:
            return render_template(
                'index.html',
                insight="❌ Not enough data for subgrouping",
                system_status="error",
                selected_chart=chart_type
            )

        total_points = len(data)

        remainder = total_points % subgroup_size

        dropped_points = 0
        dropped_values = []

        if remainder != 0:

            dropped_points = remainder

            dropped_values = data[-remainder:]

            usable_length = total_points - remainder

            data = data[:usable_length]

        subgroups = data.reshape(
            -1,
            subgroup_size
        )

        n = subgroup_size

        if dropped_points > 0:

            clean_values = [int(x) for x in dropped_values]

            warning = (
                f"⚠️ Last {dropped_points} point(s) "
                f"were excluded: {clean_values} "
                f"to form complete subgroups"
            )

        if n not in A2_TABLE:

            return render_template(
                'index.html',
                insight="❌ Unsupported subgroup size for Xbar-R",
                system_status="error",
                selected_chart=chart_type
            )

        # -------------------------------------------------
        # CALCULATIONS
        # -------------------------------------------------

        xbar = np.mean(subgroups, axis=1)

        R = (
            np.max(subgroups, axis=1)
            - np.min(subgroups, axis=1)
        )

        xbar_bar = np.mean(xbar)

        R_bar = np.mean(R)

        A2 = A2_TABLE[n]
        D3 = D3_TABLE[n]
        D4 = D4_TABLE[n]

        UCL_xbar = xbar_bar + (A2 * R_bar)
        LCL_xbar = xbar_bar - (A2 * R_bar)

        UCL_R = D4 * R_bar
        LCL_R = D3 * R_bar

        # -------------------------------------------------
        # USL / LSL
        # -------------------------------------------------

        process_std = np.std(data, ddof=1)

        if usl_input and lsl_input:

            usl = float(usl_input)
            lsl = float(lsl_input)

        else:

            usl = xbar_bar + (3 * process_std)
            lsl = xbar_bar - (3 * process_std)

        # -------------------------------------------------
        # OUT OF CONTROL
        # -------------------------------------------------

        out_x = (
            (xbar > UCL_xbar)
            | (xbar < LCL_xbar)
        )

        out_r = (
            (R > UCL_R)
            | (R < LCL_R)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        rule2_triggered, rule2_message = check_rule2(
            xbar,
            xbar_bar
        )

        if rule2_triggered:
            analysis_messages.append(rule2_message)

        if np.sum(out_x) == 0:

            analysis_messages.append(
                "✅ Process average is stable within control limits"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_x)} subgroup mean point(s) "
                f"outside control limits"
            )

        if np.sum(out_r) == 0:

            analysis_messages.append(
                "✅ Process variation is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_r)} range point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total subgroups analyzed: {len(xbar)}"
        )

        analysis_messages.append(
            f"ℹ️ Subgroup size used: {n}"
        )

        insight = "<br>".join(analysis_messages)

        subgroup_numbers = list(
            range(1, len(xbar) + 1)
        )

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("X Bar Chart", "R Chart")
        )

        chart_title = (
            f"{chart_name} - X Bar R Control Chart"
            if chart_name
            else "X Bar R Control Chart"
        )

        # XBAR TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=xbar,
                mode='lines+markers',
                name='Subgroup Mean',
                line=dict(
                    color='black',
                    width=2
                ),
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
                line=dict(
                    color='black',
                    width=2
                ),
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

    # =====================================================
    # XBAR-S CHART
    # =====================================================

    elif chart_type == "xbar_s":

        data = df.iloc[:, 0].values

        if len(data) < subgroup_size:
            return render_template(
                'index.html',
                insight="❌ Not enough data for subgrouping",
                system_status="error",
                selected_chart=chart_type
            )

        total_points = len(data)

        remainder = total_points % subgroup_size

        dropped_points = 0
        dropped_values = []

        if remainder != 0:

            dropped_points = remainder

            dropped_values = data[-remainder:]

            usable_length = total_points - remainder

            data = data[:usable_length]

        subgroups = data.reshape(
            -1,
            subgroup_size
        )

        n = subgroup_size

        if dropped_points > 0:

            clean_values = [int(x) for x in dropped_values]

            warning = (
                f"⚠️ Last {dropped_points} point(s) "
                f"were excluded: {clean_values} "
                f"to form complete subgroups"
            )

        if n not in A3_TABLE:

            return render_template(
                'index.html',
                insight="❌ Unsupported subgroup size for Xbar-S",
                system_status="error",
                selected_chart=chart_type
            )

        # -------------------------------------------------
        # CALCULATIONS
        # -------------------------------------------------

        xbar = np.mean(subgroups, axis=1)

        S = np.std(
            subgroups,
            axis=1,
            ddof=1
        )

        xbar_bar = np.mean(xbar)

        S_bar = np.mean(S)

        A3 = A3_TABLE[n]
        B3 = B3_TABLE[n]
        B4 = B4_TABLE[n]

        UCL_xbar = xbar_bar + (A3 * S_bar)
        LCL_xbar = xbar_bar - (A3 * S_bar)

        UCL_S = B4 * S_bar
        LCL_S = B3 * S_bar

        # -------------------------------------------------
        # USL / LSL
        # -------------------------------------------------

        process_std = np.std(data, ddof=1)

        if usl_input and lsl_input:

            usl = float(usl_input)
            lsl = float(lsl_input)

        else:

            usl = xbar_bar + (3 * process_std)
            lsl = xbar_bar - (3 * process_std)

        # -------------------------------------------------
        # OUT OF CONTROL
        # -------------------------------------------------

        out_x = (
            (xbar > UCL_xbar)
            | (xbar < LCL_xbar)
        )

        out_s = (
            (S > UCL_S)
            | (S < LCL_S)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        rule2_triggered, rule2_message = check_rule2(
            xbar,
            xbar_bar
        )

        if rule2_triggered:
            analysis_messages.append(rule2_message)

        if np.sum(out_x) == 0:

            analysis_messages.append(
                "✅ Process average is stable within control limits"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_x)} subgroup mean point(s) "
                f"outside control limits"
            )

        if np.sum(out_s) == 0:

            analysis_messages.append(
                "✅ Process standard deviation is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_s)} standard deviation point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total subgroups analyzed: {len(xbar)}"
        )

        analysis_messages.append(
            f"ℹ️ Subgroup size used: {n}"
        )

        insight = "<br>".join(analysis_messages)

        subgroup_numbers = list(
            range(1, len(xbar) + 1)
        )

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            subplot_titles=("X Bar Chart", "S Chart")
        )

        chart_title = (
            f"{chart_name} - X Bar S Control Chart"
            if chart_name
            else "X Bar S Control Chart"
        )

        # XBAR TRACE

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=xbar,
                mode='lines+markers',
                name='Subgroup Mean',
                line=dict(
                    color='black',
                    width=2
                ),
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
                line=dict(
                    color='black',
                    width=2
                ),
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

    # =====================================================
    # P CHART
    # =====================================================

    elif chart_type == "p_chart":

        defectives = df.iloc[:, 0].values

        sample_size = int(sample_size_input)

        sample_sizes = np.full(
            len(defectives),
            sample_size
        )

        p_values = defectives / sample_sizes

        p_bar = (
            np.sum(defectives)
            / np.sum(sample_sizes)
        )

        UCL = p_bar + (
            3 * np.sqrt(
                (p_bar * (1 - p_bar))
                / sample_sizes
            )
        )

        LCL = p_bar - (
            3 * np.sqrt(
                (p_bar * (1 - p_bar))
                / sample_sizes
            )
        )

        LCL = np.maximum(LCL, 0)

        out_p = (
            (p_values > UCL)
            | (p_values < LCL)
        )

        subgroup_numbers = list(
            range(1, len(p_values) + 1)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        if np.sum(out_p) == 0:

            analysis_messages.append(
                "✅ Process fraction defective is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_p)} point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total samples analyzed: {len(p_values)}"
        )

        insight = "<br>".join(analysis_messages)

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = go.Figure()

        chart_title = (
            f"{chart_name} - P Chart"
            if chart_name
            else "P Chart"
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=p_values,
                mode='lines+markers',
                name='Fraction Defective',
                line=dict(
                    color='black',
                    width=2
                ),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_p
                    ]
                )
            )
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=UCL,
                mode='lines',
                name='UCL',
                line=dict(
                    color='red',
                    dash='dash'
                )
            )
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=LCL,
                mode='lines',
                name='LCL',
                line=dict(
                    color='red',
                    dash='dash'
                )
            )
        )

        fig.add_hline(
            y=p_bar,
            line_color='green',
            annotation_text=f"CL = {p_bar:.4f}"
        )


    
    # =====================================================
    # NP CHART
    # =====================================================

    elif chart_type == "np_chart":

        defectives = df.iloc[:, 0].values

        sample_size = int(sample_size_input)

        p_bar = np.mean(defectives) / sample_size

        np_values = defectives

        CL = sample_size * p_bar

        sigma = np.sqrt(
            sample_size * p_bar * (1 - p_bar)
        )

        UCL = CL + (3 * sigma)

        LCL = CL - (3 * sigma)

        LCL = max(LCL, 0)

        out_np = (
            (np_values > UCL)
            | (np_values < LCL)
        )

        subgroup_numbers = list(
            range(1, len(np_values) + 1)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        if np.sum(out_np) == 0:

            analysis_messages.append(
                "✅ Number of defectives is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_np)} point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total samples analyzed: {len(np_values)}"
        )

        insight = "<br>".join(analysis_messages)

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = go.Figure()

        chart_title = (
            f"{chart_name} - NP Chart"
            if chart_name
            else "NP Chart"
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=np_values,
                mode='lines+markers',
                name='Defectives',
                line=dict(
                    color='black',
                    width=2
                ),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_np
                    ]
                )
            )
        )

        fig.add_hline(
            y=CL,
            line_color='green',
            annotation_text=f"CL = {CL:.2f}"
        )

        fig.add_hline(
            y=UCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"UCL = {UCL:.2f}"
        )

        fig.add_hline(
            y=LCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"LCL = {LCL:.2f}"
        )

    # =====================================================
    # C CHART
    # =====================================================

    elif chart_type == "c_chart":

        c_values = df.iloc[:, 0].values

        c_bar = np.mean(c_values)

        UCL = c_bar + (3 * np.sqrt(c_bar))

        LCL = c_bar - (3 * np.sqrt(c_bar))

        LCL = max(LCL, 0)

        out_c = (
            (c_values > UCL)
            | (c_values < LCL)
        )

        subgroup_numbers = list(
            range(1, len(c_values) + 1)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        if np.sum(out_c) == 0:

            analysis_messages.append(
                "✅ Defect count process is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_c)} point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total samples analyzed: {len(c_values)}"
        )

        insight = "<br>".join(analysis_messages)

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = go.Figure()

        chart_title = (
            f"{chart_name} - C Chart"
            if chart_name
            else "C Chart"
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=c_values,
                mode='lines+markers',
                name='Defects',
                line=dict(
                    color='black',
                    width=2
                ),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_c
                    ]
                )
            )
        )

        fig.add_hline(
            y=c_bar,
            line_color='green',
            annotation_text=f"CL = {c_bar:.2f}"
        )

        fig.add_hline(
            y=UCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"UCL = {UCL:.2f}"
        )

        fig.add_hline(
            y=LCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"LCL = {LCL:.2f}"
        )

    # =====================================================
    # U CHART
    # =====================================================

    elif chart_type == "u_chart":

        defects = df.iloc[:, 0].values

        sample_size = int(sample_size_input)

        u_values = defects / sample_size

        u_bar = np.mean(u_values)

        UCL = u_bar + (
            3 * np.sqrt(u_bar / sample_size)
        )

        LCL = u_bar - (
            3 * np.sqrt(u_bar / sample_size)
        )

        LCL = max(LCL, 0)

        out_u = (
            (u_values > UCL)
            | (u_values < LCL)
        )

        subgroup_numbers = list(
            range(1, len(u_values) + 1)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        if np.sum(out_u) == 0:

            analysis_messages.append(
                "✅ Defects per unit process is stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_u)} point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total samples analyzed: {len(u_values)}"
        )

        insight = "<br>".join(analysis_messages)

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = go.Figure()

        chart_title = (
            f"{chart_name} - U Chart"
            if chart_name
            else "U Chart"
        )

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=u_values,
                mode='lines+markers',
                name='Defects per Unit',
                line=dict(
                    color='black',
                    width=2
                ),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_u
                    ]
                )
            )
        )

        fig.add_hline(
            y=u_bar,
            line_color='green',
            annotation_text=f"CL = {u_bar:.4f}"
        )

        fig.add_hline(
            y=UCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"UCL = {UCL:.4f}"
        )

        fig.add_hline(
            y=LCL,
            line_color='red',
            line_dash='dash',
            annotation_text=f"LCL = {LCL:.4f}"
        )

    # =====================================================
    # IMR CHART
    # =====================================================

    elif chart_type == "imr_chart":

        data = df.iloc[:, 0].values

        if len(data) < 2:

            return render_template(
                'index.html',
                insight="❌ IMR Chart requires at least 2 observations",
                system_status="error",
                selected_chart=chart_type
            )

        # -------------------------------------------------
        # CALCULATIONS
        # -------------------------------------------------

        individual_values = data

        moving_ranges = np.abs(
            np.diff(individual_values)
        )

        x_bar = np.mean(individual_values)

        mr_bar = np.mean(moving_ranges)

        # Individuals chart limits

        UCL_X = x_bar + (2.66 * mr_bar)

        LCL_X = x_bar - (2.66 * mr_bar)

        # Moving range chart limits

        UCL_MR = 3.267 * mr_bar

        LCL_MR = 0

        # -------------------------------------------------
        # USL / LSL
        # -------------------------------------------------

        process_std = np.std(data, ddof=1)

        if usl_input and lsl_input:

            usl = float(usl_input)

            lsl = float(lsl_input)

        else:

            usl = x_bar + (3 * process_std)

            lsl = x_bar - (3 * process_std)

        # -------------------------------------------------
        # OUT OF CONTROL
        # -------------------------------------------------

        out_x = (
            (individual_values > UCL_X)
            | (individual_values < LCL_X)
        )

        out_mr = (
            (moving_ranges > UCL_MR)
            | (moving_ranges < LCL_MR)
        )

        # -------------------------------------------------
        # INSIGHTS
        # -------------------------------------------------

        analysis_messages = []

        if np.sum(out_x) == 0:

            analysis_messages.append(
                "✅ Individual observations are stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_x)} individual point(s) "
                f"outside control limits"
            )

        if np.sum(out_mr) == 0:

            analysis_messages.append(
                "✅ Moving ranges are stable"
            )

        else:

            analysis_messages.append(
                f"⚠️ {np.sum(out_mr)} moving range point(s) "
                f"outside control limits"
            )

        analysis_messages.append(
            f"ℹ️ Total observations analyzed: {len(individual_values)}"
        )

        insight = "<br>".join(analysis_messages)

        subgroup_numbers = list(
            range(1, len(individual_values) + 1)
        )

        mr_numbers = list(
            range(2, len(individual_values) + 1)
        )

        # -------------------------------------------------
        # PLOT
        # -------------------------------------------------

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=False,
            subplot_titles=(
                "Individuals Chart",
                "Moving Range Chart"
            )
        )

        chart_title = (
            f"{chart_name} - IMR Chart"
            if chart_name
            else "IMR Chart"
        )

        # Individuals plot

        fig.add_trace(
            go.Scatter(
                x=subgroup_numbers,
                y=individual_values,
                mode='lines+markers',
                name='Individuals',
                line=dict(
                    color='black',
                    width=2
                ),
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

        # Moving range plot

        fig.add_trace(
            go.Scatter(
                x=mr_numbers,
                y=moving_ranges,
                mode='lines+markers',
                name='Moving Range',
                line=dict(
                    color='black',
                    width=2
                ),
                marker=dict(
                    size=8,
                    color=[
                        'red' if val else 'black'
                        for val in out_mr
                    ]
                )
            ),
            row=2,
            col=1
        )

        # Individuals limits

        fig.add_hline(
            y=x_bar,
            line_color='green',
            annotation_text=f"CL = {x_bar:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=UCL_X,
            line_color='red',
            line_dash='dash',
            annotation_text=f"UCL = {UCL_X:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=LCL_X,
            line_color='red',
            line_dash='dash',
            annotation_text=f"LCL = {LCL_X:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=usl,
            line_color='blue',
            line_dash='dot',
            annotation_text=f"USL = {usl:.2f}",
            row=1,
            col=1
        )

        fig.add_hline(
            y=lsl,
            line_color='blue',
            line_dash='dot',
            annotation_text=f"LSL = {lsl:.2f}",
            row=1,
            col=1
        )

        # MR limits

        fig.add_hline(
            y=mr_bar,
            line_color='green',
            annotation_text=f"CL = {mr_bar:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=UCL_MR,
            line_color='red',
            line_dash='dash',
            annotation_text=f"UCL = {UCL_MR:.2f}",
            row=2,
            col=1
        )

        fig.add_hline(
            y=LCL_MR,
            line_color='red',
            line_dash='dash',
            annotation_text=f"LCL = {LCL_MR:.2f}",
            row=2,
            col=1
        )

    # -------------------------------------------------
    # End Block - No more chart types below this point
    # -------------------------------------------------
    
    else:
        return render_template(
            'index.html',
            insight="❌ Invalid chart type selected",
            system_status="error",
            selected_chart=chart_type
        )

    # =====================================================
    # DETECT SINGLE vs DUAL CHART
    # =====================================================

    SINGLE_CHART_TYPES = {'p_chart', 'np_chart', 'c_chart', 'u_chart'}
    is_single_chart = chart_type in SINGLE_CHART_TYPES

    # =====================================================
    # COMMON LAYOUT  –  SPC Insight Pro theme
    # =====================================================

    # ── Palette ──────────────────────────────────────
    CLR_BG          = '#F8FAFC'   # near-white canvas
    CLR_PAPER       = '#FFFFFF'
    CLR_GRID        = '#E2E8F0'   # slate-200
    CLR_AXIS        = '#94A3B8'   # slate-400
    CLR_TITLE       = '#0F172A'   # slate-900
    CLR_SUBTITLE    = '#475569'   # slate-600
    CLR_DATA        = '#1E40AF'   # brand blue (in-control points)
    CLR_DATA_LINE   = '#3B82F6'   # blue-500
    CLR_OOC         = '#EF4444'   # red-500  (out-of-control markers)
    CLR_CL          = '#10B981'   # emerald-500  center line
    CLR_UCL_LCL     = '#F59E0B'   # amber-500    control limits
    CLR_SPEC        = '#6366F1'   # indigo-500   spec limits
    CLR_ANNOTATION  = '#334155'   # slate-700

    # ── Annotation style shared across all hlines ────
    ann_font = dict(
        size=11,
        color=CLR_ANNOTATION,
        family="'DM Sans', 'IBM Plex Sans', sans-serif"
    )

    # ── Re-style every trace  ────────────────────────
    for trace in fig.data:
        # Data lines
        trace.line.color = CLR_DATA_LINE
        trace.line.width = 2
        # Marker colours: keep red for OOC, upgrade in-control to brand blue
        if hasattr(trace, 'marker') and trace.marker.color is not None:
            colours = trace.marker.color
            if isinstance(colours, list):
                trace.marker.color = [
                    CLR_OOC if c in ('red', '#EF4444') else CLR_DATA
                    for c in colours
                ]
            trace.marker.size = 7
            trace.marker.line = dict(color=CLR_PAPER, width=1.5)

    # Re-style every hline shape
    # Plotly stores hline color in shape.line.color; map original named colors to refined palette
    _shape_color_map = {
        'green': (CLR_CL,      2,   'solid'),
        'red':   (CLR_UCL_LCL, 1.5, 'dash'),
        'blue':  (CLR_SPEC,    1.5, 'dot'),
    }
    for shape in fig.layout.shapes:
        try:
            orig = shape.line.color or ''
        except Exception:
            continue
        if orig in _shape_color_map:
            new_clr, new_w, new_dash = _shape_color_map[orig]
            shape.line.color = new_clr
            shape.line.width = new_w
            shape.line.dash  = new_dash

    # ── Re-style every annotation ────────────────────
    for ann in fig.layout.annotations:
        if ann.text and ann.text.strip():
            # Subplot titles  (no x-anchor adjustment needed)
            if ann.xref == 'paper' and ann.yref == 'paper':
                ann.font = dict(
                    size=13,
                    color=CLR_SUBTITLE,
                    family="'DM Sans', 'IBM Plex Sans', sans-serif"
                )
            else:
                # Limit labels
                ann.font = ann_font
                ann.bgcolor = 'rgba(255,255,255,0.82)'
                ann.bordercolor = CLR_GRID
                ann.borderwidth = 1
                ann.borderpad = 3
                ann.xanchor = 'left'

    # ── Main layout ──────────────────────────────────
    fig.update_layout(
        annotations=[
            dict(
                text="SPC Insight Pro • AIQM Analytics",
                x=1,
                y=-0.12,
                xref="paper",
                yref="paper",
                showarrow=False,
                xanchor="right",
                font=dict(
                    size=10,
                    color="#94A3B8"
                )
            )
        ],
        title=dict(
            text=chart_title,
            x=0.5,
            xanchor='center',
            font=dict(
                size=20,
                color=CLR_TITLE,
                family="'DM Sans', 'IBM Plex Sans', sans-serif",
            ),
            pad=dict(t=8, b=4)
        ),
        height=480 if is_single_chart else 880,
        showlegend=False,
        plot_bgcolor=CLR_BG,
        paper_bgcolor=CLR_PAPER,
        font=dict(
            size=12,
            color=CLR_ANNOTATION,
            family="'DM Sans', 'IBM Plex Sans', sans-serif"
        ),
        margin=dict(l=64, r=120, t=80, b=56),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor=CLR_PAPER,
            bordercolor=CLR_GRID,
            font=dict(
                size=12,
                color=CLR_TITLE,
                family="'DM Sans', 'IBM Plex Sans', sans-serif"
            )
        )
    )

    # ── Axes for all subplots ────────────────────────
    fig.update_xaxes(
        showgrid=True,
        gridcolor=CLR_GRID,
        gridwidth=1,
        zeroline=False,
        linecolor=CLR_GRID,
        tickcolor=CLR_AXIS,
        tickfont=dict(size=11, color=CLR_AXIS),
        title_font=dict(size=12, color=CLR_SUBTITLE),
        title_text="Subgroup",
        mirror=False,
        ticks='outside',
        ticklen=4,
        showspikes=True,
        spikethickness=1,
        spikecolor=CLR_GRID,
        spikedash='dot'
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor=CLR_GRID,
        gridwidth=1,
        zeroline=False,
        linecolor=CLR_GRID,
        tickcolor=CLR_AXIS,
        tickfont=dict(size=11, color=CLR_AXIS),
        title_font=dict(size=12, color=CLR_SUBTITLE),
        mirror=False,
        ticks='outside',
        ticklen=4
    )

    user_charts_dir = os.path.join(CHARTS_BASE, f"user_{current_user.id}")
    os.makedirs(user_charts_dir, exist_ok=True)
    
    chart_image_path = os.path.join(user_charts_dir, "latest_chart.png")
    
    try:
        fig.write_image(chart_image_path)
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        return render_template(
            'index.html',
            insight="❌ Chart generation failed. Please check the server chart export setup.",
            system_status="error",
            selected_chart=chart_type
        )

    graph_html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={
            'displaylogo': False,
            'responsive': True,
            'modeBarButtonsToRemove': [
                'lasso2d',
                'select2d',
                'autoScale2d',
                'toggleSpikelines',
                'hoverCompareCartesian',
                'hoverClosestCartesian'
            ],
            'toImageButtonOptions': {
                'format': 'svg',
                'filename': chart_title,
                'height': 880,
                'width': 1200,
                'scale': 2
            }
        }
    )

    # =====================================================
    # STORE SESSION & DELETE FILE
    # =====================================================

    session["last_chart_title"] = chart_title
    session["last_chart_path"] = chart_image_path
    session["last_insight"] = insight

    os.remove(filepath)

    return render_template(
        'index.html',
        graph=graph_html,
        insight=insight,
        warning=warning,
        is_single_chart=is_single_chart,
        system_status="processing",
        selected_chart=chart_type
    )

    # =========================================================
    # Download Route
    # =========================================================

@spc_bp.route("/download-spc-report")
@login_required
def download_spc_report():

    user_reports_dir = os.path.join(REPORTS_BASE, f"user_{current_user.id}")
    os.makedirs(user_reports_dir, exist_ok=True)
    
    output_pdf = os.path.join(user_reports_dir, "spc_report.pdf")

    generate_spc_pdf(
        session.get("last_chart_title", "SPC Report"),
        session.get("last_insight", ""),
        session.get("last_chart_path", ""),
        output_pdf
    )
    
    report_url = f"/static/reports/user_{current_user.id}/spc_report.pdf"

    return render_template(
        "report_status.html",
        report_url=report_url,
        system_status="report",
        selected_chart=""
    )
