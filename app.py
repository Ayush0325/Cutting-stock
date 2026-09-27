import streamlit as st
import pandas as pd
from collections import deque


# ================================================================
# 1. PAGE CONFIGURATION
# ================================================================

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


# ================================================================
# 2. SIDEBAR - INPUT PARAMETERS
# ================================================================

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

    # ------------------------------------------------------------
    # Convert user input
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Validate input
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Order quantities
    # ------------------------------------------------------------

    order_demand = {}

    st.subheader("📦 Order Quantities")

    for size in customer_sizes:

        order_demand[size] = st.number_input(
            f"Qty for {size} mm",
            min_value=1,
            value=10,
            step=1
        )


# ================================================================
# 3. CUTTING PATTERN GENERATOR
# ================================================================

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

        # Safety brake
        if len(patterns) >= limit:

            brake_triggered = True
            return

        # All sizes processed
        if i == len(sizes):

            scrap = roll_width - used

            # Keep patterns with scrap less than
            # the smallest customer size
            if 0 <= scrap < min_size:

                patterns.append(
                    tuple(counts)
                )

            return

        # Maximum pieces of current size
        max_cuts = (
            (roll_width - used)
            // sizes[i]
        )

        for count in range(max_cuts + 1):

            if brake_triggered:
                break

            backtrack(
                i + 1,
                used + count * sizes[i],
                counts + [count]
            )

    backtrack(
        0,
        0,
        []
    )

    if brake_triggered:

        return [], True

    return patterns, False


# ================================================================
# 4. REMOVE DUPLICATE PATTERNS
# ================================================================

def remove_duplicate_patterns(patterns):

    return list(
        dict.fromkeys(patterns)
    )


# ================================================================
# 5. CUTTING-STOCK OPTIMIZER
# ================================================================

def optimize_patterns(
    patterns,
    customer_sizes,
    order_demand,
    max_states=500000
):

    """
    Dynamic-programming solution for the cutting-stock problem.

    Each state represents how much of every customer demand
    has already been fulfilled.

    The algorithm minimizes the number of master reels.
    """

    if not patterns:

        return None

    # ------------------------------------------------------------
    # Demand vector
    # ------------------------------------------------------------

    demands = tuple(
        int(order_demand[size])
        for size in customer_sizes
    )

    number_sizes = len(customer_sizes)

    # ------------------------------------------------------------
    # Keep only patterns that actually produce material
    # ------------------------------------------------------------

    useful_patterns = [
        pattern
        for pattern in patterns
        if sum(pattern) > 0
    ]

    if not useful_patterns:

        return {
            "success": False,
            "message": "No useful cutting patterns were generated."
        }

    patterns = useful_patterns

    # ------------------------------------------------------------
    # Starting state
    # ------------------------------------------------------------

    start = tuple(
        0
        for _ in range(number_sizes)
    )

    queue = deque([start])

    distance = {
        start: 0
    }

    parent = {}

    final_state = None

    # ------------------------------------------------------------
    # Breadth-first search
    #
    # Every level represents one additional master reel.
    # Therefore the first target reached uses the minimum
    # number of reels.
    # ------------------------------------------------------------

    while queue:

        current = queue.popleft()

        current_distance = distance[current]

        for pattern_index, pattern in enumerate(patterns):

            new_state = tuple(
                min(
                    demands[i],
                    current[i] + pattern[i]
                )
                for i in range(number_sizes)
            )

            # Pattern adds nothing useful
            if new_state == current:
                continue

            # New state
            if new_state not in distance:

                distance[new_state] = (
                    current_distance + 1
                )

                parent[new_state] = (
                    current,
                    pattern_index
                )

                # ------------------------------------------------
                # Target reached
                # ------------------------------------------------

                if new_state == demands:

                    final_state = new_state
                    queue.clear()
                    break

                queue.append(new_state)

                # ------------------------------------------------
                # Memory protection
                # ------------------------------------------------

                if len(distance) >= max_states:

                    return {
                        "success": False,
                        "message": (
                            "Optimization state limit exceeded. "
                            "Try smaller order quantities or "
                            "fewer customer sizes."
                        )
                    }

        if final_state is not None:

            break

    # ------------------------------------------------------------
    # No feasible solution
    # ------------------------------------------------------------

    if final_state is None:

        return {
            "success": False,
            "message": (
                "No feasible cutting solution was found."
            )
        }

    # ------------------------------------------------------------
    # Reconstruct selected patterns
    # ------------------------------------------------------------

    pattern_counts = [
        0
        for _ in patterns
    ]

    state = final_state

    while state != start:

        previous_state, pattern_index = parent[state]

        pattern_counts[pattern_index] += 1

        state = previous_state

    return {
        "success": True,
        "pattern_counts": pattern_counts,
        "total_rolls": distance[final_state]
    }


# ================================================================
# 6. RUN PRODUCTION OPTIMIZATION
# ================================================================

if st.button(
    "🚀 Run Production Optimization",
    type="primary"
):

    min_size = min(customer_sizes)

    simulation_results = []

    global_brake_hit = False

    # ------------------------------------------------------------
    # Safety check
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Main calculation
    # ------------------------------------------------------------

    if not global_brake_hit:

        st.header(
            "📊 Optimization Simulation Results (mm)"
        )

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

            # ----------------------------------------------------
            # Remove duplicates
            # ----------------------------------------------------

            patterns = remove_duplicate_patterns(
                patterns
            )

            # ----------------------------------------------------
            # Optimize
            # ----------------------------------------------------

            result = optimize_patterns(
                patterns,
                customer_sizes,
                order_demand
            )

            if result is None:

                st.warning(
                    f"No optimization result for "
                    f"{roll_width} mm."
                )

                continue

            if not result["success"]:

                st.warning(
                    f"⚠️ Optimization failed for "
                    f"{roll_width} mm."
                )

                st.info(
                    result["message"]
                )

                continue

            pattern_counts = result[
                "pattern_counts"
            ]

            total_rolls = result[
                "total_rolls"
            ]

            # ----------------------------------------------------
            # Material calculation
            # ----------------------------------------------------

            total_material = (
                total_rolls * roll_width
            )

            # ----------------------------------------------------
            # Calculate scrap
            # ----------------------------------------------------

            pattern_rows = []

            total_scrap = 0

            for j, pattern in enumerate(patterns):

                count = pattern_counts[j]

                if count <= 0:
                    continue

                used_width = sum(
                    pattern[i] *
                    customer_sizes[i]
                    for i in range(
                        len(customer_sizes)
                    )
                )

                scrap_per_roll = (
                    roll_width -
                    used_width
                )

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

            # ----------------------------------------------------
            # Display results
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # Store result
            # ----------------------------------------------------

            simulation_results.append(
                {
                    "RollWidth": roll_width,
                    "TotalMaterial": total_material,
                    "TotalRolls": total_rolls,
                    "TotalScrap": total_scrap
                }
            )

        # ========================================================
        # 7. FINAL RECOMMENDATION
        # ========================================================

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

            # ----------------------------------------------------
            # Summary
            # ----------------------------------------------------

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


# ================================================================
# 8. FOOTER
# ================================================================

st.divider()

st.caption(
    "📌 Professional PPC Slitting Logic — Metric Integration."
)
