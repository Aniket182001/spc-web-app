from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import os
from werkzeug.utils import secure_filename
import time
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Home page
@app.route('/')
def index():
    return render_template('index.html')


# Handle upload + chart
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    chart_type = request.form['chart']

    # Secure filename
    filename = secure_filename(file.filename)

    # Add timestamp to avoid overwrite
    unique_name = str(int(time.time())) + "_" + filename

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    # ✅ TRY-EXCEPT HERE
    try:
        file.save(filepath)
    except PermissionError:
        return "❌ Please close the Excel file before uploading"

    df = pd.read_excel(filepath)

    # Subgroups
    subgroups = df.values

    xbar = np.mean(subgroups, axis=1)
    R = np.max(subgroups, axis=1) - np.min(subgroups, axis=1)

    xbar_bar = np.mean(xbar)
    R_bar = np.mean(R)
n = subgroups.shape[1]

A2_table = {2:1.88, 3:1.023, 4:0.729, 5:0.577}
D3_table = {2:0, 3:0, 4:0, 5:0}
D4_table = {2:3.267, 3:2.574, 4:2.282, 5:2.114}

A2 = A2_table.get(n, 0.577)
D3 = D3_table.get(n, 0)
D4 = D4_table.get(n, 2.114)

UCL_R = D4 * R_bar
LCL_R = D3 * R_bar

UCL_xbar = xbar_bar + A2 * R_bar
LCL_xbar = xbar_bar - A2 * R_bar

# Create 2 rows (Xbar + R)
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    subplot_titles=("X̄ Chart", "R Chart")
)

# ---- Xbar Chart ----
fig.add_trace(
    go.Scatter(y=xbar, mode='lines+markers', name='Xbar'),
    row=1, col=1
)

fig.add_hline(y=xbar_bar, row=1, col=1, line_dash="dash", annotation_text="Mean")
fig.add_hline(y=UCL_xbar, row=1, col=1, line_dash="dash", annotation_text="UCL")
fig.add_hline(y=LCL_xbar, row=1, col=1, line_dash="dash", annotation_text="LCL")

# ---- R Chart ----
fig.add_trace(
    go.Scatter(y=R, mode='lines+markers', name='R'),
    row=2, col=1
)

fig.add_hline(y=R_bar, row=2, col=1, line_dash="dash", annotation_text="R̄")
fig.add_hline(y=UCL_R, row=2, col=1, line_dash="dash", annotation_text="UCL")
fig.add_hline(y=LCL_R, row=2, col=1, line_dash="dash", annotation_text="LCL")

# Layout
fig.update_layout(height=700, title="X̄-R Control Chart")

graph_html = fig.to_html(full_html=False)
    return render_template('chart.html', graph_html=graph_html)

if __name__ == '__main__':
    print("🚀 Starting SPC Server...")
    print("👉 Open http://127.0.0.1:5000 in browser")
    app.run(debug=True)