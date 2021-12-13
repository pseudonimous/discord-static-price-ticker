from .utils import checks
from datetime import datetime
from dateutil import parser
from discord.ext import commands
from discord.ext import tasks
import discord
import math
import pycoingecko


DATETIME_FORMAT_STRING = "%Y-%m-%d %H:%M"
DATE_FORMAT_STRING = "%Y-%m-%d"
HUMAN_READABLE_SUFFIXES = ("", "K", "M", "B", "T", "Q")


class TickerCog(commands.Cog, name='Cryptocurrency'):
    """Commands for managing ticker and alerts"""

    def __init__(self, bot):
        self.bot = bot
        self.previous_price = -1
        self.crypto_name = self.bot.config["cryptocurrency_name"]
        self.crypto_id = self.bot.config["cryptocurrency_id"]
        self.fiat_name = self.bot.config["fiat_name"]
        self.fiat_id = self.bot.config["fiat_id"]
        cursor = self.bot.database.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS ppa("invoker_id" INT, "price" REAL, "timestamp" INT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS cpa("channel_id" INT, "invoker_id" INT, "price" REAL, "timestamp" INT)')
        self.bot.database.commit()
        self.ticker_task.start()
        
        
    def human_readable(self, number):
        base = 1000
        multiple = math.trunc(math.log2(number) / math.log2(base))
        value = number / math.pow(base, multiple)
        suffix = HUMAN_READABLE_SUFFIXES[multiple]
        precision = self.bot.config["human_readable_precision"]
        if precision == 0:
            return str(int(value)) + suffix
        return f"{value:.{precision}f}{suffix}"
        
    @tasks.loop(seconds=5)
    async def ticker_task(self):
        coingecko = pycoingecko.CoinGeckoAPI()
        precision = self.bot.config["presence_precision"]
        prices = coingecko.get_price(ids=self.crypto_id, vs_currencies=self.fiat_id)
        history = coingecko.get_coin_market_chart_by_id(id=self.crypto_id, vs_currency=[self.fiat_id], days='1')
        price_fiat = prices[self.crypto_id][self.fiat_id]
        percentage = ((prices[self.crypto_id][self.fiat_id] / history['prices'][0][1]) - 1) * 100
        difference = prices[self.crypto_id][self.fiat_id] - history['prices'][0][1]
        for g in self.bot.guilds:
            if precision == 0:
                await g.me.edit(nick=f"{self.crypto_name}: {self.fiat_name}{int(price_fiat)}")
            else:
                await g.me.edit(nick=f"{self.crypto_name}: {self.fiat_name}{price_fiat:.{precision}f}")
        status = discord.Status.idle
        if percentage < -2:
            status = discord.Status.dnd
        elif percentage > 2:
            status = discord.Status.online
        if precision == 0:
            status_string = f"+{self.fiat_name}{int(difference)} (+{percentage:.2f}%)" if percentage >= 0 else f"-{self.fiat_name}{abs(int(difference))} ({percentage:.2f}%)"
        else:
            status_string = f"+{self.fiat_name}{difference:.{precision}f} (+{percentage:.2f}%)" if percentage >= 0 else f"-{self.fiat_name}{abs(difference):.{precision}f} ({percentage:.2f}%)"
        # price alerts
        cursor = self.bot.database.cursor()
        if self.previous_price != -1:
            cursor.execute('SELECT invoker_id, price, timestamp FROM ppa')
            self.bot.database.commit()
            ppa_rows = cursor.fetchall()
            for i in range(0, len(ppa_rows)):
                row = ppa_rows[i]
                invoker = self.bot.get_user(row[0])
                price = row[1]
                timestamp = datetime.fromtimestamp(row[2]).strftime(DATETIME_FORMAT_STRING)
                right_now = datetime.utcnow().strftime("%H:%M")
                if invoker == None:
                    continue
                # easier way to check, whether the price alert is in between previous and now
                if (price - price_fiat) * (self.previous_price - price) >= 0 and price:
                    embed = discord.Embed(title=f":bellhop:  Price Alert: **{self.crypto_name}** just hit **{self.fiat_name}{price}**!", color=(0xd92b47 if self.previous_price > price_fiat else 0x7ab160),
                                          description=f"You're receiving this message because at {timestamp}, you set a price alert for **{self.crypto_name}** at **{self.fiat_name}{price}**\nRight now, at {right_now}, **{self.crypto_name}** is worth **{self.fiat_name}{price_fiat}**.")
                    embed.set_footer(text="All times in UTC.")
                    try:
                        await invoker.send(embed=embed)
                    except:
                        self.bot.logger.warn(f"Unable to send price alert to {invoker.id} :(")
                    cursor.execute("DELETE FROM ppa WHERE price = ? AND invoker_id = ?", (price, invoker.id))
                    self.bot.database.commit()
            cursor.execute('SELECT invoker_id, price, timestamp, channel_id FROM cpa')
            self.bot.database.commit()
            cpa_rows = cursor.fetchall()
            for i in range(0, len(cpa_rows)):
                row = cpa_rows[i]
                invoker = row[0]
                price = row[1]
                timestamp = datetime.fromtimestamp(row[2]).strftime(DATETIME_FORMAT_STRING)
                channel = self.bot.get_channel(row[3])
                right_now = datetime.utcnow().strftime("%H:%M")
                if channel == None:
                    continue
                # easier way to check, whether the price alert is in between previous and now
                if (price - price_fiat) * (self.previous_price - price) >= 0 and price:
                    embed = discord.Embed(title=f":bellhop:  Price Alert: **{self.crypto_name}** just hit **{self.fiat_name}{price}**!", color=(0xd92b47 if self.previous_price > price_fiat else 0x7ab160),
                                          description=f"You're receiving this message because at {timestamp}, <@{invoker}> set a price alert for **{self.crypto_name}** at **{self.fiat_name}{price}**\nRight now, at {right_now}, **{self.crypto_name}** is worth **{self.fiat_name}{price_fiat}**.")
                    embed.set_footer(text="All times in UTC.")
                    try:
                        await channel.send(embed=embed)
                    except:
                        self.bot.logger.warn(f"Unable to send price alert to {channel.id} :(")
                    cursor.execute("DELETE FROM cpa WHERE price = ? AND channel_id = ?", (price, channel.id))
                    self.bot.database.commit()
        await self.bot.change_presence(status=status, activity=discord.Activity(type=discord.ActivityType.watching, name=status_string))
        self.previous_price = price_fiat

    @ticker_task.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        
    @commands.command(name="ppa-add", aliases=["ppa-a", "add-ppa"])
    async def ppa_add(self, ctx, price: float):
        """Adds a personal price alert at a given price"""
        if price < 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  You cannot set a price alert for a price lower than 0!", color=self.bot.embed_color))
        if math.isnan(price):
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  Please stick to existing numbers for price alerts. :)", color=self.bot.embed_color))
        if math.isinf(price):
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  To the moon, yes. But not to infinity.", color=self.bot.embed_color))
        limit = self.bot.config["max_ppa"]
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT price FROM ppa WHERE invoker_id = ?', (ctx.author.id,))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) >= limit:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  You've exceeded the personal price alert limit of **{limit}**!", color=self.bot.embed_color))
        for i in range(0, len(rows)):
            row = rows[i]
            if row[0] == price:
                return await ctx.send(embed=discord.Embed(title=f":no_entry:  You already have a personal price alert at **{self.fiat_name}{price}**!", color=self.bot.embed_color))
        cursor.execute("INSERT INTO ppa(invoker_id, price, timestamp) VALUES (?, ?, ?)", (ctx.author.id, price, int(datetime.utcnow().timestamp())))
        self.bot.database.commit()
        embed = discord.Embed(title=f":white_check_mark:  Successfully added a personal price alert for **{self.crypto_name}** at **{self.fiat_name}{price}**.", color=self.bot.embed_color)
        embed.set_footer(text="Remember to keep your DMs open!")
        return await ctx.send(embed=embed)
    
    @commands.command(name="ppa-list", aliases=["ppa-l", "lsppa", "list-ppa"])
    async def ppa_list(self, ctx):
        """Lists all the personal price alerts"""
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT price, timestamp FROM ppa WHERE invoker_id = ?', (ctx.author.id,))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) == 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  You have no personal price alerts!", color=self.bot.embed_color))
        embed = discord.Embed(title=f":page_with_curl:  List of **{ctx.author}**'s personal price alerts", color=self.bot.embed_color)
        embed.set_footer(text="All times in UTC.")
        for i in range(0, len(rows)):
            row = rows[i]
            price = row[0]
            timestamp = datetime.fromtimestamp(row[1]).strftime(DATETIME_FORMAT_STRING)
            embed.add_field(name=f"{self.fiat_name}{price}", value=f"from {timestamp}", inline=False)
        return await ctx.send(embed=embed)
    
    @commands.command(name="ppa-remove", aliases=["ppa-r", "ppa-rm", "ppa-rem", "rm-ppa", "rem-ppa", "remove-ppa"])
    async def ppa_remove(self, ctx, price: float):
        """Removes a personal price alert"""
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT timestamp FROM ppa WHERE invoker_id = ? AND price = ?', (ctx.author.id,price))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) == 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  You don't have a personal price alert at **{self.fiat_name}{price}!**", color=self.bot.embed_color))
        cursor.execute("DELETE FROM ppa WHERE price = ? AND invoker_id = ?", (price, ctx.author.id))
        self.bot.database.commit()
        return await ctx.send(embed=discord.Embed(title=":wastebasket:  Personal price alert removed.", color=self.bot.embed_color))
    
    @commands.command(name="cpa-add", aliases=["cpa-a", "add-cpa"])
    @checks.is_mod()
    @commands.guild_only()
    async def cpa_add(self, ctx, price: float):
        """Adds a channel price alert at a given price"""
        if price < 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  You cannot set a price alert for a price lower than 0!", color=self.bot.embed_color))
        if math.isnan(price):
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  Please stick to existing numbers for price alerts. :)", color=self.bot.embed_color))
        if math.isinf(price):
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  To the moon, yes. But not to infinity.", color=self.bot.embed_color))
        limit = self.bot.config["max_cpa"]
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT price FROM cpa WHERE channel_id = ?', (ctx.channel.id,))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) >= limit:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  The channel price alert of **{limit}** has been exceeded for this channel!", color=self.bot.embed_color))
        for i in range(0, len(rows)):
            row = rows[i]
            if row[0] == price:
                return await ctx.send(embed=discord.Embed(title=f":no_entry:  There's already a channel price alert at **{self.fiat_name}{price}**!", color=self.bot.embed_color))
        cursor.execute("INSERT INTO cpa(channel_id, invoker_id, price, timestamp) VALUES (?, ?, ?, ?)", (ctx.channel.id, ctx.author.id, price, int(datetime.utcnow().timestamp())))
        self.bot.database.commit()
        return await ctx.send(embed=discord.Embed(title=f":white_check_mark:  Successfully added a channel price alert for **{self.crypto_name}** at **{self.fiat_name}{price}**.", color=self.bot.embed_color))

    @commands.command(name="cpa-list", aliases=["cpa-l", "lscpa", "list-cpa"])
    @commands.guild_only()
    async def cpa_list(self, ctx):
        """Lists all the channel price alerts"""
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT price, timestamp, invoker_id FROM cpa WHERE channel_id = ?', (ctx.channel.id,))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) == 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  There are no channel price alerts for this channel.", color=self.bot.embed_color))
        embed = discord.Embed(title=f":page_with_curl:  List of channel price alerts for **#{ctx.channel.name}**", color=self.bot.embed_color)
        embed.set_footer(text="All times in UTC.")
        for i in range(0, len(rows)):
            row = rows[i]
            price = row[0]
            timestamp = datetime.fromtimestamp(row[1]).strftime(DATETIME_FORMAT_STRING)
            invoker_id = row[2]
            embed.add_field(name=f"{self.fiat_name}{price}", value=f"by <@{invoker_id}> from {timestamp}", inline=False)
        return await ctx.send(embed=embed)
    
    @commands.command(name="cpa-remove", aliases=["cpa-r", "cpa-rm", "cpa-rem", "rm-cpa", "rem-cpa", "remove-cpa"])
    @checks.is_mod()
    @commands.guild_only()
    async def cpa_remove(self, ctx, price: float):
        """Removes a channel price alert"""
        cursor = self.bot.database.cursor()
        cursor.execute('SELECT timestamp FROM cpa WHERE channel_id = ? AND price = ?', (ctx.channel.id,price))
        self.bot.database.commit()
        rows = cursor.fetchall()
        if len(rows) == 0:
            return await ctx.send(embed=discord.Embed(title=f":no_entry:  There's no personal price alert at **{self.fiat_name}{price}!** for this channel", color=self.bot.embed_color))
        cursor.execute("DELETE FROM cpa WHERE price = ? AND channel_id = ?", (price, ctx.channel.id))
        self.bot.database.commit()
        return await ctx.send(embed=discord.Embed(title=":wastebasket:  Channel price alert removed.", color=self.bot.embed_color))
    
    @commands.command(name="stats", aliases=["cap", "mcap", "supply", "rank", "volume"])
    async def stats(self, ctx):
        """Shows general stats about the cryptocurrency"""
        precision = self.bot.config["stats_precision"]
        coingecko = pycoingecko.CoinGeckoAPI()
        history = coingecko.get_coin_market_chart_by_id(id=self.crypto_id, vs_currency=[self.fiat_id], days='1')
        markets = coingecko.get_coins_markets(ids=self.bot.config["cryptocurrency_id"], vs_currency=self.fiat_id, order="market_cap_desc", per_page=100, page=1, sparkline=False)[0]
        market_cap = self.fiat_name + self.human_readable(markets["market_cap"]) if self.bot.config["human_readable_stats"] else self.fiat_name + "{:,}".format(markets["market_cap"])
        circulating_supply = self.human_readable(markets["circulating_supply"]) if self.bot.config["human_readable_stats"] else "{:,}".format(markets["circulating_supply"])
        try:
            total_supply = self.human_readable(markets["total_supply"]) + " " if self.bot.config["human_readable_stats"] else "{:,}".format(markets["total_supply"]) + " "
        except TypeError:
            total_supply = "???"
        supply = (circulating_supply + " / " + total_supply).replace(".0 ", " ").replace(" / ???", "")
        price = self.fiat_name + str(round(markets["current_price"], precision))
        percentage = ((markets["current_price"] / history['prices'][0][1]) - 1) * 100
        difference = markets["current_price"] - history['prices'][0][1]
        if precision == 0:
            change = f"+{self.fiat_name}{int(difference)} (+{percentage:.2f}%)" if percentage >= 0 else f"-{self.fiat_name}{abs(int(difference))} ({percentage:.2f}%)"
        else:
            change = f"+{self.fiat_name}{difference:.{precision}f} (+{percentage:.2f}%)" if percentage >= 0 else f"-{self.fiat_name}{abs(difference):.{precision}f} ({percentage:.2f}%)"
        total_volume = self.human_readable(markets["total_volume"]) if self.bot.config["human_readable_stats"] else "{:,}".format(markets["total_volume"])
        embed = discord.Embed(title=f":bar_chart:  Statistics for **{self.crypto_name}**", color=self.bot.embed_color)
        if self.bot.config["human_readable_stats"]:
            embed.set_footer(text="Some values are approximates.")
        embed.add_field(name="Rank⠀", value=("#" + str(markets["market_cap_rank"])) + "⠀", inline=True)
        embed.add_field(name="Market Cap⠀", value=market_cap + "⠀", inline=True)
        embed.add_field(name="Circulating Supply", value=supply + "", inline=True)
        embed.add_field(name="Price⠀", value=price + "⠀", inline=True)
        embed.add_field(name="Change (24h)⠀", value=change + "⠀", inline=True)
        embed.add_field(name="Volume (24h)⠀", value=total_volume + "⠀", inline=True)
        return await ctx.send(embed=embed)
    
    @commands.command(name="ath", aliases=["all-time-high"])
    async def ath(self, ctx):
        """Shows the cryptocurrency's all-time high"""
        precision = self.bot.config["stats_precision"]
        coingecko = pycoingecko.CoinGeckoAPI()
        markets = coingecko.get_coins_markets(ids=self.bot.config["cryptocurrency_id"], vs_currency=self.fiat_id, order="market_cap_desc", per_page=100, page=1, sparkline=False)[0]
        ath_fiat = markets["ath"]
        ath_time = parser.parse(markets["ath_date"])
        ath_change = markets["ath_change_percentage"]
        embed = discord.Embed(title=f":chart_with_upwards_trend:  **{self.crypto_name}**'s all-time high is **{self.fiat_name}{ath_fiat:.{precision}f}**.", color=self.bot.embed_color)
        if ath_time.hour == 0 and ath_time.minute == 0:
            embed.description = f"All-time high was hit at **{ath_time.strftime(DATE_FORMAT_STRING)}**.\nChange to current price: **{ath_change:.2f}%**."
        else:
            embed.description = f"All-time high was hit at **{ath_time.strftime(DATETIME_FORMAT_STRING)}** (UTC).\nChange to current price: **{ath_change:.2f}%**."
        await ctx.send(embed=embed)
            
    @commands.command(name="atl", aliases=["all-time-low"])
    async def atl(self, ctx):
        """Shows the cryptocurrency's all-time low"""
        precision = self.bot.config["stats_precision"]
        coingecko = pycoingecko.CoinGeckoAPI()
        markets = coingecko.get_coins_markets(ids=self.bot.config["cryptocurrency_id"], vs_currency=self.fiat_id, order="market_cap_desc", per_page=100, page=1, sparkline=False)[0]
        atl_fiat = markets["atl"]
        atl_time = parser.parse(markets["atl_date"])
        atl_change = markets["atl_change_percentage"]
        embed = discord.Embed(title=f":chart_with_downwards_trend:  **{self.crypto_name}**'s all-time low is **{self.fiat_name}{atl_fiat:.{precision}f}**.", color=self.bot.embed_color)
        if atl_time.hour == 0 and atl_time.minute == 0:
            embed.description = f"All-time low was hit at **{atl_time.strftime(DATE_FORMAT_STRING)}**.\nChange to current price: **{atl_change:.2f}%**."
        else:
            embed.description = f"All-time low was hit at **{atl_time.strftime(DATETIME_FORMAT_STRING)}** (UTC).\nChange to current price: **{atl_change:.2f}%**."
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(TickerCog(bot))

