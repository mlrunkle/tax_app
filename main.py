import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

st.set_page_config(page_title="Real Estate Depreciation & Tax Scenario Simulator", layout="wide")

# ---------------------------
# Helper Functions
# ---------------------------

def calculate_depreciation(property_value, land_value, dep_years, bonus_percent):
    """
    Calculate depreciation details for one year.
    Returns:
      - bonus_depreciation (immediate)
      - normal_depreciation (annual)
      - total_first_year_depreciation = bonus_depreciation + normal_depreciation
    """
    building_value = property_value - land_value
    bonus_depreciation = building_value * bonus_percent
    normal_depreciation = (building_value - bonus_depreciation) / dep_years
    first_year_dep = bonus_depreciation + normal_depreciation
    return bonus_depreciation, normal_depreciation, first_year_dep

def multi_year_cash_flow(property_value, land_value, dep_years, bonus_percent, years):
    """
    Create a DataFrame that models depreciation over multiple years.
    Assumes:
      - Bonus depreciation is taken only in Year 1.
      - Normal depreciation is taken evenly over the remaining period.
    Returns a DataFrame with:
      - Bonus Depreciation for the year
      - Normal Depreciation for the year
      - Total Depreciation for the year
      - Cumulative Depreciation over the period
    """
    building_value = property_value - land_value
    bonus_dep = building_value * bonus_percent
    remaining_basis = building_value - bonus_dep
    annual_normal_dep = remaining_basis / dep_years
    
    df = pd.DataFrame(index=range(1, years+1), columns=["Bonus Depreciation", "Normal Depreciation", "Total Depreciation", "Cumulative Depreciation"])
    cumulative = 0
    for year in range(1, years+1):
        if year == 1:
            norm = annual_normal_dep
            bonus = bonus_dep
        else:
            norm = annual_normal_dep if (year <= dep_years) else 0
            bonus = 0
        total = bonus + norm
        cumulative += total
        df.loc[year] = [bonus, norm, total, cumulative]
    return df

def calculate_sale_tax(cost_basis, sale_price, cumulative_depreciation, recapture_rate=0.25, capital_gains_rate=0.20):
    """
    Calculate the sale tax given a holding period with cumulative depreciation.
    Returns a dictionary with:
      - Adjusted Basis
      - Total Gain
      - Depreciation Recapture Tax
      - Capital Gains Tax
      - Total Tax Liability
    """
    adjusted_basis = cost_basis - cumulative_depreciation
    total_gain = sale_price - adjusted_basis

    dep_recapture_tax = cumulative_depreciation * recapture_rate
    remaining_gain = total_gain - cumulative_depreciation
    cap_gains_tax = max(remaining_gain, 0) * capital_gains_rate
    total_tax = dep_recapture_tax + cap_gains_tax

    return {
        "Adjusted Basis": adjusted_basis,
        "Total Gain": total_gain,
        "Depreciation Recapture Tax": dep_recapture_tax,
        "Capital Gains Tax": cap_gains_tax,
        "Total Tax": total_tax
    }

def simulate_1031_exchange(sale_price, total_depreciation, cost_basis, reinvested_value, recapture_rate=0.25, capital_gains_rate=0.20):
    """
    In a 1031 exchange, taxes are deferred.
    Returns the tax that would have been due if the property were sold.
    """
    tax_data = calculate_sale_tax(cost_basis, sale_price, total_depreciation, recapture_rate, capital_gains_rate)
    return tax_data["Total Tax"]

