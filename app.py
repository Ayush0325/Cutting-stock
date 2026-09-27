import streamlit as st
import pulp
import pandas as pd

# ------------------------------------------------------------------
# --- 1. DASHBOARD CONFIGURATION (Metric Units) ---
# ------------------------------------------------------------------
st.set_page_config(page_title="Industrial Slitting Optimizer (mm)", layout="wide")
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,0.2);
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)



st.title("🏭 Industrial Cutting & Slitting Optimizer (Metric)")

# ------------------------------------------------------------------
# --- 2. SIDEBAR: PRODUCTION INPUTS (mm) ---
# ------------------------------------------------------------------
with st.sidebar:
    st.header("📋 Input Parameters (mm)")
    reel_input = st.text_input("Large Roll Sizes (Master Reels)", "500, 1000, 1500")
    slit_input = st.text_input("Customer Sizes (Slit Widths)", "150, 200, 250")

    # Clean inputs and prevent negative values
    large_rolls = [int(x.strip()) for x in reel_input.split(",") if x.strip()]
    customer_sizes = [int(x.strip()) for x in slit_input.split(",") if x.strip()]

    if any(x <= 0 for x in large_rolls) or any(x <= 0 for x in customer_sizes):
        st.error("❌ Physical Error: All mm values must be positive.")
        st.stop()

    order_demand = {}
    if customer_sizes:
        st.subheader("📦 Order Quantities")
        for size in customer_sizes:
            order_demand[size] = st.number_input(f"Qty for {size} mm", min_value=1, value=10)

# ------------------------------------------------------------------
# --- 3. CORE LOGIC: PATTERN GENERATOR WITH LOCKOUT BRAKE ---
# ------------------------------------------------------------------
def generate_cutting_patterns(roll_width, sizes, min_size):
    patterns = []
    limit = 50000 # Memory safety threshold
    brake_triggered = False

    def backtrack(i, used, counts):
        nonlocal brake_triggered
        if len(patterns) >= limit:
            brake_triggered = True
            return
        if i == len(sizes):
            scrap = roll_width - used
            if 0 <= scrap < min_size:
                patterns.append(tuple(counts))
            return
        max_cuts = (roll_width - used) // sizes[i]
        for c in range(max_cuts + 1):
            if brake_triggered: break
            backtrack(i + 1, used + c * sizes[i], counts + [c])

    backtrack(0, 0, [])
    
    # Logic: If brake is hit, return EMPTY so no false results show
    if brake_triggered:
        return [], True
    return patterns, False

# ------------------------------------------------------------------
# --- 4. EXECUTION AND RESULTS ---
# ------------------------------------------------------------------
if st.button("🚀 Run Production Optimization"):
    if not large_rolls or not customer_sizes:
        st.stop()

    min_size = min(customer_sizes)
    simulation_results = []
    global_brake_hit = False

    # Check for brake triggers before doing ANY math
    for roll_width in large_rolls:
        _, is_broken = generate_cutting_patterns(roll_width, customer_sizes, min_size)
        if is_broken:
            st.error(f"🛑 **Pattern Brake Active for {roll_width}mm roll!**")
            st.warning("Combinations exceeded 50,000. This roll is too large compared to your small slit sizes. Results hidden to prevent false data.")
            global_brake_hit = True
            break 

    # Only show results if the calculation is safe and complete
    if not global_brake_hit:
        st.header("📊 Optimization Simulation Results (mm)")
        
        for roll_width in large_rolls:
            patterns, _ = generate_cutting_patterns(roll_width, customer_sizes, min_size)
            if not patterns: continue

            model = pulp.LpProblem(f"Opt_{roll_width}", pulp.LpMinimize)
            x = pulp.LpVariable.dicts("P", range(len(patterns)), lowBound=0, cat="Integer")
            model += pulp.lpSum(x[j] for j in range(len(patterns)))
            for i, size in enumerate(customer_sizes):
                model += pulp.lpSum(patterns[j][i] * x[j] for j in range(len(patterns))) >= order_demand[size]

            model.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=30))

            total_rolls = sum(int(round(pulp.value(x[j]))) for j in range(len(patterns)))
            total_material = int(total_rolls * roll_width)
            
            pattern_rows = []
            total_scrap = 0
            for j, p in enumerate(patterns):
                count = int(round(pulp.value(x[j])))
                if count > 0:
                    used_w = sum(p[i] * customer_sizes[i] for i in range(len(customer_sizes)))
                    scrap_per_roll = roll_width - used_w
                    run_scrap = scrap_per_roll * count # Total Run Scrap Logic
                    total_scrap += run_scrap
                    
                    pattern_rows.append({
                        "Cutting Pattern": p,
                        "Scrap/Roll (mm)": f"{scrap_per_roll} mm",
                        "Total Run Scrap": f"{run_scrap} mm", # Added column
                        "Reel Set Count": count
                    })

            with st.expander(f"Analysis: {roll_width} mm Master Reel Option", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Reels Needed", total_rolls)
                c2.metric("Gross Material", f"{total_material} mm")
                c3.metric("Net Trim Loss (Scrap)", f"{total_scrap} mm")
                if pattern_rows:
                    st.table(pd.DataFrame(pattern_rows))

            simulation_results.append({"RollWidth": roll_width, "TotalMaterial": total_material})

        # Step C: Final Recommendation (Hidden if Brake hit)
        if simulation_results:
            best = min(simulation_results, key=lambda x: x["TotalMaterial"])
            st.divider()
            st.success(f"### ✅ Procurement Recommendation: {best['RollWidth']} mm Master Reel")
            st.info(f"This size minimizes total linear consumption to {best['TotalMaterial']} mm.")

st.divider()
st.caption("📌 Professional PPC Slitting Logic — Metric Integration.")
