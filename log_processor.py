import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from collections import defaultdict
import numpy as np
from scipy.fftpack import fft, fftfreq
from scipy.signal import butter, filtfilt, welch

def find_csv_files(directory_path):
    csv_files = defaultdict(lambda: {'Area_1': [], 'Area_2': []})
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".csv"):
                full_path = os.path.join(root, file)
                path_parts = root.split(os.sep)
                if len(path_parts) >= 2:
                    wheel_type_area = path_parts[-1]
                    wheel_type, area = wheel_type_area.split('-Area_')
                    area_key = f"Area_{area}"
                    csv_files[wheel_type][area_key].append(full_path)
    return csv_files

def read_csv_data(csv_files):
    data_frames = defaultdict(lambda: {'Area_1': [], 'Area_2': []})
    for wheel_type, areas in csv_files.items():
        for area, files in areas.items():
            for file_path in files:
                try:
                    df = pd.read_csv(file_path)
                    data_frames[wheel_type][area].append(df)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
    return data_frames

def normalize_time(df_list, time_column='Timestamp'):
    for df in df_list:
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column])
    min_time = min(df[time_column].min() for df in df_list)
    for df in df_list:
        df['Normalized_Time'] = (df[time_column] - min_time).dt.total_seconds()
    return df_list

def calculate_linear_acceleration_magnitude(df, ax_column='Linear_Accel_X', ay_column='Linear_Accel_Y', az_column='Linear_Accel_Z'):
    df['Linear_Accel'] = np.sqrt(df[ax_column]**2 + df[ay_column]**2 + df[az_column]**2)
    return df

def normalize_and_calculate_linear_accel(data_frames):
    for wheel_type, areas in data_frames.items():
        for area, df_list in areas.items():
            df_list = normalize_time(df_list)
            for df in df_list:
                df = calculate_linear_acceleration_magnitude(df)
    return data_frames

def plot_combined_distribution(data_frames, output_dir, column_name, title, show_bars=True, areas=['Area_1', 'Area_2']):
    wheel_types = data_frames.keys()
    os.makedirs(output_dir, exist_ok=True)

    for area in areas:
        plt.figure(figsize=(30, 8), dpi=1200)
        
        for wheel_type in wheel_types:
            all_values = []
            for df in data_frames[wheel_type][area]:
                all_values.extend(df[column_name])
            
            mean_value = sum(all_values) / len(all_values) if all_values else 0
            print(f"Mean {column_name} for {wheel_type} in {area}: {mean_value}")
            
            if show_bars:
                sns.histplot(all_values, kde=True, bins=50, label=wheel_type, alpha=0.5)
            else:
                sns.kdeplot(all_values, label=wheel_type, linewidth=5)

            current_color = sns.color_palette()[list(wheel_types).index(wheel_type)]
            plt.axvline(mean_value, color=current_color, linestyle='--', linewidth=5, label=f'{wheel_type} Mean')

        plt.title(f'{title} in {area}', fontsize=48, fontweight='bold')
        plt.xlabel(column_name, fontsize=44)
        plt.ylabel('Density', fontsize=44)
        # --- Start of changes for the legend ---
        legend = plt.legend(title='Wheel Type', fontsize=36)
        plt.setp(legend.get_title(), fontsize=40, fontweight='bold')
        # for text in legend.get_texts():
        #     text.set_fontweight('bold')
        # --- End of changes for the legend ---
        plt.grid(True)
        plt.xticks(fontsize= 44)
        plt.yticks(fontsize=44)
        plt.tight_layout()
        
        output_path = os.path.join(output_dir, f'{title}_{area}.pdf')
        plt.savefig(output_path)
        plt.close()

    print(f"Plots saved to {output_dir}")

def highpass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='high', analog=False)
    filtered_data = filtfilt(b, a, data)
    return filtered_data

