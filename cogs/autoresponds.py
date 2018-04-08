from cogs.cog import Cog
import re


r = re.compile('(?:^| )billy(?: |$)')


class Autoresponds(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    async def on_reaction_add(self, reaction, user):
        if isinstance(reaction.emoji, str) and reaction.emoji == '🇳🇿':
            if user.id == self.bot.user.id:
                return
            if reaction.me:
                return
            await reaction.message.add_reaction('🇳🇿')

    async def on_raw_reaction_add(self, emoji, message_id, channel_id, user_id):
        if user_id == self.bot.user.id:
            return

        if emoji.name != '🇳🇿':
            return
        await self.bot.http.add_reaction(message_id, channel_id, '🇳🇿')

    async def on_message(self, message):
        if r.findall(message.content):
            await message.add_reaction('🇫')


def setup(bot):
    bot.add_cog(Autoresponds(bot))
