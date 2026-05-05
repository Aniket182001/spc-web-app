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
    
    file = request.files['file']
    chart_type = request.form['chart']

    # Save file safely
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

    # Validation
    if df.isnull().values.any():
        return "❌ Data contains empty cells"

    # Convert everything to numeric (force)
    df = df.apply(pd.to_numeric, errors='coerce')

    # Check for invalid or empty values
    if df.isnull().values.any():
        return "❌ Data must be numeric and without empty cells"

    # Subgroups
    subgroups = df.values
    n = subgroups.shape[1]

    # Constants
    A2_table = {2:1.88, 3:1.023, 4:0.729, 5:0.577}
    D3_table = {2:0, 3:0, 4:0, 5:0}
    D4_table = {2:3.267, 3:2.574, 4:2.282, 5:2.114}

    if n not in A2_table:
        return "❌ Unsupported subgroup size (use 2–5 columns)"

    # Only Xbar-R for now
    if chart_type == "xbar_r":

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

        # Detect out-of-control points
        out_of_control_x = (xbar > UCL_xbar) | (xbar < LCL_xbar)
        out_of_control_r = (R > UCL_R) | (R < LCL_R)

        # Plot
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("X̄ Chart", "R Chart")
        )

        # Xbar chart
        fig.add_trace(
        go.Scatter(
        y=xbar,
        mode='lines+markers',
        name='Xbar',
        marker=dict(
            color=['red' if val else 'blue' for val in out_of_control_x]
        )
    ),
    row=1, col=1
)

        fig.add_hline(y=xbar_bar, row=1, col=1, line_color="green", annotation_text="Mean")
        fig.add_hline(y=UCL_xbar, row=1, col=1, line_color="red", annotation_text="UCL")
        fig.add_hline(y=LCL_xbar, row=1, col=1, line_color="red", annotation_text="LCL")

        # Axis labels
        fig.update_xaxes(title_text="Subgroup", row=2, col=1)
        fig.update_yaxes(title_text="X̄ Values", row=1, col=1)
        fig.update_yaxes(title_text="Range", row=2, col=1)

        # R chart
        fig.add_trace(
        go.Scatter(
        y=R,
        mode='lines+markers',
        name='R',
        marker=dict(
            color=['red' if val else 'blue' for val in out_of_control_r]
        )
    ),
    row=2, col=1
)

        fig.add_hline(y=R_bar, row=2, col=1, line_color="green", annotation_text="R̄")
        fig.add_hline(y=UCL_R, row=2, col=1, line_color="red", annotation_text="UCL")
        fig.add_hline(y=LCL_R, row=2, col=1, line_color="red", annotation_text="LCL")

        # Axis labels
        fig.update_xaxes(title_text="Subgroup", row=2, col=1)
        fig.update_yaxes(title_text="X̄ Values", row=1, col=1)
        fig.update_yaxes(title_text="Range", row=2, col=1)

        fig.update_layout(height=700, title="X̄-R Control Chart")

        graph_html = fig.to_html(full_html=False)

        return render_template('index.html', graph=graph_html)

    else:
        return "❌ Only Xbar-R chart supported currently"


# Run app
if __name__ == '__main__':
    print("🚀 Starting SPC Server...")
    print("👉 Open http://127.0.0.1:5000 in browser")
    app.run(debug=True)