def get_asset_breakdown(property_type):
    """
    Returns a dictionary representing the asset reclassification breakdown for each property type.
    Each asset class tuple includes:
      (percentage of building value, depreciation life in years, sample asset types)
    """
    breakdown = {
        "Multifamily": {
            "5-year Assets": (0.15, 5, "Appliances, Carpets, Furniture"),
            "15-year Assets": (0.25, 15, "Land Improvements, Parking Lots, Landscaping"),
            "27.5-year Assets": (0.60, 27.5, "Structural Components, Roof, Walls, HVAC (structural)")
        },
        "Hotel": {
            "5-year Assets": (0.25, 5, "Furniture, Fixtures, Equipment"),
            "15-year Assets": (0.25, 15, "Renovations, Interior Improvements"),
            "39-year Assets": (0.50, 39, "Building Shell, Structural Components")
        },
        "Retail": {
            "5-year Assets": (0.10, 5, "Display Units, POS Equipment"),
            "15-year Assets": (0.25, 15, "Store Fixtures, Signage, Interior Finishes"),
            "39-year Assets": (0.65, 39, "Building Structure, Roof, Walls")
        },
        "Office": {
            "5-year Assets": (0.10, 5, "Furniture, Computers, Office Equipment"),
            "15-year Assets": (0.20, 15, "Partitioning, Specialized Lighting, Finishes"),
            "39-year Assets": (0.70, 39, "Building Shell, Structural Elements")
        }
    }
    return breakdown.get(property_type, {})

def compute_operating_cash_flow(df_dep, rental_income, operating_expenses, tax_bracket):
    """
    For each year, compute:
      - NOI: Rental Income minus Operating Expenses
      - Depreciation Expense for the year (from df_dep["Total Depreciation"])
      - Taxable Operating Income = NOI - Depreciation Expense (if positive; else zero)
      - Tax Liability = Taxable Operating Income * (tax_bracket / 100)
      - Operating Cash Flow = NOI - Tax Liability
      - Cumulative Operating Cash Flow
    Returns a DataFrame with these values.
    """
    cash_flow_data = []
    cumulative = 0
    for year in df_dep.index:
        depreciation = df_dep.loc[year, "Total Depreciation"]
        noi = rental_income - operating_expenses
        taxable_operating_income = noi - depreciation
        tax_liability = taxable_operating_income * (tax_bracket/100) if taxable_operating_income > 0 else 0
        operating_cf = noi - tax_liability
        cumulative += operating_cf
        cash_flow_data.append({
            "Year": year,
            "NOI": noi,
            "Depreciation": depreciation,
            "Taxable Operating Income": taxable_operating_income,
            "Tax Liability": tax_liability,
            "Operating Cash Flow": operating_cf,
            "Cumulative Operating Cash Flow": cumulative
        })
    return pd.DataFrame(cash_flow_data)

# ---------------------------
# Sidebar: Global Inputs
# ---------------------------
st.sidebar.title("Global Parameters")

# Property and Depreciation Parameters
property_value = st.sidebar.number_input("Total Property Value ($)", value=10_000_000, step=500_000)
land_value = st.sidebar.number_input("Land Value ($)", value=2_000_000, step=100_000)
dep_years = st.sidebar.number_input("Depreciation Period (years)", value=27.5, step=1.0)

# Choose the property type (influences cost segregation assumptions)
property_type = st.sidebar.selectbox("Property Type", options=["Multifamily", "Hotel", "Retail", "Office"], index=0)
default_bonus = {"Multifamily": 0.4, "Hotel": 0.5, "Retail": 0.35, "Office": 0.3}
bonus_percent = st.sidebar.slider("Bonus Depreciation % (as decimal)", min_value=0.0, max_value=1.0,
                                  value=default_bonus[property_type], step=0.05)

# Sale & Exchange Parameters
sale_price = st.sidebar.number_input("Projected Sale Price ($)", value=12_000_000, step=500_000)
simulate_exchange = st.sidebar.checkbox("Simulate 1031 Exchange", value=False)
reinvested_value = 0
if simulate_exchange:
    reinvested_value = st.sidebar.number_input("Reinvested Property Value ($)", value=12_000_000, step=500_000)

# Cash Flow & Operating Variables
years = st.sidebar.number_input("Modeling Period (years)", value=10, step=1)
tax_bracket = st.sidebar.number_input("Marginal Tax Bracket (%)", value=37, step=1)
rental_income = st.sidebar.number_input("Annual Rental Income ($)", value=500_000, step=50_000)
operating_expenses = st.sidebar.number_input("Annual Operating Expenses ($)", value=150_000, step=10_000)

# ---------------------------
# Main Tabs
# ---------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Depreciation Overview", 
    "Multi-Year Cash Flow", 
    "Sale & Tax Impact", 
    "1031 Exchange Simulation",
    "Tax Segmentation & Property Type Analysis",
    "Operating Cash Flow Analysis"
])

