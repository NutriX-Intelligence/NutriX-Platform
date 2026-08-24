import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set clean academic typography & style
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 1.0

def draw_rounded_box(ax, x, y, w, h, title, items=None, bg_color='#f0f4f8', border_color='#2b5c8f', title_color='#1b3a5a', badge=None, badge_bg='#2b5c8f', title_fontsize=10.0, item_fontsize=8.5, badge_fontsize=7.6, radius=0.07, is_stage1_right=False):
    # Base container box
    rect = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        linewidth=1.2,
        edgecolor=border_color,
        facecolor=bg_color,
        zorder=2
    )
    ax.add_patch(rect)
    
    if badge:
        # Title
        ax.text(x + w/2, y + h - 0.20, title, fontsize=title_fontsize, fontweight='bold', color=title_color, ha='center', va='center', zorder=4)
        
        # Badge
        badge_w = min(w - 0.30, 3.10) if is_stage1_right else (w - 0.24)
        badge_h = 0.24
        badge_x = x + (w - badge_w) / 2
        badge_y = y + h - 0.50
        badge_rect = patches.FancyBboxPatch(
            (badge_x, badge_y), badge_w, badge_h,
            boxstyle="round,pad=0,rounding_size=0.04",
            linewidth=0,
            facecolor=badge_bg,
            zorder=4
        )
        ax.add_patch(badge_rect)
        ax.text(x + w/2, badge_y + badge_h/2, badge, fontsize=badge_fontsize, fontweight='bold', color='#ffffff', ha='center', va='center', zorder=5)
        
        # Bullets
        if items:
            if is_stage1_right:
                curr_y = y + 0.32
                for it in items:
                    ax.text(x + 0.35, curr_y, f"• {it}", fontsize=item_fontsize, color='#1f2937', ha='left', va='center', zorder=4)
                    curr_y -= 0.22
            else:
                curr_y = y + h - 0.82
                for it in items:
                    ax.text(x + 0.16, curr_y, f"• {it}", fontsize=item_fontsize, color='#1f2937', ha='left', va='center', zorder=4)
                    curr_y -= 0.28
    else:
        # Title without badge
        ax.text(x + w/2, y + h - 0.22, title, fontsize=title_fontsize, fontweight='bold', color=title_color, ha='center', va='center', zorder=4)
        if items:
            curr_y = y + h - 0.54
            for it in items:
                ax.text(x + 0.16, curr_y, f"• {it}", fontsize=item_fontsize, color='#1f2937', ha='left', va='center', zorder=4)
                curr_y -= 0.25

