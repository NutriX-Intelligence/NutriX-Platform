import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cv2

# Set publication style
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.8

def generate_figure2():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(script_dir, "../.."))
    
    dist_csv = os.path.join(script_dir, "class_distribution.csv")
    rot_csv = os.path.join(script_dir, "rotational_robustness_results.csv")
    
    fig_dir = os.path.join(script_dir, "wacv_figures")
    os.makedirs(fig_dir, exist_ok=True)
    
    df_dist = pd.read_csv(dist_csv)
    df_rot = pd.read_csv(rot_csv)
    
    # Create 2-panel figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    
    # -------------------------------------------------------------
    # Panel (a): Validation Class Distribution (Top 25 + Representation Brackets)
    # -------------------------------------------------------------
    top_val = df_dist[df_dist['val_images'] > 0].sort_values(by='val_images', ascending=False).head(25)
    
    colors = ['#1f77b4' if v > 20 else '#ff7f0e' for v in top_val['val_images']]
    bars = ax1.bar(range(len(top_val)), top_val['val_images'], color='#2b5c8f', width=0.65, edgecolor='#1b3a5a', linewidth=0.8)
    
    ax1.set_xticks(range(len(top_val)))
    ax1.set_xticklabels(top_val['class_name'], rotation=65, ha='right', fontsize=8.5)
    ax1.set_ylabel('Validation Images Count', fontsize=10, fontweight='bold')
    ax1.set_title('(a) Validation Class Distribution (Top 25 Represented Classes)', fontsize=11, fontweight='bold', pad=12)
    ax1.grid(axis='y', linestyle='--', alpha=0.4)
    ax1.set_ylim(0, max(top_val['val_images']) * 1.12)
    
    # Annotate summary box
    bracket_text = "Representation Brackets (123 Classes):\n• >20 Images: 51 Classes\n• 5–20 Images: 5 Classes\n• <5 Images: 30 Classes\n• 0 Images: 37 Classes"
    ax1.text(0.96, 0.94, bracket_text, transform=ax1.transAxes, fontsize=8,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#f8f9fa', edgecolor='#cccccc', alpha=0.9))
    
    # -------------------------------------------------------------
    # Panel (b): Rotational Robustness Evaluation
    # -------------------------------------------------------------
    angles = [0, 90, 180, 270]
    prec = df_rot['Precision'].values
    rec = df_rot['Recall'].values
    map50 = df_rot['mAP50'].values
    
    ax2.plot(angles, map50, marker='s', markersize=8, color='#2ca02c', linewidth=2.2, label='mAP@50 (IoU=0.50)')
    ax2.plot(angles, prec, marker='o', markersize=7, color='#1f77b4', linewidth=1.8, linestyle='--', label='Precision')
    ax2.plot(angles, rec, marker='^', markersize=7, color='#d62728', linewidth=1.8, linestyle=':', label='Recall')
    
    # Add shaded stability region
    ax2.axhspan(min(map50)-0.005, max(map50)+0.005, color='#2ca02c', alpha=0.08, label='mAP@50 Stability Band (<1.2% Δ)')
    
    ax2.set_xticks(angles)
    ax2.set_xticklabels(['0° (Baseline)', '90° (Clockwise)', '180° (Inverted)', '270° (Counter-CW)'], fontsize=9)
    ax2.set_xlabel('Plate Rotation Angle', fontsize=10, fontweight='bold')
    ax2.set_ylabel('Metric Score (0.0 – 1.0)', fontsize=10, fontweight='bold')
    ax2.set_title('(b) Rotational Invariance Robustness (N=200 Plate Images)', fontsize=11, fontweight='bold', pad=12)
    ax2.set_ylim(0.75, 0.95)
    ax2.grid(True, linestyle='--', alpha=0.4)
    ax2.legend(loc='lower left', fontsize=8.5, framealpha=0.9)
    
    # Value annotations on map50
    for a, m in zip(angles, map50):
        ax2.annotate(f'{m:.4f}', (a, m), textcoords="offset points", xytext=(0, 9), ha='center', fontsize=8.5, fontweight='bold', color='#1e6b1e')
        
    plt.tight_layout()
    
    png_path = os.path.join(fig_dir, "figure2_quantitative.png")
    pdf_path = os.path.join(fig_dir, "figure2_quantitative.pdf")
    plt.savefig(png_path, dpi=300, bbox_inches='tight')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"Successfully generated Figure 2:")
    print(f"  PNG: {png_path}")
    print(f"  PDF: {pdf_path}")

def generate_figure3_grid():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    qual_dir = os.path.join(script_dir, "wacv_figures", "qualitative")
    
    images_info = [
        ("1_high_conf_correct.jpg", "(a) Correct High-Confidence\nGT: palakpaneer | Pred: palakpaneer (0.88)"),
        ("2_false_positive.jpg", "(b) Background False Positive\nGT: None | Pred: potato (0.64), garlic (0.22)"),
        ("3_missed_detection.jpg", "(c) Missed Detection (FN)\nGT: farsi ko munta | Pred: None (<0.15)"),
        ("4_visually_similar_confusion.jpg", "(d) Visually Similar Confusion\nGT: beans | Pred: pea (0.75)"),
        ("5_duplicate_semantic_confusion.jpg", "(e) Duplicate Semantic Confusion\nGT: capsicum | Pred: bell pepper (0.36)"),
        ("6_crowded_plate.jpg", "(f) Crowded Multi-Object Plate\nGT: bell pepper (x3) | Pred: bell pepper (x4)"),
        ("7_low_confidence.jpg", "(g) Low-Confidence Detection\nGT: beans | Pred: beans (0.17)")
    ]
    
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), dpi=300)
    axes = axes.flatten()
    
    for i, (fn, caption) in enumerate(images_info):
        img_path = os.path.join(qual_dir, fn)
        if os.path.exists(img_path):
            img = cv2.imread(img_path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            axes[i].imshow(img)
        axes[i].set_title(caption, fontsize=9, fontweight='bold', pad=6)
        axes[i].axis('off')
        
    # Hide the 8th unused subplot
    axes[7].axis('off')
    
    plt.suptitle("Figure 3: Qualitative Food Perception & Error Analysis Taxonomy", fontsize=13, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    fig3_png = os.path.join(script_dir, "wacv_figures", "figure3_qualitative.png")
    fig3_pdf = os.path.join(script_dir, "wacv_figures", "figure3_qualitative.pdf")
    plt.savefig(fig3_png, dpi=300, bbox_inches='tight')
    plt.savefig(fig3_pdf, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"Successfully generated Figure 3:")
    print(f"  PNG: {fig3_png}")
    print(f"  PDF: {fig3_pdf}")

if __name__ == "__main__":
    generate_figure2()
    generate_figure3_grid()