# ---------------------------
# Tab 1: Depreciation Overview
# ---------------------------
with tab1:
    st.header("Depreciation Overview (Year 1)")
    bonus_dep, normal_dep, first_year_dep = calculate_depreciation(property_value, land_value, dep_years, bonus_percent)
    st.write(f"**Bonus Depreciation:** ${bonus_dep:,.2f}")
    st.write(f"**Normal Depreciation (Year 1):** ${normal_dep:,.2f}")
    st.write(f"**Total First-Year Depreciation Deduction:** ${first_year_dep:,.2f}")
    if first_year_dep >= 4_000_000:
        st.success("Your first-year depreciation meets your goal of offsetting $4M in passive income!")
    else:
        st.warning("Your first-year depreciation is below $4M. Adjust the parameters to reach your goal.")

# ---------------------------
# Tab 2: Multi-Year Cash Flow
# ---------------------------
with tab2:
    st.header("Multi-Year Depreciation Cash Flow")
    df = multi_year_cash_flow(property_value, land_value, dep_years, bonus_percent, int(years))
    st.dataframe(df.style.format("${:,.2f}"))
    st.markdown("**Cumulative Depreciation** over the period can help offset passive income over time.")

# ---------------------------
# Tab 3: Sale & Tax Impact for Various Holding Periods
# ---------------------------
with tab3:
    st.header("Sale Scenario: Outcome by Holding Period")
    st.markdown("""
    The table below shows the tax implications of selling the property after different holding periods.
    For each year, the cumulative depreciation is used to determine:
    - Adjusted Basis
    - Total Gain on Sale
    - Depreciation Recapture Tax (25%)
    - Capital Gains Tax (20% on the remaining gain)
    - Total Tax Liability
    """)
    df_dep = multi_year_cash_flow(property_value, land_value, dep_years, bonus_percent, int(years))
    sale_data = []
    cost_basis = property_value
    for year in df_dep.index:
        cumulative_dep = df_dep.loc[year, "Cumulative Depreciation"]
        tax_results = calculate_sale_tax(cost_basis, sale_price, cumulative_dep)
        sale_data.append({
            "Holding Period (years)": year,
            "Cumulative Depreciation": cumulative_dep,
            "Adjusted Basis": tax_results["Adjusted Basis"],
            "Total Gain": tax_results["Total Gain"],
            "Depreciation Recapture Tax": tax_results["Depreciation Recapture Tax"],
            "Capital Gains Tax": tax_results["Capital Gains Tax"],
            "Total Tax": tax_results["Total Tax"]
        })
    sale_df = pd.DataFrame(sale_data)
    st.dataframe(sale_df.style.format({
        "Cumulative Depreciation": "${:,.2f}",
        "Adjusted Basis": "${:,.2f}",
        "Total Gain": "${:,.2f}",
        "Depreciation Recapture Tax": "${:,.2f}",
        "Capital Gains Tax": "${:,.2f}",
        "Total Tax": "${:,.2f}"
    }))

# ---------------------------
# Tab 4: 1031 Exchange Simulation
# ---------------------------
with tab4:
    st.header("1031 Exchange Simulation")
    if simulate_exchange:
        deferred_tax = simulate_1031_exchange(sale_price, first_year_dep, property_value, reinvested_value)
        st.write(f"By reinvesting in a new property valued at ${reinvested_value:,.2f}, you can defer an estimated tax of **${deferred_tax:,.2f}**.")
        st.markdown("""
        **Note:**  
        - A 1031 exchange defers both capital gains and depreciation recapture taxes.
        - This simulation provides an estimate of the deferred tax.
        - Detailed planning with a tax professional is recommended.
        """)
    else:
        st.info("Check the box above to simulate a 1031 exchange.")

