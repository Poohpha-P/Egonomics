# Descriptions for every bot command, grouped by section.
# Shown when the user types !menu. Edit here to update the menu.

SECTIONS = {
    "GDP": """
!gdp    [ISO] [start] [end/max]   Nominal GDP (current USD)
!gdp-r  [ISO] [start] [end/max]   Real GDP (constant 2015 USD)
!gdp-g  [ISO] [start] [end/max]   Real GDP growth rate (%)
!gdp-pc [ISO] [start] [end/max]   GDP per capita (current USD)
""",
    "Prices & Inflation": """
!cpi    [ISO] [start] [end/max]   Consumer Price Index
!inf    [ISO] [start] [end/max]   Inflation rate (annual %)
""",
    "Labour": """
!uem    [ISO] [start] [end/max]   Unemployment rate (%)
""",
    "Government": """
!debt   [ISO] [start] [end/max]   Public debt (% of GDP)
""",
    "Trade & Finance": """
!trade   [ISO] [start] [end/max]  Trade balance (% of GDP)
!fdi     [ISO] [start] [end/max]  FDI net inflows (USD)
!reserve [ISO] [start] [end/max]  Foreign exchange reserves (USD)
""",
    "Society": """
!pop    [ISO] [start] [end/max]   Total population
!gini   [ISO] [start] [end/max]   Gini inequality index (0-100)
""",
    "Reference": """
!iso    Show ISO country and region codes
!menu   Show this command list
""",
}

EXAMPLE = "Example:  !gdp US 2014 2024  |  !inf TH max  |  !pop CN 2000 2020"
