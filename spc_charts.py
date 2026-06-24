from flask import (
    Blueprint,
    render_template,
    request,
    session,
    send_from_directory,
    send_file,
    jsonify
)
from flask_login import login_required, current_user
from extensions import db
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
import time
from datetime import datetime

from utils import allowed_file
from werkzeug.utils import secure_filename
from spc_pdf_generator import generate_spc_pdf, generate_check_sheet_pdf

from spc_constants import A2_TABLE, A3_TABLE
from quality_engines.basic_qc_engine import calculate_histogram, calculate_scatter, calculate_boxplot, calculate_pareto
from quality_engines.spc_engine import (
    check_rule2,
    calculate_xbar_r,
    calculate_xbar_s,
    calculate_p_chart,
    calculate_np_chart,
    calculate_c_chart,
    calculate_u_chart,
    calculate_imr_chart
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
# DASHBOARD ROUTE
# =========================================================

@spc_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "index.html",
        graph=None,
        insight=None,
        warning=None,
        system_status="ready",
        now=datetime.utcnow(),
    )


# =========================================================
# UPLOAD + PROCESS
# =========================================================

@spc_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    sample_size_input = request.form.get('sample_size')
    chart_type = request.form.get('chart', 'xbar_r')

    # =====================================================
    # SUBSCRIPTION AND LIMIT ENFORCEMENT
    # =====================================================
    if not current_user.subscription_active:
        return render_template(
            'index.html',
            insight="❌ Your subscription is inactive. Please contact the administrator.",
            system_status="error",
            selected_chart=chart_type,
            now=datetime.utcnow()
        )

    if current_user.subscription_expires_at and current_user.subscription_expires_at < datetime.utcnow():
        return render_template(
            'index.html',
            insight="❌ Your subscription has expired. Please contact the administrator.",
            system_status="error",
            selected_chart=chart_type,
            now=datetime.utcnow()
        )

    if current_user.monthly_chart_limit != -1 and current_user.charts_used_this_month >= current_user.monthly_chart_limit:
        return render_template(
            'index.html',
            insight="❌ You have reached your monthly chart limit.",
            system_status="error",
            selected_chart=chart_type,
            now=datetime.utcnow()
        )

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

    if chart_type != "pareto":
        df = df.apply(
            pd.to_numeric,
            errors='coerce'
        )
        df = df.dropna()

    if chart_type != "pareto" and len(df) == 0:

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

        if subgroup_size not in A2_TABLE:
            return render_template(
                'index.html',
                insight="❌ Unsupported subgroup size for Xbar-R",
                system_status="error",
                selected_chart=chart_type
            )

        results = calculate_xbar_r(data, subgroup_size, usl_input, lsl_input)

        xbar = results['xbar']
        R = results['R']
        xbar_bar = results['xbar_bar']
        R_bar = results['R_bar']
        UCL_xbar = results['UCL_xbar']
        LCL_xbar = results['LCL_xbar']
        UCL_R = results['UCL_R']
        LCL_R = results['LCL_R']
        usl = results['usl']
        lsl = results['lsl']
        out_x = results['out_x']
        out_r = results['out_r']
        n = results['n']
        dropped_points = results['dropped_points']
        dropped_values = results['dropped_values']

        if dropped_points > 0:
            clean_values = [int(x) for x in dropped_values]
            warning = (
                f"⚠️ Last {dropped_points} point(s) "
                f"were excluded: {clean_values} "
                f"to form complete subgroups"
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

        if subgroup_size not in A3_TABLE:
            return render_template(
                'index.html',
                insight="❌ Unsupported subgroup size for Xbar-S",
                system_status="error",
                selected_chart=chart_type
            )

        results = calculate_xbar_s(data, subgroup_size, usl_input, lsl_input)

        xbar = results['xbar']
        S = results['S']
        xbar_bar = results['xbar_bar']
        S_bar = results['S_bar']
        UCL_xbar = results['UCL_xbar']
        LCL_xbar = results['LCL_xbar']
        UCL_S = results['UCL_S']
        LCL_S = results['LCL_S']
        usl = results['usl']
        lsl = results['lsl']
        out_x = results['out_x']
        out_s = results['out_s']
        n = results['n']
        dropped_points = results['dropped_points']
        dropped_values = results['dropped_values']

        if dropped_points > 0:
            clean_values = [int(x) for x in dropped_values]
            warning = (
                f"⚠️ Last {dropped_points} point(s) "
                f"were excluded: {clean_values} "
                f"to form complete subgroups"
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

        if df.shape[1] < 2:
            return render_template(
                'index.html',
                insight="❌ P Chart requires two columns: Defectives and Sample Size.",
                system_status="error",
                selected_chart=chart_type
            )

        defectives = df.iloc[:, 0].values
        sample_sizes = df.iloc[:, 1].values

        results = calculate_p_chart(defectives, sample_sizes)

        p_values = results['p_values']
        p_bar = results['p_bar']
        UCL = results['UCL']
        LCL = results['LCL']
        out_p = results['out_p']

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

        if not sample_size_input:
            return render_template(
                'index.html',
                insight="❌ Sample size is required for NP Chart.",
                system_status="error",
                selected_chart=chart_type
            )
        sample_size = int(sample_size_input)

        results = calculate_np_chart(defectives, sample_size)

        np_values = results['np_values']
        CL = results['CL']
        UCL = results['UCL']
        LCL = results['LCL']
        out_np = results['out_np']

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

        results = calculate_c_chart(c_values)

        c_bar = results['c_bar']
        UCL = results['UCL']
        LCL = results['LCL']
        out_c = results['out_c']

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

        if df.shape[1] < 2:
            return render_template(
                'index.html',
                insight="❌ U Chart requires two columns: Defects and Units Inspected.",
                system_status="error",
                selected_chart=chart_type
            )

        defects = df.iloc[:, 0].values
        sample_sizes = df.iloc[:, 1].values

        results = calculate_u_chart(defects, sample_sizes)

        u_values = results['u_values']
        u_bar = results['u_bar']
        UCL = results['UCL']
        LCL = results['LCL']
        out_u = results['out_u']

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

        results = calculate_imr_chart(data, usl_input, lsl_input)

        individual_values = results['individual_values']
        moving_ranges = results['moving_ranges']
        x_bar = results['x_bar']
        mr_bar = results['mr_bar']
        UCL_X = results['UCL_X']
        LCL_X = results['LCL_X']
        UCL_MR = results['UCL_MR']
        LCL_MR = results['LCL_MR']
        usl = results['usl']
        lsl = results['lsl']
        out_x = results['out_x']
        out_mr = results['out_mr']

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

    # =====================================================
    # HISTOGRAM
    # =====================================================

    elif chart_type == "histogram":

        data = df.iloc[:, 0].values

        if not np.issubdtype(data.dtype, np.number):
            try:
                data = pd.to_numeric(data, errors='coerce')
            except Exception:
                pass

        results = calculate_histogram(data)

        if not results:
            return render_template(
                'index.html',
                insight="❌ Histogram requires numeric data.",
                system_status="error",
                selected_chart=chart_type
            )

        clean_data = results['data']
        count = results['count']
        mean = results['mean']
        std_dev = results['std_dev']
        min_val = results['min']
        max_val = results['max']

        # INSIGHTS
        analysis_messages = [
            "✅ Histogram generated successfully",
            f"ℹ️ Valid numeric observations: {count}",
            f"ℹ️ Mean: {mean:.4f} | Std Dev: {std_dev:.4f}",
            f"ℹ️ Range: [{min_val:.4f}, {max_val:.4f}]"
        ]
        insight = "<br>".join(analysis_messages)

        # PLOT
        fig = go.Figure()
        chart_title = f"{chart_name} - Histogram" if chart_name else "Histogram"
        
        fig.add_trace(
            go.Histogram(
                x=clean_data,
                name='Frequency',
                marker_color='#3B82F6',
                opacity=0.85
            )
        )

    # =====================================================
    # SCATTER DIAGRAM
    # =====================================================

    elif chart_type == "scatter":

        if df.shape[1] < 2:
            return render_template(
                'index.html',
                insight="❌ Scatter Diagram requires at least two columns of data.",
                system_status="error",
                selected_chart=chart_type
            )

        x_raw = df.iloc[:, 0].values
        y_raw = df.iloc[:, 1].values

        if not np.issubdtype(x_raw.dtype, np.number):
            try:
                x_raw = pd.to_numeric(x_raw, errors='coerce')
            except:
                pass
        
        if not np.issubdtype(y_raw.dtype, np.number):
            try:
                y_raw = pd.to_numeric(y_raw, errors='coerce')
            except:
                pass

        results = calculate_scatter(x_raw, y_raw)

        if not results:
            return render_template(
                'index.html',
                insight="❌ Scatter Diagram requires valid numeric data in both columns.",
                system_status="error",
                selected_chart=chart_type
            )

        clean_x = results['x']
        clean_y = results['y']
        count = results['count']
        correlation = results['correlation']
        x_min = results['x_min']
        x_max = results['x_max']
        y_min = results['y_min']
        y_max = results['y_max']

        # INSIGHTS
        analysis_messages = [
            "✅ Scatter Diagram generated successfully",
            f"ℹ️ Valid pairs: {count}",
            f"ℹ️ Pearson Correlation (r): {correlation:.4f}",
            f"ℹ️ X Range: [{x_min:.4f}, {x_max:.4f}]",
            f"ℹ️ Y Range: [{y_min:.4f}, {y_max:.4f}]"
        ]
        insight = "<br>".join(analysis_messages)

        # PLOT
        fig = go.Figure()
        chart_title = f"{chart_name} - Scatter Diagram" if chart_name else "Scatter Diagram"
        
        fig.add_trace(
            go.Scatter(
                x=clean_x,
                y=clean_y,
                mode='markers',
                name='Data Points',
                marker=dict(
                    color='#3B82F6',
                    size=8,
                    line=dict(color='white', width=1)
                )
            )
        )

        fig.update_xaxes(title_text=str(df.columns[0]))
        fig.update_yaxes(title_text=str(df.columns[1]))

    # =====================================================
    # BOX PLOT
    # =====================================================

    elif chart_type == "box_plot":

        data = df.iloc[:, 0].values

        if not np.issubdtype(data.dtype, np.number):
            try:
                data = pd.to_numeric(data, errors='coerce')
            except Exception:
                pass

        results = calculate_boxplot(data)

        if not results:
            return render_template(
                'index.html',
                insight="❌ Box Plot requires numeric data.",
                system_status="error",
                selected_chart=chart_type
            )

        clean_data = results['data']
        count = results['count']
        median = results['median']
        iqr = results['iqr']
        outlier_count = results['outlier_count']

        # INSIGHTS
        analysis_messages = [
            "✅ Box Plot generated successfully",
            f"ℹ️ Valid numeric observations: {count}",
            f"ℹ️ Median: {median:.4f} | IQR: {iqr:.4f}",
            f"⚠️ Potential Outliers: {outlier_count}" if outlier_count > 0 else "✅ No extreme outliers detected."
        ]
        insight = "<br>".join(analysis_messages)

        # PLOT
        fig = go.Figure()
        chart_title = f"{chart_name} - Box Plot" if chart_name else "Box Plot"
        
        fig.add_trace(
            go.Box(
                y=clean_data,
                name='Distribution',
                marker_color='#3B82F6',
                boxpoints='outliers'
            )
        )

    # =====================================================
    # PARETO CHART
    # =====================================================

    elif chart_type == "pareto":

        results = calculate_pareto(df)

        if not results:
            return render_template(
                'index.html',
                insight="❌ Pareto Chart requires valid categorical data (or category-frequency pairs).",
                system_status="error",
                selected_chart=chart_type
            )

        categories = results['categories']
        frequencies = results['frequencies']
        cum_pct = results['cum_pct']
        total_count = results['total_count']
        num_categories = len(categories)

        # INSIGHTS
        top_80 = [c for c, p in zip(categories, cum_pct) if p <= 80]
        if not top_80 and cum_pct:
            top_80 = [categories[0]]
            
        analysis_messages = [
            "✅ Pareto Chart generated successfully",
            f"ℹ️ Total Data Points/Frequency: {total_count}",
            f"ℹ️ Number of Categories: {num_categories}",
            f"⚠️ 'Vital Few' (Top ~80%): {', '.join(top_80)}"
        ]
        insight = "<br>".join(analysis_messages)

        # PLOT
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        chart_title = f"{chart_name} - Pareto Chart" if chart_name else "Pareto Chart"
        
        fig.add_trace(
            go.Bar(
                x=categories,
                y=frequencies,
                name='Frequency',
                marker_color='#3B82F6',
                opacity=0.85
            ),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(
                x=categories,
                y=cum_pct,
                name='Cumulative %',
                mode='lines+markers',
                line=dict(color='#F59E0B', width=3),
                marker=dict(color='#F59E0B', size=8)
            ),
            secondary_y=True
        )

        fig.update_yaxes(title_text="Frequency", secondary_y=False)
        fig.update_yaxes(
            title_text="Cumulative %", 
            range=[0, 105], 
            secondary_y=True,
            showgrid=False
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

    SINGLE_CHART_TYPES = {'p_chart', 'np_chart', 'c_chart', 'u_chart', 'histogram', 'scatter', 'box_plot', 'pareto'}
    is_single_chart = chart_type in SINGLE_CHART_TYPES

    # =====================================================
    # COMMON LAYOUT  –  SPC Insights theme
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
        # Only restyle lines/markers if trace is a Scatter plot, skip Histograms
        if trace.type == 'scatter':
            # Skip restyling for pareto cumulative percentage line
            if getattr(trace, 'name', '') == 'Cumulative %':
                continue

            if hasattr(trace, 'line'):
                trace.line.color = CLR_DATA_LINE
                trace.line.width = 2
            
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
                text="SPC Insights • AIQM India",
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
        margin=dict(
            l=48 if is_single_chart else 64, 
            r=80 if is_single_chart else 120, 
            t=80, 
            b=56
        ),
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

    if current_user.monthly_chart_limit != -1:
        current_user.charts_used_this_month += 1
        db.session.commit()

    return render_template(
        'index.html',
        graph=graph_html,
        insight=insight,
        warning=warning,
        is_single_chart=is_single_chart,
        system_status="processing",
        selected_chart=chart_type,
        now=datetime.utcnow()
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

@spc_bp.route("/export_check_sheet_pdf", methods=["POST"])
@login_required
def export_check_sheet_pdf():
    data = request.get_json()
    if not data or 'counters' not in data:
        return jsonify({'error': 'Invalid data provided'}), 400

    counters_data = data['counters']

    user_reports_dir = os.path.join(REPORTS_BASE, f"user_{current_user.id}")
    os.makedirs(user_reports_dir, exist_ok=True)
    
    output_pdf = os.path.join(user_reports_dir, "check_sheet_report.pdf")

    try:
        generate_check_sheet_pdf(counters_data, output_pdf)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return send_file(
        output_pdf,
        as_attachment=True,
        download_name="check_sheet_report.pdf",
        mimetype="application/pdf"
    )