# ---------------------------
# Tab 5: Tax Segmentation & Property Type Analysis
# ---------------------------
with tab5:
    st.header("Tax Segmentation & Property Type Analysis")
    st.markdown(f"### Selected Property Type: {property_type}")
    st.markdown("""
    Different property types have varying assumptions regarding bonus depreciation, depreciation periods, and asset reclassification.
    The table below shows a sample breakdown of asset classes including the percentage of building value, the depreciation life, and examples of asset types.
    """)
    asset_breakdown = get_asset_breakdown(property_type)
    if asset_breakdown:
        breakdown_data = []
        for asset_class, (pct, life, asset_types) in asset_breakdown.items():
            breakdown_data.append({
                "Asset Class": asset_class,
                "Percentage of Building Value": f"{pct*100:.0f}%",
                "Depreciation Life (years)": life,
                "Asset Types": asset_types
            })
        breakdown_df = pd.DataFrame(breakdown_data)
        st.dataframe(breakdown_df)
    else:
        st.info("No asset breakdown data available for the selected property type.")
    
    st.markdown("### Comparison of Depreciation by Property Type")
    property_types = ["Multifamily", "Hotel", "Retail", "Office"]
    default_bonuses = {"Multifamily": 0.4, "Hotel": 0.5, "Retail": 0.35, "Office": 0.3}
    comparisons = []
    for ptype in property_types:
        bonus_pct = default_bonuses[ptype]
        bonus_dep, normal_dep, first_year_dep = calculate_depreciation(property_value, land_value, dep_years, bonus_pct)
        comparisons.append({
            "Property Type": ptype,
            "Bonus %": f"{bonus_pct*100:.0f}%",
            "Bonus Depreciation": bonus_dep,
            "Normal Depreciation (Year 1)": normal_dep,
            "Total First-Year Depreciation": first_year_dep
        })
    comp_df = pd.DataFrame(comparisons)
    st.dataframe(comp_df.style.format({
        "Bonus Depreciation": "${:,.2f}", 
        "Normal Depreciation (Year 1)": "${:,.2f}", 
        "Total First-Year Depreciation": "${:,.2f}"
    }))
    
    st.markdown("""
    **Interpretation:**  
    - The breakdown table shows how much of your property’s cost may be reclassified into shorter-lived assets along with examples.
    - Compare property types to see which one provides the best tax benefits based on your assumptions.
    """)

# ---------------------------
# Tab 6: Operating Cash Flow Analysis
# ---------------------------
with tab6:
    st.header("Operating Cash Flow Analysis")
    st.markdown("""
    This analysis incorporates your annual rental income and operating expenses to calculate:
    - Net Operating Income (NOI)
    - Taxable Operating Income (NOI minus that year's depreciation)
    - Tax Liability (using your marginal tax rate)
    - Annual Operating Cash Flow and its cumulative sum.
    """)
    # Retrieve depreciation schedule
    df_dep = multi_year_cash_flow(property_value, land_value, dep_years, bonus_percent, int(years))
    op_cf_df = compute_operating_cash_flow(df_dep, rental_income, operating_expenses, tax_bracket)
    st.dataframe(op_cf_df.style.format({
        "NOI": "${:,.2f}",
        "Depreciation": "${:,.2f}",
        "Taxable Operating Income": "${:,.2f}",
        "Tax Liability": "${:,.2f}",
        "Operating Cash Flow": "${:,.2f}",
        "Cumulative Operating Cash Flow": "${:,.2f}"
    }))
    
    # Visualize annual Operating Cash Flow
    chart_data = op_cf_df[["Year", "Operating Cash Flow"]].set_index("Year")
    st.subheader("Annual Operating Cash Flow")
    st.line_chart(chart_data)
    
    # Visualize cumulative Operating Cash Flow
    cum_data = op_cf_df[["Year", "Cumulative Operating Cash Flow"]].set_index("Year")
    st.subheader("Cumulative Operating Cash Flow")
    st.area_chart(cum_data)

# ---------------------------
# Final Analysis Section
# ---------------------------
st.markdown("---")
st.header("Overall Analysis & Next Steps")
st.markdown("""
- **Depreciation & Tax Impact:** Review the multi-year depreciation and sale tax impact tables to understand your tax benefits.
- **Operating Cash Flow:** Analyze the NOI and operating cash flow visuals to assess the property’s income performance.
- **1031 Exchange:** Consider deferring taxes via a 1031 exchange for long-term planning.
- **Property Type Analysis:** Use the tax segmentation data to compare different asset reclassification scenarios.
- **Next Steps:**  
  - Adjust inputs to match specific properties in the Oklahoma City area.
  - Consider additional operating factors and consult with a tax professional or advisor.
""")