def draw_flow_arrow(ax, x1, y1, x2, y2, color='#0284c7', lw=4.8, head_scale=30, rad=0.0):
    arrow = patches.FancyArrowPatch(
        (x1, y1), (x2, y2),
        arrowstyle="-|>",
        mutation_scale=head_scale,
        linewidth=lw,
        color=color,
        connectionstyle=f"arc3,rad={rad}",
        zorder=6
    )
    ax.add_patch(arrow)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = script_dir
    os.makedirs(out_dir, exist_ok=True)
    
    # Canvas dimensions (9.2 x 12.6 inches)
    fig, ax = plt.subplots(figsize=(9.2, 12.6), dpi=300)
    ax.set_xlim(0, 9.2)
    ax.set_ylim(0, 12.6)
    ax.axis('off')
    
    # -------------------------------------------------------------------------
    # 3 STAGE CONTAINERS (Top to Bottom)
    # -------------------------------------------------------------------------
    # Stage 1: Input & Perception (Top)
    s1 = patches.FancyBboxPatch((0.45, 7.80), 8.30, 4.15, boxstyle="round,pad=0,rounding_size=0.12", linewidth=1.1, linestyle="--", edgecolor="#38bdf8", facecolor="#f0f9ff", zorder=1)
    ax.add_patch(s1)
    ax.text(4.60, 11.60, "STAGE 1: INPUT & PERCEPTION", fontsize=11.2, fontweight='bold', color="#0369a1", ha="center", va="center", zorder=3)
    
    # Stage 2: Canonical & Knowledge Grounding (Middle)
    s2 = patches.FancyBboxPatch((0.45, 4.30), 8.30, 2.90, boxstyle="round,pad=0,rounding_size=0.12", linewidth=1.3, linestyle="--", edgecolor="#4ade80", facecolor="#f0fdf4", zorder=1)
    ax.add_patch(s2)
    ax.text(4.60, 6.95, "STAGE 2: CANONICAL REPRESENTATION & KNOWLEDGE GROUNDING", fontsize=10.5, fontweight='bold', color="#15803d", ha="center", va="center", zorder=3)
    
    # Stage 3: Constrained Optimization & Output (Bottom)
    s3 = patches.FancyBboxPatch((0.45, 0.85), 8.30, 2.85, boxstyle="round,pad=0,rounding_size=0.12", linewidth=1.1, linestyle="--", edgecolor="#fb923c", facecolor="#fff7ed", zorder=1)
    ax.add_patch(s3)
    ax.text(4.60, 3.45, "STAGE 3: CONSTRAINED OPTIMIZATION & OUTPUT", fontsize=11.2, fontweight='bold', color="#c2410c", ha="center", va="center", zorder=3)
    
    # -------------------------------------------------------------------------
    # STAGE 1 NODES: INPUT PATHWAYS & EXTRACTORS
    # -------------------------------------------------------------------------
    row_h = 1.05
    left_w = 2.20
    right_w = 4.65
    left_x = 0.70
    right_x = 3.85
    
    # Row 1: Food Image → Food Detection
    draw_rounded_box(ax, left_x, 10.30, left_w, row_h, "Food Image", ["Overhead plate meal", "Multi-dish meal scene"], bg_color='#ffffff', border_color='#0284c7', title_color='#0369a1')
    draw_flow_arrow(ax, left_x + left_w + 0.06, 10.825, right_x - 0.08, 10.825, color='#0284c7', lw=4.8, head_scale=30)
    draw_rounded_box(ax, right_x, 10.30, right_w, row_h, "Food Detection", ["123 visual food classes", "56,147 annotated images"], badge="YOLOv8n Food Detector", badge_bg='#0284c7', bg_color='#e0f2fe', border_color='#0284c7', title_color='#0369a1', is_stage1_right=True)
    
    # Row 2: Packaged Food → Barcode Decoding
    draw_rounded_box(ax, left_x, 9.10, left_w, row_h, "Packaged Food", ["Commercial food item", "UPC / EAN / GTIN barcode"], bg_color='#ffffff', border_color='#0284c7', title_color='#0369a1')
    draw_flow_arrow(ax, left_x + left_w + 0.06, 9.625, right_x - 0.08, 9.625, color='#0284c7', lw=4.8, head_scale=30)
    draw_rounded_box(ax, right_x, 9.10, right_w, row_h, "Barcode Decoding", ["Product identity lookup", "Open Food Facts & local DB"], badge="Barcode Decoder", badge_bg='#0284c7', bg_color='#e0f2fe', border_color='#0284c7', title_color='#0369a1', is_stage1_right=True)
    
    # Row 3: Nutrition Label → OCR Text Extraction
    draw_rounded_box(ax, left_x, 7.90, left_w, row_h, "Nutrition Label", ["Menu description", "Packaged facts panel"], bg_color='#ffffff', border_color='#0284c7', title_color='#0369a1')
    draw_flow_arrow(ax, left_x + left_w + 0.06, 8.425, right_x - 0.08, 8.425, color='#0284c7', lw=4.8, head_scale=30)
    draw_rounded_box(ax, right_x, 7.90, right_w, row_h, "Text Extraction", ["Text line token parsing", "Serving size & nutrient regex"], badge="OCR Engine", badge_bg='#0284c7', bg_color='#e0f2fe', border_color='#0284c7', title_color='#0369a1', is_stage1_right=True)
    
    # Prominent Downward Flow Arrow from Stage 1 into Stage 2
    draw_flow_arrow(ax, 4.60, 7.74, 4.60, 7.26, color='#0369a1', lw=5.0, head_scale=32)
    
    # -------------------------------------------------------------------------
    # STAGE 2 NODES: CANONICAL IDENTITY & KNOWLEDGE GROUNDING
    # -------------------------------------------------------------------------
    card_w = 2.20
    s2_card_h = 2.05
    c1_x = 0.70
    c2_x = 3.50
    c3_x = 6.30
    
    # Card 1: Canonical Food Identity
    draw_rounded_box(
        ax, c1_x, 4.50, card_w, s2_card_h,
        "Canonical Identity",
        [
            "Name normalization",
            "Synonym/alias map",
            "Portion/unit scale",
            "Confidence fusion"
        ],
        badge="Unified Entity",
        badge_bg='#0f766e',
        bg_color='#ffffff',
        border_color='#0f766e',
        title_color='#115e59',
        radius=0.08
    )
    
    # Extra Large Horizontal Connecting Arrow 1 → 2
    draw_flow_arrow(ax, c1_x + card_w + 0.06, 5.52, c2_x - 0.06, 5.52, color='#16a34a', lw=4.8, head_scale=30)
    
    # Card 2: Nutrition Knowledge Grounding
    draw_rounded_box(
        ax, c2_x, 4.50, card_w, s2_card_h,
        "Nutrition Grounding",
        [
            "Calories & macros",
            "Protein, Carbs, Fats",
            "Micronutrients & fiber",
            "IFCT / USDA database"
        ],
        badge="Clinical Database",
        badge_bg='#15803d',
        bg_color='#ffffff',
        border_color='#16a34a',
        title_color='#14532d',
        radius=0.08
    )
    
    # Extra Large Horizontal Connecting Arrow 2 → 3
    draw_flow_arrow(ax, c2_x + card_w + 0.06, 5.52, c3_x - 0.06, 5.52, color='#16a34a', lw=4.8, head_scale=30)
    
    # Card 3: Regional Food Knowledge
    draw_rounded_box(
        ax, c3_x, 4.50, card_w, s2_card_h,
        "Regional Knowledge",
        [
            "217 regional classes",
            "10 culinary categories",
            "Recipes & ingredients",
            "Dietary & cultural tags"
        ],
        badge="Grounding (217 Classes)",
        badge_bg='#166534',
        bg_color='#dcfce7',
        border_color='#15803d',
        title_color='#14532d',
        radius=0.08
    )
    
    # Prominent Downward Flow Arrow from Stage 2 into Stage 3
    draw_flow_arrow(ax, 4.60, 4.24, 4.60, 3.76, color='#15803d', lw=5.0, head_scale=32)
    
    # -------------------------------------------------------------------------
    # STAGE 3 NODES: CONSTRAINED OPTIMIZATION & OUTPUT
    # -------------------------------------------------------------------------
    s3_card_w = 3.50
    s3_card_h = 2.05
    s3_c1_x = 0.70
    s3_c2_x = 5.00
    
    # Card 1: Constrained Meal Planning
    draw_rounded_box(
        ax, s3_c1_x, 1.00, s3_card_w, s3_card_h,
        "Constrained Meal Planning",
        [
            "4 Meal Slots: B / L / D / Snack",
            "Calorie & macro bounds: (1±τ)T",
            "Dietary & ingredient constraints",
            "Candidate selection: N ∈ [50, 500]"
        ],
        badge="OR-Tools / SCIP Solver",
        badge_bg='#c2410c',
        bg_color='#ffffff',
        border_color='#ea580c',
        title_color='#7c2d12',
        radius=0.08
    )
    
    # Extra Large Horizontal Connecting Arrow in Stage 3
    draw_flow_arrow(ax, s3_c1_x + s3_card_w + 0.08, 2.02, s3_c2_x - 0.08, 2.02, color='#ea580c', lw=5.0, head_scale=32)
    
    # Card 2: Nutrition-Grounded Meal Plan
    draw_rounded_box(
        ax, s3_c2_x, 1.00, s3_card_w, s3_card_h,
        "Nutrition-Grounded Meal Plan",
        [
            "Optimized daily recipe schedule",
            "Target nutrient & calorie fulfillment",
            "Serving sizes & portion weights",
            "Nutritional summary & compliance"
        ],
        badge="Optimized Feasible Output",
        badge_bg='#9a3412',
        bg_color='#ffedd5',
        border_color='#c2410c',
        title_color='#7c2d12',
        radius=0.08
    )
    
    # -------------------------------------------------------------
    # BOTTOM SCIENTIFIC TAXONOMY ANNOTATION BANNER
    # -------------------------------------------------------------
    note_box = patches.FancyBboxPatch(
        (0.45, 0.22), 8.30, 0.38,
        boxstyle="round,pad=0,rounding_size=0.06",
        linewidth=0.8,
        edgecolor="#94a3b8",
        facecolor="#f8fafc",
        zorder=2
    )
    ax.add_patch(note_box)
    
    note_text = "Visual recognition taxonomy: 123 classes | Regional knowledge taxonomy: 217 classes across 10 culinary categories"
    ax.text(4.60, 0.41, note_text, fontsize=7.8, fontweight='normal', color="#334155", ha="center", va="center", zorder=3)
    
    plt.tight_layout()
    
    # Export in Vector PDF, Scalable SVG, and 600 DPI PNG
    pdf_path = os.path.join(out_dir, "figure1_pipeline.pdf")
    svg_path = os.path.join(out_dir, "figure1_pipeline.svg")
    png_path = os.path.join(out_dir, "figure1_pipeline.png")
    
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.savefig(svg_path, format='svg', bbox_inches='tight')
    plt.savefig(png_path, dpi=600, bbox_inches='tight')
    plt.close()
    
    print(f"Successfully generated clean compact Portrait Figure 1 with extra-large bold pointers:")
    print(f"  PDF: {pdf_path}")
    print(f"  SVG: {svg_path}")
    print(f"  PNG (600 DPI): {png_path}")

if __name__ == "__main__":
    main()
