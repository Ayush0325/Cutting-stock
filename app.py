import streamlit as st
import pandas as pd
import numpy as np

from scipy.optimize import milp, LinearConstraint, Bounds


# ------------------------------------------------------------------
# 1. DASHBOARD CONFIGURATION
# ------------------------------------------------------------------

st.set_page_config(
    page_title="Industrial Slitting Optimizer (mm)",
    layout="wide"
)

st.markdown(
    """
    <style>
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        padding: 18px;
        border-radius: 14px;
        border: 1px solid rgba(128,128,128,0.2);
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏭 Industrial Cutting & Slitting Optimizer (Metric)")


# ------------------------------------------------------------------
# 2. SIDEBAR INPUTS
# ------------------------------------------------------------------

with st.sidebar:

    st.header("📋 Input Parameters (mm)")

    reel_input = st.text_input(
        "Large Roll Sizes (Master Reels)",
        "500, 1000, 1500"
    )

    slit_input = st.text_input(
        "Customer Sizes (Slit Widths)",
        "150, 200, 250"
    )

    # --------------------------------------------------------------
    # Convert inputs
    # --------------------------------------------------------------

    try:

        large_rolls = [
            int(x.strip())
            for x in reel_input.split(",")
            if x.strip()
        ]

        customer_sizes = [
            int(x.strip())
            for x in slit_input.split(",")
            if x.strip()
        ]

    except ValueError:

        st.error(
            "❌ Please enter only positive whole numbers."
        )

        st.stop()

    # --------------------------------------------------------------
    # Validate inputs
    # --------------------------------------------------------------

    if not large_rolls:

        st.error(
            "❌ Enter at least one master reel size."
        )

        st.stop()

    if not customer_sizes:

        st.error(
            "❌ Enter at least one customer slit size."
        )

        st.stop()

    if any(x <= 0 for x in large_rolls):

        st.error(
            "❌ Master reel sizes must be greater than 0."
        )

        st.stop()

    if any(x <= 0 for x in customer_sizes):

        st.error(
            "❌ Customer slit sizes must be greater than 0."
        )

        st.stop()

    # Remove duplicate customer sizes

    customer_sizes = list(
        dict.fromkeys(customer_sizes)
    )

    # --------------------------------------------------------------
    # Order quantities
    # --------------------------------------------------------------

    order_demand = {}

    st.subheader("📦 Order Quantities")

    for size in customer_sizes:

        order_demand[size] = st.number_input(
            f"Qty for {size} mm",
            min_value=1,
            value=10,
            step=1
        )


# ------------------------------------------------------------------
# 3. CUTTING PATTERN GENERATOR
# ------------------------------------------------------------------

def generate_cutting_patterns(
    roll_width,
    sizes,
    min_size,
    limit=50000
):

    patterns = []

    brake_triggered = False

    def backtrack(i, used, counts):

        nonlocal brake_triggered

        # Safety limit
        if len(patterns) >= limit:

            brake_triggered = True
            return

        # All sizes processed
        if i == len(sizes):

            scrap = roll_width - used

            # Keep patterns where remaining scrap is
            # smaller than the smallest customer width.

            if 0 <= scrap < min_size:

                patterns.append(
                    tuple(counts)
                )

            return

        # Maximum number of current size pieces
        max_cuts = (
            (roll_width - used)
            // sizes[i]
        )

        for c in range(max_cuts + 1):

            if brake_triggered:
                break

            backtrack(
                i + 1,
                used + c * sizes[i],
                counts + [c]
            )

    backtrack(
        0,
        0,
        []
    )

    if brake_triggered:

        return [], True

    return patterns, False


# ------------------------------------------------------------------
# 4. MILP OPTIMIZATION USING SCIPY
# ------------------------------------------------------------------

def optimize_patterns(
    patterns,
    customer_sizes,
    order_demand
):

    if not patterns:
        return None

    number_patterns = len(patterns)
    number_sizes = len(customer_sizes)

    # --------------------------------------------------------------
    # Objective:
    # Minimize number of master reels
    # --------------------------------------------------------------

    objective = np.ones(
        number_patterns,
        dtype=float
    )

    # --------------------------------------------------------------
    # Constraint matrix
    #
    # Each row = customer size
    # Each column = cutting pattern
    # --------------------------------------------------------------

    A = np.array(
        [
            [
                patterns[j][i]
                for j in range(number_patterns)
            ]
            for i in range(number_sizes)
        ],
        dtype=float
    )

    # Demand constraints:
    #
    # A @ x >= demand
    #
    # scipy LinearConstraint:
    # lower <= A @ x <= upper

    demand = np.array(
        [
            order_demand[size]
            for size in customer_sizes
        ],
        dtype=float
    )

    constraints = LinearConstraint(
        A,
        demand,
        np.full(
            number_sizes,
            np.inf
        )
    )

    # --------------------------------------------------------------
    # Integer variables
    # --------------------------------------------------------------

    integrality = np.ones(
        number_patterns,
        dtype=int
    )

    # Variables must be >= 0
    # Upper bound is infinity

    bounds = Bounds(
        np.zeros(number_patterns),
        np.full(
            number_patterns,
            np.inf
        )
    )

    # --------------------------------------------------------------
    # Solve MILP
    # --------------------------------------------------------------

    result = milp(
        c=objective,
        integrality=integrality,
        bounds=bounds,
        constraints=constraints,
        options={
            "time_limit": 30
        }
    )

    # --------------------------------------------------------------
    # Check result
    # --------------------------------------------------------------

    if not result.success:

        return {
            "success": False,
            "message": result.message
        }

    # Round integer solution
    solution = np.rint(
        result.x
    ).astype(int)

    return {
        "success": True,
        "solution": solution,
        "objective": result.fun,
        "message": result.message
    }


# ------------------------------------------------------------------
# 5. RUN OPTIMIZATION
# ------------------------------------------------------------------

if st.button(
    "🚀 Run Production Optimization",
    type="primary"
):

    min_size = min(customer_sizes)

    simulation_results = []

    global_brake_hit = False

    # --------------------------------------------------------------
    # Check pattern generation first
    # --------------------------------------------------------------

    for roll_width in large_rolls:

        _, brake_hit = generate_cutting_patterns(
            roll_width,
            customer_sizes,
            min_size
        )

        if brake_hit:

            st.error(
                f"🛑 Pattern Brake Active for "
                f"{roll_width} mm roll!"
            )

            st.warning(
                "Combinations exceeded 50,000. "
                "This roll is too large compared with "
                "the customer slit sizes."
            )

            global_brake_hit = True

            break

    # --------------------------------------------------------------
    # Stop if pattern generation exceeded safety limit
    # --------------------------------------------------------------

    if not global_brake_hit:

        st.header(
            "📊 Optimization Simulation Results (mm)"
        )

        # ----------------------------------------------------------
        # Evaluate every master reel
        # ----------------------------------------------------------

        for roll_width in large_rolls:

            patterns, brake_hit = (
                generate_cutting_patterns(
                    roll_width,
                    customer_sizes,
                    min_size
                )
            )

            if brake_hit:

                st.warning(
                    f"Pattern generation stopped for "
                    f"{roll_width} mm."
                )

                continue

            if not patterns:

                st.warning(
                    f"⚠️ No valid cutting patterns found "
                    f"for {roll_width} mm master reel."
                )

                continue

            # ------------------------------------------------------
            # Run optimization
            # ------------------------------------------------------

            optimization = optimize_patterns(
                patterns,
                customer_sizes,
                order_demand
            )

            if optimization is None:

                st.warning(
                    f"No optimization model could be created "
                    f"for {roll_width} mm."
                )

                continue

            if not optimization["success"]:

                st.warning(
                    f"⚠️ Optimization failed for "
                    f"{roll_width} mm."
                )

                st.info(
                    optimization["message"]
                )

                continue

            solution = optimization[
                "solution"
            ]

            # ------------------------------------------------------
            # Calculate total reels
            # ------------------------------------------------------

            total_rolls = int(
                np.sum(solution)
            )

            # ------------------------------------------------------
            # Gross material consumption
            # ------------------------------------------------------

            total_material = int(
                total_rolls * roll_width
            )

            # ------------------------------------------------------
            # Pattern details
            # ------------------------------------------------------

            pattern_rows = []

            total_scrap = 0

            for j, pattern in enumerate(patterns):

                count = int(
                    solution[j]
                )

                if count <= 0:
                    continue

                # Material actually used
                used_width = sum(
                    pattern[i] *
                    customer_sizes[i]
                    for i in range(
                        len(customer_sizes)
                    )
                )

                # Scrap on one master reel
                scrap_per_roll = (
                    roll_width -
                    used_width
                )

                # Scrap generated by this pattern
                run_scrap = (
                    scrap_per_roll *
                    count
                )

                total_scrap += run_scrap

                pattern_rows.append(
                    {
                        "Cutting Pattern": pattern,

                        "Scrap/Roll (mm)":
                            f"{scrap_per_roll} mm",

                        "Total Run Scrap":
                            f"{run_scrap} mm",

                        "Reel Set Count":
                            count
                    }
                )

            # ------------------------------------------------------
            # Display results
            # ------------------------------------------------------

            with st.expander(
                f"Analysis: {roll_width} mm Master Reel Option",
                expanded=True
            ):

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Total Reels Needed",
                    total_rolls
                )

                c2.metric(
                    "Gross Material",
                    f"{total_material} mm"
                )

                c3.metric(
                    "Net Trim Loss (Scrap)",
                    f"{total_scrap} mm"
                )

                if pattern_rows:

                    result_df = pd.DataFrame(
                        pattern_rows
                    )

                    st.table(
                        result_df
                    )

                else:

                    st.info(
                        "No cutting patterns were selected."
                    )

            # ------------------------------------------------------
            # Store result
            # ------------------------------------------------------

            simulation_results.append(
                {
                    "RollWidth": roll_width,
                    "TotalMaterial": total_material,
                    "TotalRolls": total_rolls,
                    "TotalScrap": total_scrap
                }
            )

        # ----------------------------------------------------------
        # FINAL RECOMMENDATION
        # ----------------------------------------------------------

        if simulation_results:

            best = min(
                simulation_results,
                key=lambda x:
                    x["TotalMaterial"]
            )

            st.divider()

            st.success(
                f"### ✅ Procurement Recommendation: "
                f"{best['RollWidth']} mm Master Reel"
            )

            st.info(
                f"This option minimizes total linear "
                f"material consumption to "
                f"{best['TotalMaterial']} mm."
            )

            # ------------------------------------------------------
            # Summary
            # ------------------------------------------------------

            summary_df = pd.DataFrame(
                simulation_results
            )

            summary_df = summary_df.rename(
                columns={
                    "RollWidth":
                        "Master Reel (mm)",

                    "TotalMaterial":
                        "Total Material (mm)",

                    "TotalRolls":
                        "Total Reels",

                    "TotalScrap":
                        "Total Scrap (mm)"
                }
            )

            st.subheader(
                "📋 Optimization Summary"
            )

            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.warning(
                "⚠️ No feasible optimization result was found."
            )


# ------------------------------------------------------------------
# 6. FOOTER
# ------------------------------------------------------------------

st.divider()

st.caption(
    "📌 Professional PPC Slitting Logic — Metric Integration."
)
