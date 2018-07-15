import csv
import json
import math
import os
import textwrap
import re
from functools import partial

from discord import utils, Embed
from discord.embeds import EmptyEmbed
from discord.errors import HTTPException
from discord.ext.commands import cooldown, BucketType
from discord.ext.commands.converter import UserConverter
from discord.ext.commands.errors import BadArgument, UserInputError

from bot.bot import command
from bot.exceptions import BotException
from bot.globals import POKESTATS
from cogs.cog import Cog
from utils.utilities import basic_check, random_color

pokestats = re.compile(r'''Level (?P<level>\d+) "?(?P<name>.+?)"?
.+?
(Holding: .+?\n)?Nature: (?P<nature>\w+)
HP: (?P<hp>\d+)( - IV: (?P<hp_iv>\d+)/\d+)?
Attack: (?P<attack>\d+)( - IV: (?P<attack_iv>\d+)/\d+)?
Defense: (?P<defense>\d+)( - IV: (?P<defense_iv>\d+)/\d+)?
Sp. Atk: (?P<spattack>\d+)( - IV: (?P<spattack_iv>\d+)/\d+)?
Sp. Def: (?P<spdefense>\d+)( - IV: (?P<spdefense_iv>\d+)/\d+)?
Speed: (?P<speed>\d+)( - IV: (?P<speed_iv>\d+)/\d+)?''')

pokemon = {}
stat_names = ('hp', 'attack', 'defense', 'spattack', 'spdefense', 'speed')
MAX_IV = (31, 31, 31, 31, 31, 31)
MIN_IV = (0, 0, 0, 0, 0, 0)

legendary_detector = re.compile(r'Congratulations (<@!?\d+>)! You caught a level \d+ (.+?)!')
legendaries = ['arceus', 'articuno', 'azelf', 'blacephalon', 'buzzwole',
               'celebi', 'celesteela', 'cobalion', 'cosmoem', 'cosmog',
               'cresselia', 'darkrai', 'deoxys', 'dialga', 'diancie',
               'entei', 'genesect', 'giratina', 'groudon', 'guzzlord',
               'heatran', 'ho-oh', 'hoopa', 'jirachi', 'kartana', 'keldeo',
               'kyogre', 'kyurem', 'landorus', 'latias', 'latios', 'lugia',
               'lunala', 'magearna', 'manaphy', 'marshadow', 'meloetta',
               'mesprit', 'mew', 'mewtwo', 'moltres', 'naganadel', 'necrozma',
               'nihilego', 'palkia', 'pheromosa', 'phione', 'poipole', 'raikou',
               'rayquaza', 'regice', 'regigigas', 'regirock', 'registeel',
               'reshiram', 'shaymin', 'silvally', 'solgaleo', 'stakataka',
               'suicune', 'tapu bulu', 'tapu fini', 'tapu koko', 'tapu lele',
               'terrakion', 'thundurus', 'tornadus', 'type: null', 'uxie',
               'victini', 'virizion', 'volcanion', 'xerneas', 'xurkitree',
               'yveltal', 'zapdos', 'zekrom', 'zeraora', 'zygarde']



