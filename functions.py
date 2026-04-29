import io
import csv
import aiohttp
import discord
import matplotlib
import matplotlib.pyplot as plt
from discord.ext import commands
from iso_codes import ISO_REGIONS, ISO_COUNTRIES
from help_text import SECTIONS, EXAMPLE

# Use non-interactive backend so matplotlib doesn't try to open a window
matplotlib.use("Agg")


# A button that appears under the embed.
# When clicked, it converts the data into a CSV file and sends it in Discord.
class DownloadButton(discord.ui.View):
    def __init__(self, rows, country_name, label, unit):
        # timeout=None means the button never expires
        super().__init__(timeout=None)
        self.rows = rows
        self.country_name = country_name
        self.label_text = label
        self.unit = unit

    @discord.ui.button(label="Download CSV", style=discord.ButtonStyle.secondary)
    async def download(self, interaction: discord.Interaction, _button: discord.ui.Button):
        try:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["Year", f"{self.label_text} ({self.unit})"])
            writer.writerows(self.rows)
            buf.seek(0)
            filename = f"{self.country_name}_{self.label_text.lower().replace(' ', '_')}.csv"
            file = discord.File(fp=io.BytesIO(buf.getvalue().encode()), filename=filename)
            await interaction.response.send_message(file=file)
        except Exception as e:
            await interaction.response.send_message(f"Error: `{e}`", ephemeral=True)


# Discord limits each embed field to 1024 characters.
# This splits the table lines into chunks that each fit under that limit.
def chunk_table(lines, limit=980):
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


# Generates a line chart from the data and returns it as an in-memory PNG file.
# No file is saved to disk — the image lives only in memory and is sent directly to Discord.
def build_chart(rows, label, country_name, unit):
    years = [r[0] for r in rows]
    values = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(years, values, marker="o", linewidth=2, color="#5865F2")
    ax.set_title(f"{label} — {country_name}", fontsize=13)
    ax.set_xlabel("Year")
    ax.set_ylabel(unit)
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()

    # Save the figure into a BytesIO buffer instead of a file
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# The core engine. This does all the heavy lifting:
# fetches data from the World Bank, formats it, builds a chart, and sends everything to Discord.
# Every command below uses this so they don't repeat the same logic.
async def world_bank_fetch(ctx, country, start, end, indicator, label, unit="USD", decimals=None):
    # Build the URL — skip the date filter if the user typed "max"
    if start.lower() == "max":
        date_param = ""
    elif end is None:
        # Single year — fetch just that one year
        date_param = f"&date={start}"
    else:
        # Range — fetch from start to end
        date_param = f"&date={start}:{end}"

    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json&per_page=100{date_param}"

    # Fetch and parse the data — using aiohttp so the bot doesn't freeze while waiting
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            payload = await resp.json()

    # The World Bank API returns a 2-element list: [metadata, data].
    # If something went wrong (bad indicator, bad country code), it returns a single error dict.
    if not isinstance(payload, list) or len(payload) < 2:
        await ctx.send(f"API error for `{country.upper()}`. Check the country code and try again.")
        return

    data = payload[1]

    if not data:
        await ctx.send(f"No data found for `{country.upper()}`.")
        return

    # Sort oldest to newest, skip years with no value
    rows = sorted(
        [(int(r["date"]), r["value"]) for r in data if r["value"] is not None],
        key=lambda x: x[0],
    )

    # Format each row — whole numbers for USD/population, 2 decimals for everything else
    if decimals is not None:
        fmt = f",.{decimals}f"
    else:
        fmt = ",.0f" if unit == "USD" else ",.2f"
    lines = [f"{year}  {value:{fmt}} {unit}" for year, value in rows]
    country_name = data[0]["country"]["value"]
    year_range = "All available data" if start.lower() == "max" else (f"{start}–{end}" if end else start)

    # Build the chart in memory
    chart = build_chart(rows, label, country_name, unit)
    chart_file = discord.File(fp=chart, filename="chart.png")

    # Split into chunks and build the embed, then attach the Download button and chart
    chunks = chunk_table(lines)
    embed = discord.Embed(title=f"{label} — {country_name} ({year_range})", color=discord.Color.blue())
    for i, chunk in enumerate(chunks):
        embed.add_field(name=unit if i == 0 else "​", value=f"```\n{chunk}\n```", inline=False)
    embed.set_image(url="attachment://chart.png")

    await ctx.send(embed=embed, file=chart_file, view=DownloadButton(rows, country_name, label, unit))


