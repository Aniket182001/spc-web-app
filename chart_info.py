from flask import Blueprint, abort, render_template
from flask_login import login_required


VARIABLE_CHART_RULES = [
    "One point outside the UCL or the LCL.",
    "Seven (or nine) points in a row on the same side of the center line.",
    "Six points (or eight) in a row, all increasing or all decreasing.",
]

VARIABLE_CHART_NOTES = [
    "These charts are analyzed in pairs.",
    (
        "Before interpreting the Xbar chart, always check the dispersion "
        "chart (R, S, or MR) first."
    ),
    (
        "If variation (R, S, or MR) is out of control, the control limits "
        "on the process mean chart (Xbar or I) are invalid."
    ),
    (
        "The R, S, or MR chart measures the capability of the machine or "
        "process equipment, while the Xbar or I chart measures how well "
        "that process is being managed over time."
    ),
    (
        "These conditions are typical indications of an assignable cause "
        "variation."
    ),
]

ATTRIBUTE_CHART_RULES = [
    (
        "One point is more than 3 standard deviations (3σ) from the center "
        "line, outside the UCL or LCL."
    ),
    "Nine (or seven) consecutive points on the same side of the center line.",
    "Six consecutive points steadily increasing or decreasing.",
    "Fourteen consecutive points alternating up and down.",
]

ATTRIBUTE_CHART_NOTES = [
    "The most common triggers for investigation are listed below.",
]


CHART_INFO = {
    "xbar_r": {
        "dropdown_value": "xbar_r",
        "chart_type": "Xbar-R Chart",
        "data_type": "Variable/Continuous",
        "description": "Continuous data measured in subgroups.",
        "short_description": (
            "Continuous data measured in subgroups; monitors mean (Xbar) "
            "and variation (range)."
        ),
        "data_volume": "Medium or Small",
        "subgroup_size": "Small, generally 3 to 6",
        "monitors": "Mean (Xbar) and Variation (Range)",
        "interpretation_rules": VARIABLE_CHART_RULES,
        "practical_notes": VARIABLE_CHART_NOTES,
    },
    "xbar_s": {
        "dropdown_value": "xbar_s",
        "chart_type": "Xbar-S Chart",
        "data_type": "Variable/Continuous",
        "description": "Continuous data measured in subgroups.",
        "short_description": (
            "Continuous data measured in subgroups; monitors mean (Xbar) "
            "and variation (standard deviation)."
        ),
        "data_volume": "Large",
        "subgroup_size": "Generally more than 10",
        "monitors": "Mean (Xbar) and Variation (Standard Deviation)",
        "interpretation_rules": VARIABLE_CHART_RULES,
        "practical_notes": VARIABLE_CHART_NOTES,
    },
    "imr": {
        "dropdown_value": "imr_chart",
        "chart_type": "Xbar-MR Chart",
        "data_type": "Variable/Continuous",
        "description": (
            "Continuous data where measurements are taken one at a time."
        ),
        "short_description": (
            "Continuous data where measurements are taken one at a time; "
            "used when data collection is slow, expensive, or involves "
            "destructive testing."
        ),
        "data_volume": "Very few readings",
        "subgroup_size": None,
        "monitors": (
            "Used when data collection is slow, expensive, or involves "
            "destructive testing."
        ),
        "interpretation_rules": VARIABLE_CHART_RULES,
        "practical_notes": VARIABLE_CHART_NOTES,
    },
    "p_chart": {
        "dropdown_value": "p_chart",
        "chart_type": "P Chart",
        "data_type": "Attribute Data",
        "description": (
            "Tracks the proportion of defective units to total units. "
            'Control limits will "zigzag" when sample sizes vary.'
        ),
        "short_description": (
            "Tracks the proportion of defective units to total units; "
            "control limits will zigzag when sample sizes vary."
        ),
        "data_volume": None,
        "subgroup_size": "Subgroup size is not constant",
        "monitors": (
            "Tracks the capability of the process to yield acceptable "
            "products."
        ),
        "interpretation_rules": ATTRIBUTE_CHART_RULES,
        "practical_notes": ATTRIBUTE_CHART_NOTES,
    },
    "np_chart": {
        "dropdown_value": "np_chart",
        "chart_type": "NP Chart",
        "data_type": "Attribute Data",
        "description": (
            "Tracks the proportion of defective units to total units."
        ),
        "short_description": (
            "Tracks the proportion of defective units to total units with "
            "a constant subgroup size."
        ),
        "data_volume": None,
        "subgroup_size": "Subgroup size is constant",
        "monitors": (
            "Tracks the capability of the process to yield acceptable "
            "products."
        ),
        "interpretation_rules": ATTRIBUTE_CHART_RULES,
        "practical_notes": ATTRIBUTE_CHART_NOTES,
    },
    "u_chart": {
        "dropdown_value": "u_chart",
        "chart_type": "U Chart",
        "data_type": "Count Data",
        "description": "Tracks the fraction of defects to total units.",
        "short_description": (
            "Tracks the fraction of defects to total units when subgroup "
            "size is not constant."
        ),
        "data_volume": None,
        "subgroup_size": "Subgroup size is not constant",
        "monitors": "Tracks the absolute frequency of defect occurrences.",
        "interpretation_rules": ATTRIBUTE_CHART_RULES,
        "practical_notes": ATTRIBUTE_CHART_NOTES,
    },
    "c_chart": {
        "dropdown_value": "c_chart",
        "chart_type": "C Chart",
        "data_type": "Count Data",
        "description": "Tracks the fraction of defects to total units.",
        "short_description": (
            "Tracks the fraction of defects to total units when subgroup "
            "size is constant."
        ),
        "data_volume": None,
        "subgroup_size": "Subgroup size is constant",
        "monitors": "Tracks the absolute frequency of defect occurrences.",
        "interpretation_rules": ATTRIBUTE_CHART_RULES,
        "practical_notes": ATTRIBUTE_CHART_NOTES,
    },
}


chart_info_bp = Blueprint("chart_info", __name__)


@chart_info_bp.route("/chart-info/<chart_type>")
@login_required
def chart_info_detail(chart_type):
    chart = CHART_INFO.get(chart_type)

    if chart is None:
        abort(404)

    return render_template(
        "chart_info.html",
        chart=chart,
        chart_slug=chart_type,
        system_status="ready",
    )

