import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set clean academic typography & style
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.9

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    
    dist_csv = os.path.join(base_dir, "docs", "rajDocs4", "class_distribution.csv")
    rot_csv = os.path.join(base_dir, "docs", "rajDocs4", "rotational_robustness_results.csv")
    
    df_dist = pd.read_csv(dist_csv)
    df_rot = pd.read_csv(rot_csv)
    
    # Create 2-panel figure with balanced aspect ratio
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.0, 5.5), dpi=300)
    
    # -------------------------------------------------------------------------
    # PANEL (a): VALIDATION CLASS DISTRIBUTION (TOP 25 CLASSES)
    # -------------------------------------------------------------------------
    top25 = df_dist[df_dist['val_images'] > 0].sort_values(by='val_images', ascending=False).head(25)
    
    bars = ax1.bar(
        range(len(top25)),
        top25['val_images'],
        color='#2b5c8f',
        width=0.68,
        edgecolor='#1b3a5a',
        linewidth=0.8,
        zorder=3
    )
    
    ax1.set_xticks(range(len(top25)))
    ax1.set_xticklabels(top25['class_name'], rotation=45, ha='right', fontsize=8.5)
    ax1.set_xlabel('Class Names', fontsize=9.5, fontweight='bold', labelpad=6)
    ax1.set_ylabel('Validation Images Count', fontsize=9.5, fontweight='bold', labelpad=6)
    ax1.set_title('(a) Validation Class Distribution (Top 25 Represented Classes)', fontsize=10.5, fontweight='bold', pad=12)
    ax1.grid(axis='y', linestyle='--', alpha=0.45, zorder=1)
    ax1.set_ylim(0, max(top25['val_images']) * 1.14)
    ax1.set_xlim(-0.7, len(top25) - 0.3)
    
    # Compact representation brackets annotation box (upper-right corner)
    bracket_text = (
        "Representation Brackets (123 Classes):\n"
        "• >20 Images: 51 Classes\n"
        "• 5–20 Images: 5 Classes\n"
        "• <5 Images: 30 Classes\n"
        "• 0 Images: 37 Classes"
    )
    ax1.text(
        0.96, 0.94, bracket_text,
        transform=ax1.transAxes,
        fontsize=8.0,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#f8f9fa', edgecolor='#b0bec5', linewidth=0.8, alpha=0.95),
        zorder=4
    )
    
    # -------------------------------------------------------------------------
    # PANEL (b): ROTATIONAL INVARIANCE ROBUSTNESS (N=200 PLATE IMAGES)
    # -------------------------------------------------------------------------
    angles = [0, 90, 180, 270]
    angle_labels = ['0° (Baseline)', '90° (Clockwise)', '180° (Inverted)', '270° (Counter-CW)']
    
    # Exact measured values
    prec = df_rot['Precision'].values       # [0.8710, 0.8604, 0.8808, 0.8706]
    rec = df_rot['Recall'].values             # [0.8432, 0.8343, 0.8268, 0.8157]
    map50 = df_rot['mAP50'].values           # [0.8924, 0.8911, 0.8875, 0.8804]
    
    # Shaded stability band (descriptive region between min and max mAP50)
    ax2.axhspan(
        min(map50), max(map50),
        color='#16a34a',
        alpha=0.09,
        label='mAP@50 Stability (max Δ = 1.20 percentage points)',
        zorder=1
    )
    
    # Plot lines with distinct styles and markers
    ax2.plot(angles, map50, marker='s', markersize=7.5, color='#15803d', linewidth=2.2, linestyle='-', label='mAP@50 (IoU=0.50)', zorder=4)
    ax2.plot(angles, prec, marker='o', markersize=6.5, color='#1d4ed8', linewidth=1.8, linestyle='--', label='Precision', zorder=4)
    ax2.plot(angles, rec, marker='^', markersize=6.5, color='#b91c1c', linewidth=1.8, linestyle=':', label='Recall', zorder=4)
    
    # Show numerical mAP@50 values directly above the four data points
    for a, m in zip(angles, map50):
        ax2.annotate(
            f'{m:.4f}',
            (a, m),
            textcoords="offset points",
            xytext=(0, 8),
            ha='center',
            fontsize=8.5,
            fontweight='bold',
            color='#15803d',
            zorder=5
        )
        
    ax2.set_xticks(angles)
    ax2.set_xticklabels(angle_labels, fontsize=8.8)
    ax2.set_xlabel('Plate Rotation Angle', fontsize=9.5, fontweight='bold', labelpad=6)
    ax2.set_ylabel('Metric Score (0.0–1.0)', fontsize=9.5, fontweight='bold', labelpad=6)
    ax2.set_title('(b) Rotational Invariance Robustness (N=200 Plate Images)', fontsize=10.5, fontweight='bold', pad=12)
    ax2.set_ylim(0.75, 0.95)
    ax2.set_xlim(-25, 295)
    ax2.grid(True, linestyle='--', alpha=0.45, zorder=2)
    ax2.legend(loc='lower left', fontsize=8.2, framealpha=0.95, edgecolor='#b0bec5')
    
    plt.tight_layout()
    
    # Export publication formats
    png_path = os.path.join(script_dir, "figure2_quantitative.png")
    pdf_path = os.path.join(script_dir, "figure2_quantitative.pdf")
    
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"Successfully generated Figure 2:")
    print(f"  PNG: {png_path}")
    print(f"  PDF: {pdf_path}")

if __name__ == "__main__":
    main()
