def fmt_money(value):
    if value is None:
        return "N/A"
    return f"${float(value):,.0f}"


def fmt_pct(value):
    if value is None:
        return "N/A"
    return f"{float(value):.1f}%"


def fmt_irr(value):
    if value is None:
        return "N/A"
    value = float(value)
    if value < 1:
        value *= 100
    return f"{value:.2f}%"


def core_question_coverage(flexible_result):
    extracted_names = {
        item["metric_name"].lower()
        for item in flexible_result.get("extracted_metrics", [])
    }

    def has_any(keywords):
        return any(
            any(keyword in name for name in extracted_names)
            for keyword in keywords
        )

    checks = [
        {
            "question": "Are we performing vs plan?",
            "required": ["NOI", "Revenue", "Expense", "Occupancy", "Variance"],
            "available": [
                "NOI" if has_any(["noi", "net operating income"]) else None,
                "Revenue" if has_any(["revenue", "income"]) else None,
                "Expense" if has_any(["expense", "opex"]) else None,
                "Occupancy" if has_any(["occupancy"]) else None,
            ],
        },
        {
            "question": "Is the income durable?",
            "required": ["WALT", "Occupancy", "Tenant Concentration", "Delinquency", "Rollover"],
            "available": [
                "WALT" if has_any(["walt", "wale"]) else None,
                "Occupancy" if has_any(["occupancy"]) else None,
                "Delinquency" if has_any(["delinquency", "bad debt"]) else None,
                "Rollover" if has_any(["rollover", "expiration"]) else None,
            ],
        },
        {
            "question": "Is the leverage healthy?",
            "required": ["DSCR", "Debt Yield", "LTV", "Debt Balance", "Debt Service"],
            "available": [
                "DSCR" if has_any(["dscr"]) else None,
                "Debt Yield" if has_any(["debt yield"]) else None,
                "LTV" if has_any(["ltv", "loan to value"]) else None,
                "Debt / Loan" if has_any(["debt", "loan"]) else None,
            ],
        },
        {
            "question": "Is further capital justified?",
            "required": ["CapEx", "CapEx ROI", "Yield on Cost", "Incremental NOI"],
            "available": [
                "CapEx" if has_any(["capex", "capital"]) else None,
                "Yield on Cost" if has_any(["yield on cost"]) else None,
                "Incremental NOI" if has_any(["incremental noi"]) else None,
            ],
        },
        {
            "question": "Is the asset worth its basis?",
            "required": ["Basis", "Value", "Cap Rate", "IRR", "Equity Multiple"],
            "available": [
                "Basis" if has_any(["basis"]) else None,
                "Value" if has_any(["value", "valuation"]) else None,
                "Cap Rate" if has_any(["cap rate"]) else None,
                "IRR" if has_any(["irr"]) else None,
                "Equity Multiple" if has_any(["equity multiple"]) else None,
            ],
        },
        {
            "question": "Is risk increasing or decreasing over time?",
            "required": ["NOI Trend", "Revenue Trend", "Expense Trend", "DSCR Trend", "Occupancy Trend"],
            "available": [
                "NOI" if has_any(["noi", "net operating income"]) else None,
                "Revenue" if has_any(["revenue"]) else None,
                "Expense" if has_any(["expense", "opex"]) else None,
                "DSCR" if has_any(["dscr"]) else None,
                "Occupancy" if has_any(["occupancy"]) else None,
            ],
        },
    ]

    results = []

    for item in checks:
        available = [x for x in item["available"] if x]
        missing = [x for x in item["required"] if x not in available]
        coverage_pct = len(available) / len(item["required"])

        if coverage_pct >= 0.75:
            coverage = "high"
        elif coverage_pct >= 0.4:
            coverage = "partial"
        else:
            coverage = "low"

        results.append({
            "question": item["question"],
            "coverage": coverage,
            "available_metrics": available,
            "missing_metrics": missing,
        })

    return results


