"""
Basic QC Engine
"""
import numpy as np
import pandas as pd

def calculate_histogram(data):
    """
    Computes basic statistics for a histogram.
    Expects data to be a numeric numpy array.
    """
    # Filter out NaNs
    clean_data = data[~np.isnan(data)]
    
    count = len(clean_data)
    if count == 0:
        return None
        
    mean = np.mean(clean_data)
    std_dev = np.std(clean_data, ddof=1) if count > 1 else 0
    min_val = np.min(clean_data)
    max_val = np.max(clean_data)
    
    return {
        "data": clean_data,
        "count": count,
        "mean": mean,
        "std_dev": std_dev,
        "min": min_val,
        "max": max_val
    }

def calculate_scatter(x_data, y_data):
    """
    Computes basic statistics for a scatter diagram.
    Expects x_data and y_data to be numeric numpy arrays.
    """
    # Ensure they have the same length
    min_len = min(len(x_data), len(y_data))
    x_data = x_data[:min_len]
    y_data = y_data[:min_len]

    # Filter out NaNs from both simultaneously
    mask = ~np.isnan(x_data) & ~np.isnan(y_data)
    clean_x = x_data[mask]
    clean_y = y_data[mask]

    count = len(clean_x)
    if count == 0:
        return None

    # Calculate correlation (handle edge cases where variance is 0 or count < 2)
    if count > 1 and np.std(clean_x) > 0 and np.std(clean_y) > 0:
        correlation = np.corrcoef(clean_x, clean_y)[0, 1]
    else:
        correlation = 0.0

    return {
        "x": clean_x,
        "y": clean_y,
        "count": count,
        "correlation": correlation,
        "x_min": np.min(clean_x),
        "x_max": np.max(clean_x),
        "y_min": np.min(clean_y),
        "y_max": np.max(clean_y)
    }

def calculate_boxplot(data):
    """
    Computes basic statistics for a box plot.
    Expects data to be a numeric numpy array.
    """
    clean_data = data[~np.isnan(data)]
    
    count = len(clean_data)
    if count == 0:
        return None
        
    q1 = np.percentile(clean_data, 25)
    median = np.median(clean_data)
    q3 = np.percentile(clean_data, 75)
    iqr = q3 - q1
    
    # Typical outlier bounds
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    outliers = clean_data[(clean_data < lower_bound) | (clean_data > upper_bound)]
    
    return {
        "data": clean_data,
        "count": count,
        "median": median,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "outlier_count": len(outliers)
    }

def calculate_pareto(df):
    """
    Computes pareto statistics from a dataframe.
    Supports either:
      1 column: categorical data (will count frequencies)
      2 columns: categorical and numerical frequency
    """
    if df.shape[1] >= 2:
        # Format B: Two columns
        cat_col = df.columns[0]
        freq_col = df.columns[1]
        
        # Ensure freq is numeric, drop NaNs in frequencies
        df_clean = df.copy()
        df_clean[freq_col] = pd.to_numeric(df_clean[freq_col], errors='coerce')
        df_clean = df_clean.dropna(subset=[freq_col])
        
        # Group by category and sum
        grouped = df_clean.groupby(cat_col, dropna=True)[freq_col].sum().reset_index()
        grouped = grouped[grouped[freq_col] > 0]
        
    else:
        # Format A: One column
        cat_col = df.columns[0]
        df_clean = df.dropna(subset=[cat_col])
        
        counts = df_clean[cat_col].value_counts().reset_index()
        grouped = counts
        grouped.columns = [cat_col, 'frequency']
        freq_col = 'frequency'

    if grouped.empty:
        return None

    # Sort descending
    grouped = grouped.sort_values(by=freq_col, ascending=False).reset_index(drop=True)
    
    total = grouped[freq_col].sum()
    if total <= 0:
        return None
        
    grouped['cum_sum'] = grouped[freq_col].cumsum()
    grouped['cum_pct'] = (grouped['cum_sum'] / total) * 100.0
    
    return {
        "categories": grouped[cat_col].astype(str).tolist(),
        "frequencies": grouped[freq_col].tolist(),
        "cum_pct": grouped['cum_pct'].tolist(),
        "total_count": total
    }