# A cog is just a container that groups related commands together.
# Discord.py requires commands to live inside a class like this.
class Economics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Nominal GDP — current USD, not adjusted for inflation
    @commands.command()
    async def gdp(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "NY.GDP.MKTP.CD", "Nominal GDP")

    # Real GDP — constant 2015 USD, adjusted for inflation
    @commands.command(name="gdp-r")
    async def gdp_r(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "NY.GDP.MKTP.KD", "Real GDP")

    # CPI — Consumer Price Index, measures inflation over time
    @commands.command()
    async def cpi(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "FP.CPI.TOTL", "CPI", unit="Index")

    # Unemployment rate — percentage of the labor force that is unemployed
    @commands.command()
    async def uem(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "SL.UEM.TOTL.ZS", "Unemployment Rate", unit="%")

    # Public debt — central government debt as a percentage of GDP
    @commands.command()
    async def debt(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "GC.DOD.TOTL.GD.ZS", "Public Debt", unit="% of GDP")

    # Inflation rate — annual % change in CPI
    @commands.command()
    async def inf(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "FP.CPI.TOTL.ZG", "Inflation Rate", unit="%")

    # Real GDP growth rate — annual % change in real GDP
    @commands.command(name="gdp-g")
    async def gdp_g(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "NY.GDP.MKTP.KD.ZG", "Real GDP Growth", unit="%")

    # GDP per capita — nominal GDP divided by population (current USD)
    @commands.command(name="gdp-pc")
    async def gdp_pc(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "NY.GDP.PCAP.CD", "GDP per Capita", unit="USD")

    # Trade balance — exports minus imports as % of GDP
    @commands.command()
    async def trade(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "NE.RSB.GNFS.ZS", "Trade Balance", unit="% of GDP")

    # FDI — foreign direct investment net inflows in current USD
    @commands.command()
    async def fdi(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "BX.KLT.DINV.CD.WD", "FDI Inflows", unit="USD")

    # Population — total population
    @commands.command()
    async def pop(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "SP.POP.TOTL", "Population", unit="People", decimals=0)

    # Gini index — measures income inequality (0 = perfect equality, 100 = perfect inequality)
    @commands.command()
    async def gini(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "SI.POV.GINI", "Gini Index", unit="Index")

    # Foreign exchange reserves — total reserves in current USD
    @commands.command()
    async def reserve(self, ctx, country: str, start: str, end: str = None):
        await world_bank_fetch(ctx, country, start, end, "FI.RES.TOTL.CD", "FX Reserves", unit="USD")

    # Shows all available commands and usage examples, one block per category
    @commands.command()
    async def menu(self, ctx):
        embed = discord.Embed(title="Available Commands", color=discord.Color.orange())
        for section, content in SECTIONS.items():
            embed.add_field(name=section, value=f"```\n{content.strip()}\n```", inline=False)
        embed.set_footer(text=EXAMPLE)
        await ctx.send(embed=embed)

    # Shows a reference list of common ISO region and country codes
    @commands.command()
    async def iso(self, ctx):
        embed = discord.Embed(title="ISO Codes", color=discord.Color.green())
        embed.add_field(name="Regions", value=f"```\n{ISO_REGIONS.strip()}\n```", inline=False)
        for chunk in chunk_table(ISO_COUNTRIES.strip().splitlines()):
            embed.add_field(name="Countries", value=f"```\n{chunk}\n```", inline=False)
        await ctx.send(embed=embed)


# Tells Discord.py to register the Economics cog when the bot loads. Required boilerplate.
async def setup(bot):
    await bot.add_cog(Economics(bot))