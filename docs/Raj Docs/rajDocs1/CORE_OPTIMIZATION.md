# WACV 2027 Technical Audit: Core Optimization Engine

**Target Repository:** `NutriX-Intelligence/NutriX-Platform`  
**Scope:** Mathematical Optimization, Google OR-Tools MIP Solver, Constraint Programming, and Adaptive Meal Planning.

---

## 1. Overview of Optimization Engine

The optimization module in this repository automates daily nutrition and dietary planning using Mixed-Integer Linear Programming (MILP). It ensures that full-day meal plans adhere strictly to target calories, macronutrient ratios (protein, carbohydrates, fat), and dietary fiber floors while maximizing user recipe preference and recommendation scores.

* **Primary Code Location:** [ms3_user/NutriX-main/NutriX-main/app/services/optimization_engine.py](file:///wsl.localhost/Ubuntu/home/harsh/Nutrix/ms3_user/NutriX-main/NutriX-main/app/services/optimization_engine.py)
* **Underlying Optimization Framework:** Google OR-Tools (`ortools.linear_solver.pywraplp`)
* **Solver Backend:** SCIP (Solving Constraint Integer Programming) MILP Solver (`pywraplp.Solver.CreateSolver("SCIP")`)

---

## 2. Formal Mathematical Formulation

### 2.1 Sets & Indices
* $S = \{\text{Breakfast}, \text{Lunch}, \text{Dinner}, \text{Snack}\}$: Set of required daily meal slots.
* $C_s$: Set of candidate recipes categorized for meal slot $s \in S$.
* $r \in C_s$: Individual candidate recipe.

### 2.2 Decision Variables
$$y_{s, r} \in \{0, 1\} \quad \forall s \in S, \forall r \in C_s$$
where $y_{s, r} = 1$ if recipe $r$ is selected for meal slot $s$, and $0$ otherwise.

### 2.3 Objective Function
Maximize total recommendation score and high-fiber bonus across selected meals:
$$\text{Maximize } Z = \sum_{s \in S} \sum_{r \in C_s} \Big( \text{Score}_r + \text{Bonus}_r \Big) \cdot y_{s, r}$$
where:
* $\text{Score}_r$: Preference matching score produced by `RecommendationEngine` (range $[0, 1]$).
* $\text{Bonus}_r = \begin{cases} 2.0 \times \text{Fibre}_r & \text{if preference } = \text{"high\_fiber"} \\ 0.0 & \text{otherwise} \end{cases}$

### 2.4 Mathematical Constraints

1. **Exact Meal Slot Assignment Constraint:**  
   Select exactly one recipe per meal slot:
   $$\sum_{r \in C_s} y_{s, r} = 1 \quad \forall s \in S$$

2. **Recipe Diversity / Non-Repetition Constraint:**  
   Prevent the same recipe from being assigned to both Lunch and Dinner:
   $$y_{\text{Lunch}, r} + y_{\text{Dinner}, r} \le 1 \quad \forall r \in C_{\text{Lunch}} \cap C_{\text{Dinner}}$$

3. **Caloric Target Bounded Range Constraint:**
   $$(1 - \tau) \cdot T_{\text{cal}} \le \sum_{s \in S} \sum_{r \in C_s} E_r \cdot y_{s, r} \le (1 + \tau) \cdot T_{\text{cal}}$$
   where $E_r$ is the per-serving energy (kcal) of recipe $r$, $T_{\text{cal}}$ is user calorie target, and $\tau$ is tolerance parameter.

4. **Macronutrient Range Constraints:**
   * **Protein:** $(1 - \tau) \cdot T_{\text{prot}} \le \sum_{s \in S} \sum_{r \in C_s} P_r \cdot y_{s, r} \le (1 + \tau) \cdot T_{\text{prot}}$
   * **Carbohydrates:** $(1 - \tau) \cdot T_{\text{carb}} \le \sum_{s \in S} \sum_{r \in C_s} C_r \cdot y_{s, r} \le (1 + \tau) \cdot T_{\text{carb}}$
   * **Fat:** $(1 - \tau) \cdot T_{\text{fat}} \le \sum_{s \in S} \sum_{r \in C_s} F_r \cdot y_{s, r} \le (1 + \tau) \cdot T_{\text{fat}}$

5. **High-Fiber Minimum Threshold Constraint (Optional):**
   $$\sum_{s \in S} \sum_{r \in C_s} \text{Fib}_r \cdot y_{s, r} \ge (1 - \tau) \cdot T_{\text{fiber}}$$

---

## 3. Dynamic Tolerance Relaxation Algorithm

To prevent solver infeasibility when user constraints (e.g. strict per-meal slot cuisine filters) reduce the candidate recipe pool:

```python
current_tol = tolerance  # starts at 0.15 (15%)
while current_tol <= max_tolerance:  # max_tolerance = 0.40 (40%)
  result = _solve_mip(..., tolerance=current_tol)
  if result:
    return result
  current_tol += 0.05  # relaxes tolerance by 5% each iteration
```

---

## 4. Preference Profile Configurations

Supported macronutrient split presets in `OptimizationEngine.generate_daily_plan()`:

| Preference Mode | Protein (% Cal) | Carbs (% Cal) | Fat (% Cal) | Fiber Target |
| :--- | :--- | :--- | :--- | :--- |
| **Balanced** | 20% | 50% | 30% | 28.0 g |
| **High Protein** | 30% | 40% | 30% | 28.0 g |
| **Low Carb** | 25% | 20% | 55% | 28.0 g |
| **Low Fat** | 20% | 60% | 20% | 28.0 g |
| **High Fiber** | 20% | 55% | 25% | 35.0 g |
