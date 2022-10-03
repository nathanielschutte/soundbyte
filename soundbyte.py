
# soundbyte.py - The Soundbyte Cog

import logging, os, json, asyncio

import discord
from discord.ext import commands

from exceptions import BotLoadError
from config import BotConfig
from constants import AUDIO_FILE_TYPES, resolve_path
from constants import COL_GLOBAL, COL_GUILD, COL_SOUNDS, PROJECT_ROOT, CONFIG_FILE, AUDIO_FILE_EXT, OUTRO_TIMEOUT
from store import SimpleStorage, SimpleStorageException

class Soundbyte(commands.Cog):
    """Soundbyte discord Cog"""

    def __init__(self, bot, commands_file=f'{__name__}.json', config=None, logger=None, store=None) -> None:

        self.bot = bot

        if config is None or not isinstance(config, BotConfig):
            raise BotLoadError('Bot requires Config object')
        if logger is None or not isinstance(logger, logging.Logger):
            raise BotLoadError('Bot requires Logger object')
        if store is None or not isinstance(store, SimpleStorage):
            raise BotLoadError('Bot requires SimpleStorage object')

        if not os.path.isfile(resolve_path(commands_file)):
            raise BotLoadError(f'Commands file not found: {commands_file}')
        self.commands_file = commands_file

        try:
            with open(commands_file, 'r') as file:
                self.commands = json.loads(file.read())
        except Exception as e:
            raise BotLoadError(f'Commands file not parseable: {commands_file} [{str(e)}]')


        self.config: BotConfig = config
        self.logger: logging.Logger = logger
        self.store: SimpleStorage = store
        self.helper = SoundbyteHelp(self.config, self.commands)

        self.loop = asyncio.get_event_loop()

        self.logger.info('Instantiating bot...')
        


    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f'{self.config.bot_prefix}help'))
        self.logger.info('Bot is ready')


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if not isinstance(error, commands.errors.CommandNotFound):
            logging.error(f'command error: {str(error)}')


    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        guild = str(msg.guild.id)
        guilds = self.store.get_collection(COL_GUILD)

        # make sure to load guild data
        if guild not in guilds:
            guilds[guild] = {}
            self.store.set_collection(COL_GUILD, guilds)
            self.store.persist_collection(COL_GUILD)
        if 'prefix' not in guilds[guild]:
            guilds[guild]['prefix'] = self.config.bot_prefix
            self.store.set_collection(COL_GUILD, guilds)
            self.store.persist_collection(COL_GUILD)

        # message content
        content = msg.content.strip()
        
        # command
        if len(content) > 1 and content[0] == guilds[guild]['prefix'] and content[1] != ' ':
            cmd_contents = content[1:].split()
            command = cmd_contents[0]
            args = cmd_contents[1:]

            # check for aliases
            for cmd, data in self.commands.items():
                if 'aliases' in data and command in data['aliases']:
                    command = cmd
                    break

            # check for declared command
            if command in self.commands:

                # command disabled
                if 'disabled' in self.commands[command] and self.commands[command]['disabled'] == 1:
                    return

                self.logger.debug(f'user {msg.author.display_name} called on: \'{command}\'')

                method_name = command

                if 'function' in self.commands[command]:
                    method_name = self.commands[command]['function']

                if hasattr(self, method_name):
                    method = getattr(self, method_name)
                    if asyncio.iscoroutinefunction(method):

                        # check arg minimum requirement
                        if 'argmin' in self.commands[command] and len(args) < self.commands[command]['argmin']:
                            if 'usage' in self.commands[command]:
                                await msg.channel.send(f'Usage: `{guilds[guild]["prefix"]}{command} {self.commands[command]["usage"]}`')
                            return
                        
                        #self.logger.debug(f'executing function for: \'{command}\'')
                        self.loop.create_task(method(msg, *args))
                    else:
                        self.logger.error(f'function not coroutine for command: {command}')
                else:
                    self.logger.error(f'could not find function to call for command: {command}')


    # Needed for other soundbit commands
    def _ensure_collection(self, guild_id):
        # set up the soundbit store - use defaults
        if not self.store.has_collection(f'{COL_SOUNDS}-{guild_id}'):
            self.store.use_collection(f'{COL_SOUNDS}-{guild_id}')
            self.logger.info(f'first time guild [{guild_id}], creating collection')

        # get global tracks
        track_globals = None
        if self.store.has_collection(f'{COL_SOUNDS}-{COL_GLOBAL}'):
            track_globals = self.store.get_collection(f'{COL_SOUNDS}-{COL_GLOBAL}')
            
        track_store = self.store.get_collection(f'{COL_SOUNDS}-{guild_id}')

        # if no bits, load the globals
        if 'bits' not in track_store:
            if track_globals is not None and 'bits' in track_globals and isinstance(track_globals['bits'], dict):
                track_store['bits'] = track_globals['bits']
                self.logger.info(f'no bits in new guild [{guild_id}], adding {len(track_globals["bits"].keys())} global sounds')
            else:
                track_store['bits'] = {}

            self.store.set_collection(f'{COL_SOUNDS}-{guild_id}', track_store)
            self.store.persist_collection(f'{COL_SOUNDS}-{guild_id}')

        return track_store


    # Play a sound in a channel, towards a target user, specified track
    async def _play_sound(self, msg, track_name, timeout=None):
        target = msg.author

        if timeout is None:
            timeout = self.config.audio_timeout

        # author isnt in a channel, see if anyone else is
        if target.voice is None or target.voice.channel is None:
            audio_channels = msg.guild.voice_channels
            #print(f'audio channels: {audio_channels}')
            for ac in audio_channels:
                #print(f'voice states in channel {ac.name}: {ac.voice_states}')
                for user_id, vs in ac.voice_states.items():
                    if vs.channel is not None and not vs.self_deaf:
                        channel = vs.channel
                        break
                if channel is not None:
                    break

        # pick author's channel alternatively (priority)
        else:
            channel = target.voice.channel

        # there is a joinable channel
        if channel is None:
            return

        # make sure bot isnt already connected 
        for vc in self.bot.voice_clients:
            if vc.channel.id == channel.id:
                self.logger.debug(f'bot already connected to the channel! {channel.id}')
                return

        # read audio bit file
        audio_dir = os.path.join(self.config.audio_root, self.config.audio_server_storage)
        filename = os.path.join(audio_dir, f'{msg.guild.id}', track_name + '.' + AUDIO_FILE_EXT)
        if not os.path.isfile(filename):

            # check in the comman dir
            audio_dir = os.path.join(self.config.audio_root, self.config.audio_common_storage)
            filename = os.path.join(audio_dir, track_name + '.' + AUDIO_FILE_EXT)
            
            if not os.path.isfile(filename):
                self.logger.error(f'sound error: \'{filename} not found\'')
                return

        # connect to voice channel
        try:
            vc = await channel.connect(timeout=2.0) # get voice client
        except discord.ClientException:
            self.logger.debug(f'bot already connected to the channel! {channel.id}')
            return
        except asyncio.TimeoutError:
            self.logger.error(f'connecting to channel {channel.id} timed out!')
            return

        # play the audio file
        vc.play(discord.FFmpegPCMAudio(executable=self.config.ffmpeg_exe, source=filename))

        # wait on it...asyncio timeout didnt seem to work
        while timeout > 0 and vc.is_playing() and vc.is_connected():
            await asyncio.sleep(1.0)
            timeout -= 1

        if vc.is_playing():
            vc.stop()

        if vc.is_connected():
            await vc.disconnect()


    # Command function template
    # async def command(self, msg: discord.Message, *args)

    # Commands
    async def sound(self, msg: discord.Message, *args):
        if len(args) < 1:
            await msg.channel.send('Please name the sound you want to hear')
            return

        track_name = args[0]
        track_store = self._ensure_collection(msg.guild.id)

        # ensure store is ok
        tracks = track_store['bits']

        # convert to new store
        if isinstance(tracks, list):
            new_store = {}

            for track in tracks:
                new_store[track] = {
                    'name': track,
                    'outro': {},
                    'intro': {}
                }
                
            track_store['bits'] = new_store

            self.store.set_collection(f'{COL_SOUNDS}-{msg.guild.id}', new_store)
            self.store.persist_collection(f'{COL_SOUNDS}-{msg.guild.id}')

        if not isinstance(tracks, dict):
            self.logger.error(f'error reading track store for server [{msg.guild.name}]')
            return
        
        # check for this audio file
        if not track_name in tracks:
            await msg.channel.send(f'I don\'t know the sound `{track_name}`')
            return
        
        await self._play_sound(msg, track_name)


    async def add(self, msg: discord.Message, *args):
        if len(args) < 1:
            await msg.channel.send('Please name the sound you want to hear')
            return
        if len(args) > 1:
            await msg.channel.send('Please use a single word to name the sound')
            return

        track_name = args[0]

        if track_name is None or len(track_name.strip()) == 0:
            await msg.channel.send('Please include a name for this soundbit!')
            return

        guild = str(msg.guild.id)
        guilds = self.store.get_collection(COL_GUILD)

        # Look for sound attachment
        added = False
        async for message in msg.channel.history(limit=2):
            att = message.attachments
            for media in att:
                type = media.content_type.split('/')
                if type[0] == 'audio':
                    if type[1] in AUDIO_FILE_TYPES:
                        self.logger.debug(f'found sound in {msg.channel.name} [format={type[1]}], saving')

                        # check on server dir
                        audio_dir = resolve_path(os.path.join(self.config.audio_root, self.config.audio_server_storage, f'{msg.guild.id}'), force_exists=False)
                        if not os.path.isdir(audio_dir):
                            try:
                                os.mkdir(audio_dir)
                            except Exception as e:
                                self.logger.error(f'could not create new server dir: {str(e)}')
                                return
                        
                        # save sound
                        filename = os.path.join(audio_dir, track_name    + '.' + AUDIO_FILE_EXT)
                        await media.save(filename)

                        track_store = self._ensure_collection(msg.guild.id)

                        # ensure store is ok
                        tracks = track_store['bits']
                        
                        # convert to new store
                        if isinstance(tracks, list):
                            new_store = {}

                            for track in tracks:
                                new_store[track] = {
                                    'name': track,
                                    'outro': {},
                                    'intro': {}
                                }

                            track_store['bits'] = new_store

                            self.store.set_collection(f'{COL_SOUNDS}-{msg.guild.id}', new_store)
                            self.store.persist_collection(f'{COL_SOUNDS}-{msg.guild.id}')

                        if not isinstance(tracks, dict):
                            self.logger.error(f'error reading track store for server ({msg.guild.name})')
                            return

                        # add file to store - if it already exists, it will now be overwritten
                        if track_name not in tracks:
                            self.logger.info(f'appending track to guild ({msg.guild.name}): {track_name}')
                            
                            track_store['bits'][track_name] = {
                                'name': track_name,
                                'outro': {},
                                'intro': {}
                            }

                            self.store.set_collection(f'{COL_SOUNDS}-{msg.guild.id}', track_store)
                            self.store.persist_collection(f'{COL_SOUNDS}-{msg.guild.id}')

                            await msg.channel.send(f'Added new sound `{track_name}`')
                            added = True

                        break

                    else:
                        await msg.channel.send('Unsupported file type \'' + type[1] + '\'')
                        return
                else:
                    await msg.channel.send('Unsupported file type \'' + type[1] + '\'')
                    return

        if not added:
            await msg.channel.send(f'Send an audio file in chat, then type `{guilds[guild]["prefix"]}add [name]`')


    async def list(self, msg: discord.Message, *args):
        track_store = self._ensure_collection(msg.guild.id)
        tracks = track_store['bits']

        author_id = msg.author.id
        author_display_name = msg.author.display_name

        # convert to new store
        if isinstance(tracks, list):
            new_store = {}

            for track in tracks:
                new_store[track] = {
                    'name': track,
                    'outro': {},
                    'intro': {}
                }

            track_store['bits'] = new_store
            
            self.store.set_collection(f'{COL_SOUNDS}-{msg.guild.id}', track_store)
            self.store.persist_collection(f'{COL_SOUNDS}-{msg.guild.id}')

        if not isinstance(tracks, dict):
            self.logger.error(f'error reading track store for server [{msg.guild.name}]')
            return

        if len(tracks) == 0:
            guild = str(msg.guild.id)
            guilds = self.store.get_collection(COL_GUILD)
            
            await msg.channel.send(f'No soundbits stored!  Upload an mp3, then type `{guilds[guild]["prefix"]}add [name]` to add one.')
        else:
            track_list = []

            for track_name, track_data in tracks.items():
                track_str = f'{track_name}'

                # outro: { 'nates_id': { display_name: 'drunk_irishman', id: 'nates_id' } }
                if 'outro' in track_data and isinstance(track_data['outro'], dict) and len(track_data['outro'].keys()) > 0:
                    track_str += f' (outro for: `{", ".join([user["display_name"] for user in track_data["outro"].values()])}`)'

                track_list.append(track_str)

            track_str = "\n".join(track_list)

            await msg.channel.send(embed=discord.Embed(title='Tracks', description=track_str))


    async def setoutro(self, msg: discord.Message, *args):
        outro_name = args[0]
        
        author_id = str(msg.author.id)
        author_display_name = msg.author.display_name

        track_store = self._ensure_collection(msg.guild.id)
        tracks = track_store['bits']

        if not isinstance(tracks, dict):
            self.logger.error(f'error reading track store for server [{msg.guild.name}]')
            return

        if outro_name not in tracks:
            await msg.channel.send(f'Sound does not exist: {outro_name}')
            return

        for bit_name, bit_data in tracks.items():
            if str(author_id) in bit_data['outro']:
                del track_store['bits'][bit_name]['outro'][str(author_id)]

        if str(author_id) not in track_store['bits'][outro_name]['outro']:
            track_store['bits'][outro_name]['outro'][str(author_id)] = {
                'display_name': author_display_name,
                'id': author_id
            }

        self.store.set_collection(f'{COL_SOUNDS}-{msg.guild.id}', track_store)
        self.store.persist_collection(f'{COL_SOUNDS}-{msg.guild.id}')

        await msg.channel.send(f'Set user `{author_display_name}` outro to `{outro_name}`')
        

    # Play user outro
    async def outro(self, msg: discord.Message, *args):
        guild = str(msg.guild.id)
        guilds = self.store.get_collection(COL_GUILD)
        
        author_id = str(msg.author.id)
        author_display_name = msg.author.display_name

        track_store = self._ensure_collection(msg.guild.id)
        tracks = track_store['bits']

        for bit_name in tracks.keys():
            if str(author_id) in tracks[bit_name]['outro']:
                
                # play outro music
                await self._play_sound(msg, bit_name, timeout=OUTRO_TIMEOUT)

                # disconnect user
                await msg.author.move_to(None)
                return

        await msg.channel.send(f'No outro set for you, {author_display_name}. Use `{guilds[guild]["prefix"]}setoutro [sound name]` to set your outro sound.')
    

    # Set server prefix
    async def setprefix(self, msg: discord.Message, *args):

        if len(args) < 1 or len(args[0]) > 1:
            await msg.channel.send('Please specify a single-character prefix')
            return

        prefix = args[0][0]

        guild = str(msg.guild.id)
        guilds = self.store.get_collection(COL_GUILD)

        guilds[guild]['prefix'] = prefix

        self.store.set_collection(COL_GUILD, guilds)
        self.store.persist_collection(COL_GUILD)


    async def help(self, msg: discord.Message, *args):
        guild = str(msg.guild.id)
        guilds = self.store.get_collection(COL_GUILD)
        
        await self.helper.send_bot_help(msg.channel, guilds[guild]['prefix'])

        

class SoundbyteHelp(commands.HelpCommand):
    '''Bot commands help'''

    def __init__(self, config, commands):
        super().__init__()

        self.config = config
        self.commands = commands
        

    async def send_bot_help(self, channel, prefix):
        embed = discord.Embed(title=f'{self.config.bot_title} help:')
        for cmd_name, cmd in self.commands.items():

            # skip commands that have a permission besides 'any', or are disabled
            if 'permission' in cmd and cmd['permission'] != 'any':
                continue
            if 'disabled' in cmd and cmd['disabled'] == 1:
                continue

            if 'desc' not in cmd:
                cmd['desc'] = ''
            if 'usage' not in cmd:
                cmd['usage'] = ''

            cmdstr = f'{cmd["desc"]}\n`{prefix}{cmd_name} {cmd["usage"]}`'
            embed.add_field(name=f'{cmd_name}:', value=cmdstr, inline=False)
            
        await channel.send(embed=embed)


    async def send_cog_help(self, cog):
        return await super().send_cog_help(cog)


    async def send_group_help(self, group):
        return await super().send_group_help(group)


    async def send_command_help(self, command):
        return await super().send_command_help(command)