def plot_fourier_transform(data_frames, output_dir, time_column='Normalized_Time', value_column='Linear_Accel', areas=['Area_1', 'Area_2'], cutoff_frequency=0.5):
    wheel_types = data_frames.keys()
    os.makedirs(output_dir, exist_ok=True)

    for area in areas:
        plt.figure(figsize=(30, 11), dpi=1200)
        
        for wheel_type in wheel_types:
            aggregated_values = []
            for df in data_frames[wheel_type][area]:
                values = df[value_column].to_numpy()
                values = values - np.mean(values)  # Remove DC component
                T = np.mean(np.diff(df[time_column]))  # Sampling interval
                
                # High-pass filtering
                fs = 1.0 / T  # Sampling frequency
                values = highpass_filter(values, cutoff_frequency, fs)
                
                aggregated_values.extend(values)
            
            aggregated_values = np.array(aggregated_values)

            # Perform Fourier Transform
            N = len(aggregated_values)
            yf = fft(aggregated_values)
            xf = fftfreq(N, T)[:N//2]

            # Plot the Fourier Transform magnitude
            plt.plot(xf, 2.0/N * np.abs(yf[:N//2]), label=wheel_type)

        plt.title(f'Fourier Transform of {value_column} in {area}', fontsize=48, fontweight='bold')
        plt.xlabel('Frequency [Hz]', fontsize=44)
        plt.ylabel('Amplitude', fontsize=44)
        # --- Start of changes for the legend ---
        legend = plt.legend(title='Wheel Type', fontsize=44)
        plt.setp(legend.get_title(), fontsize=48, fontweight='bold')
        # for text in legend.get_texts():
        #     text.set_fontweight('bold')
        # --- End of changes for the legend ---
        plt.grid(True)
        plt.xticks(fontsize= 44)
        plt.yticks(fontsize=44)
        plt.tight_layout()
        
        output_path = os.path.join(output_dir, f'Fourier_Transform_{value_column}_{area}.pdf')
        plt.savefig(output_path)
        plt.close()

    print(f"Fourier Transform plots saved to {output_dir}")


def plot_psd(data_frames, output_dir, time_column='Normalized_Time', value_column='Linear_Accel', areas=['Area_1', 'Area_2'], cutoff_frequency=0.5):
    wheel_types = data_frames.keys()
    os.makedirs(output_dir, exist_ok=True)

    for area in areas:
        plt.figure(figsize=(30, 12), dpi=1200)
        
        for wheel_type in wheel_types:
            aggregated_values = []
            for df in data_frames[wheel_type][area]:
                values = df[value_column].to_numpy()
                
                # Subtract the mean to remove DC component
                values = values - np.mean(values)
                
                # Apply high-pass filter to remove low-frequency drift
                T = np.mean(np.diff(df[time_column]))  # Sampling interval
                fs = 1.0 / T  # Sampling frequency
                values = highpass_filter(values, cutoff_frequency, fs)
                
                aggregated_values.extend(values)
            
            # Convert to numpy array
            aggregated_values = np.array(aggregated_values)
            
            # Compute the PSD using Welch's method with adjusted parameters
            f, Pxx = welch(aggregated_values, fs, nperseg=1024, noverlap=512, scaling='density')
            
            # Plot the PSD
            plt.plot(f, Pxx, label=wheel_type, linewidth=5)

        plt.xlim(0, 31)  # Focus on the 0-50 Hz range
        plt.title(f'Power Spectral Density of {value_column} in {area}', fontsize=48, fontweight='bold')
        plt.xlabel('Frequency [Hz]', fontsize=44)
        plt.ylabel('Power Spectral Density [$V^2$/Hz]  ', fontsize=44)
        # --- Start of changes for the legend ---
        legend = plt.legend(title='Wheel Type', fontsize=44)
        plt.setp(legend.get_title(), fontsize=48, fontweight='bold')
        # for text in legend.get_texts():
        #     text.set_fontweight('bold')
        # --- End of changes for the legend ---
        plt.grid(True)
        plt.xticks(fontsize= 44)
        plt.yticks(fontsize=44)
        plt.tight_layout()
        
        output_path = os.path.join(output_dir, f'PSD_{value_column}_{area}.pdf')
        plt.savefig(output_path)
        plt.close()

    print(f"PSD plots saved to {output_dir}")

# Main function
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python find_csv_files.py <directory_path> <output_directory>")
        sys.exit(1)

    path = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)

    if not os.path.isdir(path):
        print(f"Error: The path '{path}' is not a valid directory.")
        sys.exit(1)

    csv_files = find_csv_files(path)
    data_frames = read_csv_data(csv_files)

    # Normalize time and calculate linear acceleration magnitude
    data_frames = normalize_and_calculate_linear_accel(data_frames)

    # Plot the average current distribution
    plot_combined_distribution(data_frames, output_dir, 'Current_mA', 'Current Distribution', show_bars=False)

    # Fourier series of the linear acceleration for the three wheel types
    plot_fourier_transform(data_frames, output_dir)

    # Power spectral density (PSD) plot of linear acceleration magnitude for the three wheel types
    plot_psd(data_frames, output_dir)