def build_analysis_context(known_result, flexible_result=None):
    acquisition = known_result["acquisition"]
    actual_2021 = known_result["actual_2021"]
    actual_2022 = known_result["actual_2022"]
    bp_2022 = known_result["business_plan_2022"]
    diagnosis = known_result["diagnosis"]
    variance = diagnosis["variance_2022"]

    original_noi = acquisition["original_noi"]
    actual_2021_noi = actual_2021["noi"]

    noi_2021_var = actual_2021_noi - original_noi
    noi_2021_var_pct = noi_2021_var / original_noi * 100 if original_noi else None

    acquisition_value = acquisition["implied_value_at_going_in_cap"]
    value_2021 = actual_2021["implied_value_at_going_in_cap"]
    value_2022 = actual_2022["implied_value_at_going_in_cap"]

    value_2021_change = value_2021 - acquisition_value
    value_2022_change = value_2022 - acquisition_value

    context = {
        "headline_finding": "The property is underperforming the 2022 business plan primarily due to operating margin compression, not severe revenue collapse.",
        "critical_metrics": {
            "2022_revenue_variance_amount": variance["revenue_variance"],
            "2022_revenue_variance_pct": variance["revenue_variance_pct"],
            "2022_opex_variance_amount": variance["opex_variance"],
            "2022_opex_variance_pct": variance["opex_variance_pct"],
            "2022_noi_variance_amount": variance["noi_variance"],
            "2022_noi_variance_pct": variance["noi_variance_pct"],
            "acquisition_unlevered_irr": acquisition.get("unlevered_irr"),
            "acquisition_levered_irr": acquisition.get("levered_irr"),
            "bp_2022_unlevered_irr": bp_2022.get("bp_unlevered_irr"),
            "bp_2022_levered_irr": bp_2022.get("bp_levered_irr"),
        },
        "acquisition_vs_2021": {
            "underwritten_noi": original_noi,
            "actual_2021_noi": actual_2021_noi,
            "variance_amount": noi_2021_var,
            "variance_pct": noi_2021_var_pct,
            "acquisition_implied_value": acquisition_value,
            "actual_2021_implied_value": value_2021,
            "value_change": value_2021_change,
        },
        "bp_2022_vs_actual_2022": {
            "bp_2022_ytd_noi": bp_2022["noi"],
            "actual_2022_ytd_noi": actual_2022["noi"],
            "bp_2022_ytd_revenue": bp_2022["revenue"],
            "actual_2022_ytd_revenue": actual_2022["revenue"],
            "bp_2022_ytd_opex": bp_2022["opex"],
            "actual_2022_ytd_opex": actual_2022["opex"],
            "variance": variance,
        },
        "value_implication": {
            "acquisition_implied_value": acquisition_value,
            "actual_2021_implied_value": value_2021,
            "actual_2022_annualized_implied_value": value_2022,
            "value_change_2021_vs_acquisition": value_2021_change,
            "value_change_2022_vs_acquisition": value_2022_change,
            "cap_rate_assumption": "same going-in cap rate",
        },
        "expense_leaks": diagnosis["top_expense_leaks"],
        "metric_catalog_coverage": None,
        "core_question_coverage": None,
    }

    if flexible_result:
        context["metric_catalog_coverage"] = {
            "total_metrics": flexible_result.get("total_metrics"),
            "extracted_count": flexible_result.get("extracted_count"),
            "missing_count": flexible_result.get("missing_count"),
            "missing_high_priority_metrics": [
                item for item in flexible_result.get("missing_metrics", [])
                if item.get("priority") in ["High", "high"]
            ][:20],
        }
        context["core_question_coverage"] = core_question_coverage(flexible_result)

    return context


def generate_performance_analysis(known_result, flexible_result=None):
    """
    Returns structured evidence only.
    GPT should generate the narrative from this object.
    """
    return build_analysis_context(known_result, flexible_result)