# Stats taken from https://www.kaggle.com/mylesoneill/pokemon-sun-and-moon-gen-7-stats
with open(os.path.join(POKESTATS, 'pokemon.csv'), 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    keys = ('ndex', 'hp', 'attack', 'defense', 'spattack', 'spdefense', 'speed')
    for row in reader:
        name = None

        if '(Mega ' in row['forme']:
            name = row['forme']
            name = 'mega' + name.split('(Mega')[1].split(')')[0].lower()

        elif '(Primal Reversion)' in row['forme']:
            name = 'primal ' + row['species'].lower()

        else:
            name = row['species'].lower()

        if name in pokemon:
            continue

        pokemon[name] = {k: int(row[k]) for k in keys}

with open(os.path.join(POKESTATS, 'natures.json'), 'r') as f:
    natures = json.load(f)

# Good work from https://github.com/xKynn/PokecordCatcher
with open(os.path.join(POKESTATS, 'pokemonrefs.json'), 'r') as f:
    pokemonrefs = json.load(f)


# Below functions ported from https://github.com/dalphyx/pokemon-stat-calculator
# Formulas from https://bulbapedia.bulbagarden.net/wiki/Statistic
def calc_stat(iv, base, ev=0, level=1, nature=1):
    result = math.floor(((2 * base + iv + math.floor(ev / 4)) * level) / 100 + 5) * nature
    result = math.floor(result)
    return result


def calc_iv(value, base, ev=0, level=1, nature=1):
    return max(math.floor((100 * value / nature - 500) / level) - math.floor(ev / 4) - 2 * base, 0)


def calc_hp_iv(hp, base, ev=0, level=1):
    return max(math.floor((100 * hp - 1000) / level - 2 * base - math.floor(ev / 4) - 100), 0)


def iv_range(level, natures, stats, base):
    ivs = []

    def get_range(get_stat, get_iv, stat, base, nature=None):
        iv_small = None
        iv_big = 31
        if nature is None:
            iv_guess = get_iv(stat, base, ev=102, level=level)
        else:
            iv_guess = get_iv(stat, base, ev=102, level=level, nature=nature)

        if nature is not None:
            get_stat = partial(get_stat, nature=nature)
        if get_stat(iv_guess, base, ev=102, level=level) != stat:
            for iv in range(1, 32):
                if get_stat(iv, base, ev=102, level=level) == stat:
                    iv_guess = iv


        for iv in range(32):
            stat_new = get_stat(iv, base, ev=102, level=level)
            if stat_new == stat and iv_small is None:
                iv_small = iv
                continue

            if stat_new != stat:
                if iv_small is None:
                    continue
                iv_big = iv - 1
                break

        if iv_small is None:
            return 'N/A'

        return list(range(iv_small, iv_big+1))

    ivs.append(get_range(calc_hp_stats, calc_hp_iv, stats[0], base[0]))
    for stat, base_, nature in zip(stats[1:], base[1:], natures):
        ivs.append(get_range(calc_stat, calc_iv, stat, base_, nature=nature))

    return ivs


def calc_hp_stats(iv, base, ev, level):
    # No.292 Shedinja's HP always be 1.
    if base == 1:
        return 1

    result = math.floor((2 * base + iv + math.floor(ev / 4)) * level / 100) + level + 10
    return result


def get_base_stats(name: str):
    poke = pokemon.get(name.lower())
    if not poke:
        raise BotException(f"Could not find pokemon `{name}`"
                           "Make sure you replace the nickname to the pokemons real name or this won't work")

    return tuple(poke[stat] for stat in stat_names)


def calc_all_stats(name, level, nature, evs=(102, 102, 102, 102, 102, 102), ivs=MAX_IV, with_max_level=False):
    if isinstance(nature, str):
        nature_ = natures.get(nature.lower())
        if not nature_:
            raise BotException(f'Could not find nature `{nature}`')

        nature = nature_

    base_stats = get_base_stats(name)

    def calc_stats(lvl):
        st = [calc_hp_stats(ivs[0], base_stats[0], evs[0], lvl)]

        for i in range(1, 6):
            st.append(calc_stat(ivs[i], base_stats[i], evs[i], lvl, nature[i - 1]))

        return st

    stats = calc_stats(level)
    if with_max_level and level != 100:
        max_stats = calc_stats(100)
    elif with_max_level:
        max_stats = stats

    if with_max_level:
        return stats, max_stats

    return stats


def from_max_stat(min: int, max: int, value: int) -> tuple:
    """
    Gets where the stats stands between the max and min
    Args:
        min: min value
        max: max value
        value: the current value of the stat

    Returns: tuple
        Percentage on how close the value is to the max and the actual diff to max
    """
    d = value - min
    from_max = max - value
    diff = max - min
    if diff == 0:
        delta = 'N/A'
    else:
        delta = d/diff

    return delta, from_max


class Pokemon(Cog):
    def __init__(self, bot):
        super().__init__(bot)

    @command(aliases=['pstats', 'pstat'])
    @cooldown(1, 3, BucketType.user)
    async def poke_stats(self, ctx, *, stats=None):
        """
        Calculate how good your pokemons stats are.
        To be used in combination with pokecord

        How to use:
        Use p!info (use whatever prefix pokecord has on the server instead of p!)
        Copy the fields from Level to Speed. Then use the command as follows
        {prefix}pstats

        or manually

        {prefix}pstats Level 100 Pikachu
        2305/2610XP
        Nature: Hasty
        HP: 300
        Attack: 300
        Defense: 300
        Sp. Atk: 300
        Sp. Def: 300
        Speed: 300
        """
        async def process_embed(embed):
            stats = embed.title + '\n' + embed.description.replace('*', '')

            match = pokestats.match(stats)
            if not match:
                await ctx.send("Failed to parse stats. Make sure it's the correct format")
                return

            pokemon_name = pokemonrefs.get(embed.image.url.split('/')[-1].split('.')[0])
            if not pokemon_name:
                await ctx.send('Could not get pokemon name from message. Please give the name of the pokemon')
                msg = await self.bot.wait_for('message', check=basic_check(author=ctx.author, channel=ctx.channel),
                                              timeout=30)
                pokemon_name = msg.content

            stats = match.groupdict()
            stats['name'] = pokemon_name

            return stats

        def check_msg(msg):
            embed = msg.embeds[0]
            if embed.title != EmptyEmbed and embed.title.startswith('Level '):
                return embed

        author = None
        try:
            if stats:
                author = await (UserConverter().convert(ctx, stats))
        except UserInputError:
            pass

        if not author:
            try:
                stats = int(stats)
            except (ValueError, TypeError):
                author = ctx.author
                not_found = 'Could not find p!info message'
                accept_any = True
                if stats:
                    match = pokestats.match(stats)
                    if not match:
                        await ctx.send("Failed to parse stats. Make sure it's the correct format")
                        return

                    stats = match.groupdict()

        else:
            stats = None
            not_found = f'No p!info message found for user {author}'
            accept_any = False

        if not stats:
            _embed = None
            async for msg in ctx.channel.history():
                if msg.author.id != 365975655608745985:
                    continue
                if not msg.embeds:
                    continue
                embed = msg.embeds[0]
                if embed.title != EmptyEmbed and embed.title.startswith('Level '):
                    if author.avatar_url.startswith(embed.thumbnail.url):
                        _embed = embed
                        break
                    if accept_any and _embed is None:
                        _embed = embed

            if _embed is None:
                await ctx.send(not_found)
                return

            stats = await process_embed(_embed)

        elif isinstance(stats, int):
            try:
                msg = await ctx.channel.get_message(stats)
            except HTTPException as e:
                return await ctx.send(f'Could not get message with id `{stats}` because of an error\n{e}')

            embed = check_msg(msg)
            stats = await process_embed(embed)

        try:
            level = int(stats['level'])
        except ValueError:
            raise BadArgument('Could not convert level to integer')

        current_stats = []
        try:
            for name in stat_names:
                iv = stats[name + '_iv']
                if iv is not None:
                    stats[name + '_iv'] = int(iv)
                i = int(stats[name])
                current_stats.append(i)
                stats[name] = i
        except ValueError:
            raise BadArgument(f'Failed to convert {name} to integer')

        nature = stats['nature'].lower()

        try:
            max_stats = calc_all_stats(stats['name'], level, nature)
            min_stats = calc_all_stats(stats['name'], level, nature, ivs=MIN_IV)
        except KeyError as e:
            return await ctx.send(f"{e}\nMake sure you replace the nickname to the pokemons real name in the message or this won't work")

        s = f'```py\nLevel {stats["level"]} {stats["name"]}\nStat: Max value | Delta | Percentage | lvl 100 | iv\n'

        nature_mod = natures[nature]
        base_stats = get_base_stats(stats['name'])
        if stats['hp_iv'] is not None:
            iv_ranges = []
            for name in stat_names:
                iv_ranges.append((stats[name + '_iv'], ))
        else:
            iv_ranges = iv_range(level, nature_mod, current_stats, base_stats)
        idx = 0
        for min_val, max_val, name, ivs in zip(min_stats, max_stats, stat_names, iv_ranges):
            diff, from_max = from_max_stat(min_val, max_val, stats[name])
            fill = ' ' * (11 - len(name))
            fill2 = ' ' * (4 - len(str(max_val)))
            fill3 = ' ' * (6 - len(str(from_max)))

            if isinstance(diff, float):
                diff = f'{diff*100:.0f}%'
            fill4 = ' ' * (11 - len(diff))

            if ivs == 'N/A':
                ivs = (0, 31)
                iv = 'N/A'
            elif len(ivs) == 1:
                iv = str(ivs[0])
            else:
                iv = f'{ivs[0]}-{ivs[-1]}'

            if idx == 0:
                minimum = calc_hp_stats(ivs[0], base_stats[idx], 102, 100)
                maximum = calc_hp_stats(ivs[-1], base_stats[idx], 102, 100)
            else:
                minimum = calc_stat(ivs[0], base_stats[idx], 102, 100, nature_mod[idx - 1])
                maximum = calc_stat(ivs[-1], base_stats[idx], 102, 100, nature_mod[idx - 1])

            if maximum == minimum:
                stat_range = str(maximum)
            else:
                stat_range = f'{minimum}-{maximum}'

            idx += 1

            fill5 = ' ' * (8 - len(stat_range))
            s += f'{name}:{fill}{max_val}{fill2}| {from_max}{fill3}| {diff}{fill4}| {stat_range}{fill5}| {iv}\n'
        s += '```'
        await ctx.send(s)

    async def on_message(self, message):
        # Ignore others than pokecord
        if message.author.id != 365975655608745985:
            return

        if not message.content:
            return

        channel = utils.get(message.guild.channels, name='pokelog')
        if not channel:
            return

        perms = channel.permissions_for(message.guild.get_member(self.bot.user.id))
        if not (perms.send_messages and perms.read_messages and perms.embed_links):
            return

        match = legendary_detector.match(message.content)
        if not match:
            return

        mention, poke = match.groups()
        if poke.lower() not in legendaries:
            return

        url = 'http://play.pokemonshowdown.com/sprites/xyani/%s.gif' % re.sub(r' |:|-', '', poke).lower()
        embed = Embed(description=f'{mention} caught a **{poke}**', colour=random_color())
        embed.set_image(url=url)
        icon = 'https://raw.githubusercontent.com/msikma/pokesprite/master/icons/pokemon/regular/%s.png' % re.sub(' |: ', '-', poke).lower()
        embed.set_thumbnail(url=icon)

        await channel.send(embed=embed)

    @command(aliases=['pstats_format'], ignore_extra=True)
    async def pstat_format(self, ctx):
        await ctx.send(textwrap.dedent("""
        Level 100 Pikachu
        2305/2610XP
        Nature: Hasty
        HP: 300
        Attack: 300
        Defense: 300
        Sp. Atk: 300
        Sp. Def: 300
        Speed: 300"""))


def setup(bot):
    bot.add_cog(Pokemon(bot))