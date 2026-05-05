from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)

# Folder setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# Home route
@app.route('/')
def index():
    return render_template('index.html')


# Upload + process
@app.route('/upload', methods=['POST'])
def upload_file():

    if 'file' not in request.files:
        return "❌ No file part in request"

    file = request.files['file']

    if file.filename == "":
        return "❌ No file selected"

    chart_type = request.form['chart']
    subgroup_size = int(request.form['subgroup_size'])

    # Save file
    filename = secure_filename(file.filename)
    unique_name = str(int(time.time())) + "_" + filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    try:
        file.save(filepath)
    except PermissionError:
        return "❌ Please close the Excel file before uploading"

    # Read file
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    # Convert to numeric
    df = df.apply(pd.to_numeric, errors='coerce')

    if df.isnull().values.any():
        return "❌ Data must be numeric and without empty cells"

    # Prepare subgroups
    data = df.iloc[:, 0].values

    if len(data) < subgroup_size:
        return "❌ Not enough data for subgrouping"

    usable_length = len(data) - (len(data) % subgroup_size)
    data = data[:usable_length]

    subgroups = data.reshape(-1, subgroup_size)
    n = subgroup_size

    # Constants
    A2_table = {2:1.88, 3:1.023, 4:0.729, 5:0.577}
    D3_table = {2:0, 3:0, 4:0, 5:0}
    D4_table = {2:3.267, 3:2.574, 4:2.282, 5:2.114}

    A3_table = {2:2.659, 3:1.954, 4:1.628, 5:1.427}
    B3_table = {2:0, 3:0, 4:0, 5:0}
    B4_table = {2:3.267, 3:2.568, 4:2.266, 5:2.089}

    # =========================
    # XBAR-R CHART
    # =========================
    if chart_type == "xbar_r":

        if n not in A2_table:
            return "❌ Unsupported subgroup size (use 2–5)"

        xbar = np.mean(subgroups, axis=1)
        R = np.max(subgroups, axis=1) - np.min(subgroups, axis=1)

        xbar_bar = np.mean(xbar)
        R_bar = np.mean(R)

        A2 = A2_table[n]
        D3 = D3_table[n]
        D4 = D4_table[n]

        UCL_xbar = xbar_bar + A2 * R_bar
        LCL_xbar = xbar_bar - A2 * R_bar

        UCL_R = D4 * R_bar
        LCL_R = D3 * R_bar

        # Detect
        out_x = (xbar > UCL_xbar) | (xbar < LCL_xbar)
        out_r = (R > UCL_R) | (R < LCL_R)

        total_out = np.sum(out_x) + np.sum(out_r)

        if total_out > 0:
            insight = f"⚠️ {total_out} point(s) out of control → Process is NOT stable"
        else:
            insight = "✅ Process is stable"

        # Plot
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("X̄ Chart", "R Chart")
        )

        fig.add_trace(go.Scatter(
            y=xbar,
            mode='lines+markers',
            marker=dict(color=['red' if v else 'blue' for v in out_x])
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            y=R,
            mode='lines+markers',
            marker=dict(color=['red' if v else 'blue' for v in out_r])
        ), row=2, col=1)

        fig.add_hline(y=xbar_bar, row=1, col=1, line_color="green")
        fig.add_hline(y=UCL_xbar, row=1, col=1, line_color="red")
        fig.add_hline(y=LCL_xbar, row=1, col=1, line_color="red")

        fig.add_hline(y=R_bar, row=2, col=1, line_color="green")
        fig.add_hline(y=UCL_R, row=2, col=1, line_color="red")
        fig.add_hline(y=LCL_R, row=2, col=1, line_color="red")

        fig.update_layout(height=700, title=f"X̄-R Control Chart (n={n})")

    # =========================
    # XBAR-S CHART
    # =========================
    elif chart_type == "xbar_s":

        if n not in A3_table:
            return "❌ Unsupported subgroup size for Xbar-S"

        xbar = np.mean(subgroups, axis=1)
        S = np.std(subgroups, axis=1, ddof=1)

        xbar_bar = np.mean(xbar)
        S_bar = np.mean(S)

        A3 = A3_table[n]
        B3 = B3_table[n]
        B4 = B4_table[n]

        UCL_xbar = xbar_bar + A3 * S_bar
        LCL_xbar = xbar_bar - A3 * S_bar

        UCL_S = B4 * S_bar
        LCL_S = B3 * S_bar

        # Detect
        out_x = (xbar > UCL_xbar) | (xbar < LCL_xbar)
        out_s = (S > UCL_S) | (S < LCL_S)

        total_out = np.sum(out_x) + np.sum(out_s)

        if total_out > 0:
            insight = f"⚠️ {total_out} point(s) out of control → Process is NOT stable"
        else:
            insight = "✅ Process is stable"

        # Plot
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("X̄ Chart", "S Chart")
        )

        fig.add_trace(go.Scatter(
            y=xbar,
            mode='lines+markers',
            marker=dict(color=['red' if v else 'blue' for v in out_x])
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            y=S,
            mode='lines+markers',
            marker=dict(color=['red' if v else 'blue' for v in out_s])
        ), row=2, col=1)

        fig.add_hline(y=xbar_bar, row=1, col=1, line_color="green")
        fig.add_hline(y=UCL_xbar, row=1, col=1, line_color="red")
        fig.add_hline(y=LCL_xbar, row=1, col=1, line_color="red")

        fig.add_hline(y=S_bar, row=2, col=1, line_color="green")
        fig.add_hline(y=UCL_S, row=2, col=1, line_color="red")
        fig.add_hline(y=LCL_S, row=2, col=1, line_color="red")

        fig.update_layout(height=700, title=f"X̄-S Control Chart (n={n})")

    else:
        return "❌ Invalid chart type selected"

    graph_html = fig.to_html(full_html=False)
    os.remove(filepath)  # delete file after processing
    return render_template('index.html', graph=graph_html, insight=insight)


# Run app
if __name__ == '__main__':
    print("🚀 Starting SPC Server...")
    print("👉 Open http://127.0.0.1:5000 in browser")
    app.run(debug=True)