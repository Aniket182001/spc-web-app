import numpy as np
from spc_constants import (
    A2_TABLE,
    D3_TABLE,
    D4_TABLE,
    A3_TABLE,
    B3_TABLE,
    B4_TABLE
)

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

def calculate_xbar_r(data, subgroup_size, usl_input=None, lsl_input=None):
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

    xbar = np.mean(subgroups, axis=1)
    R = np.max(subgroups, axis=1) - np.min(subgroups, axis=1)

    xbar_bar = np.mean(xbar)
    R_bar = np.mean(R)

    A2 = A2_TABLE[n]
    D3 = D3_TABLE[n]
    D4 = D4_TABLE[n]

    UCL_xbar = xbar_bar + (A2 * R_bar)
    LCL_xbar = xbar_bar - (A2 * R_bar)

    UCL_R = D4 * R_bar
    LCL_R = D3 * R_bar

    process_std = np.std(data, ddof=1)

    if usl_input is not None and lsl_input is not None:
        usl = float(usl_input)
        lsl = float(lsl_input)
    else:
        usl = xbar_bar + (3 * process_std)
        lsl = xbar_bar - (3 * process_std)

    out_x = ((xbar > UCL_xbar) | (xbar < LCL_xbar))
    out_r = ((R > UCL_R) | (R < LCL_R))

    return {
        'xbar': xbar,
        'R': R,
        'xbar_bar': xbar_bar,
        'R_bar': R_bar,
        'UCL_xbar': UCL_xbar,
        'LCL_xbar': LCL_xbar,
        'UCL_R': UCL_R,
        'LCL_R': LCL_R,
        'usl': usl,
        'lsl': lsl,
        'out_x': out_x,
        'out_r': out_r,
        'dropped_points': dropped_points,
        'dropped_values': dropped_values,
        'n': n
    }

def calculate_xbar_s(data, subgroup_size, usl_input=None, lsl_input=None):
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

    xbar = np.mean(subgroups, axis=1)
    S = np.std(subgroups, axis=1, ddof=1)

    xbar_bar = np.mean(xbar)
    S_bar = np.mean(S)

    A3 = A3_TABLE[n]
    B3 = B3_TABLE[n]
    B4 = B4_TABLE[n]

    UCL_xbar = xbar_bar + (A3 * S_bar)
    LCL_xbar = xbar_bar - (A3 * S_bar)

    UCL_S = B4 * S_bar
    LCL_S = B3 * S_bar

    process_std = np.std(data, ddof=1)

    if usl_input is not None and lsl_input is not None:
        usl = float(usl_input)
        lsl = float(lsl_input)
    else:
        usl = xbar_bar + (3 * process_std)
        lsl = xbar_bar - (3 * process_std)

    out_x = ((xbar > UCL_xbar) | (xbar < LCL_xbar))
    out_s = ((S > UCL_S) | (S < LCL_S))

    return {
        'xbar': xbar,
        'S': S,
        'xbar_bar': xbar_bar,
        'S_bar': S_bar,
        'UCL_xbar': UCL_xbar,
        'LCL_xbar': LCL_xbar,
        'UCL_S': UCL_S,
        'LCL_S': LCL_S,
        'usl': usl,
        'lsl': lsl,
        'out_x': out_x,
        'out_s': out_s,
        'dropped_points': dropped_points,
        'dropped_values': dropped_values,
        'n': n
    }

def calculate_p_chart(defectives, sample_sizes):
    p_values = defectives / sample_sizes
    p_bar = np.sum(defectives) / np.sum(sample_sizes)

    UCL = p_bar + (3 * np.sqrt((p_bar * (1 - p_bar)) / sample_sizes))
    LCL = p_bar - (3 * np.sqrt((p_bar * (1 - p_bar)) / sample_sizes))
    LCL = np.maximum(LCL, 0)

    out_p = ((p_values > UCL) | (p_values < LCL))

    return {
        'p_values': p_values,
        'p_bar': p_bar,
        'UCL': UCL,
        'LCL': LCL,
        'out_p': out_p
    }

def calculate_np_chart(defectives, sample_size):
    p_bar = np.mean(defectives) / sample_size
    np_values = defectives

    CL = sample_size * p_bar
    sigma = np.sqrt(sample_size * p_bar * (1 - p_bar))

    UCL = CL + (3 * sigma)
    LCL = CL - (3 * sigma)
    LCL = max(LCL, 0)

    out_np = ((np_values > UCL) | (np_values < LCL))

    return {
        'np_values': np_values,
        'CL': CL,
        'UCL': UCL,
        'LCL': LCL,
        'out_np': out_np
    }

def calculate_c_chart(c_values):
    c_bar = np.mean(c_values)

    UCL = c_bar + (3 * np.sqrt(c_bar))
    LCL = c_bar - (3 * np.sqrt(c_bar))
    LCL = max(LCL, 0)

    out_c = ((c_values > UCL) | (c_values < LCL))

    return {
        'c_values': c_values,
        'c_bar': c_bar,
        'UCL': UCL,
        'LCL': LCL,
        'out_c': out_c
    }

def calculate_u_chart(defects, sample_sizes):
    u_values = defects / sample_sizes
    u_bar = np.sum(defects) / np.sum(sample_sizes)

    UCL = u_bar + (3 * np.sqrt(u_bar / sample_sizes))
    LCL = u_bar - (3 * np.sqrt(u_bar / sample_sizes))
    LCL = np.maximum(LCL, 0)

    out_u = ((u_values > UCL) | (u_values < LCL))

    return {
        'u_values': u_values,
        'u_bar': u_bar,
        'UCL': UCL,
        'LCL': LCL,
        'out_u': out_u
    }

def calculate_imr_chart(data, usl_input=None, lsl_input=None):
    individual_values = data
    moving_ranges = np.abs(np.diff(individual_values))

    x_bar = np.mean(individual_values)
    mr_bar = np.mean(moving_ranges)

    UCL_X = x_bar + (2.66 * mr_bar)
    LCL_X = x_bar - (2.66 * mr_bar)

    UCL_MR = 3.267 * mr_bar
    LCL_MR = 0

    process_std = np.std(data, ddof=1)

    if usl_input is not None and lsl_input is not None:
        usl = float(usl_input)
        lsl = float(lsl_input)
    else:
        usl = x_bar + (3 * process_std)
        lsl = x_bar - (3 * process_std)

    out_x = ((individual_values > UCL_X) | (individual_values < LCL_X))
    out_mr = ((moving_ranges > UCL_MR) | (moving_ranges < LCL_MR))

    return {
        'individual_values': individual_values,
        'moving_ranges': moving_ranges,
        'x_bar': x_bar,
        'mr_bar': mr_bar,
        'UCL_X': UCL_X,
        'LCL_X': LCL_X,
        'UCL_MR': UCL_MR,
        'LCL_MR': LCL_MR,
        'usl': usl,
        'lsl': lsl,
        'out_x': out_x,
        'out_mr': out_mr
    }
