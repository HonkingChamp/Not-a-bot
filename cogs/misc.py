from discord.ext.commands import BucketType

from bot.bot import command, cooldown
from cogs.cog import Cog
from utils import wolfram, memes


class Misc(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    @command()
    @cooldown(1, 2, type=BucketType.user)
    async def math(self, ctx, *, query):
        """Queries a math problem to be solved by wolfram alpha"""
        await ctx.send(await wolfram.math(query, self.bot.aiohttp_client,
                                          self.bot.config.wolfram_key))

    @command(name='say')
    @cooldown(1, 2, BucketType.channel)
    async def say_command(self, ctx, *, words):
        """Says the text that was put as a parameter"""
        await ctx.send('{0} {1}'.format(ctx.author.mention, words))

    @command(ignore_extra=True, aliases=['twitchquotes'])
    @cooldown(1, 2, type=BucketType.guild)
    async def twitchquote(self, ctx, tts: bool=None):
        """Random twitch quote from twitchquotes.com"""
        await ctx.send(await memes.twitch_poems(self.bot.aiohttp_client), tts=tts)


def setup(bot):
    bot.add_cog(Misc(bot))
