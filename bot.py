
# bot.py - bot runner

import os, logging, asyncio

from discord.ext import commands
from dotenv import load_dotenv

from config import BotConfig
from exceptions import BotLoadError
from soundbyte import Soundbyte, SoundbyteHelp
from constants import resolve_path
from constants import PROJECT_ROOT, COL_GUILD, COL_SOUNDS, COL_GLOBAL, CONFIG_FILE
from store import SimpleStorage, SimpleStorageException

config = BotConfig(CONFIG_FILE)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

try:
    bot = commands.Bot(command_prefix=config.bot_prefix, help_command=None)
    bot.remove_command('help')

    logger = logging.getLogger(config.log_name)
    logger.setLevel(config.log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] |   %(message)s')

    file_handle = logging.FileHandler(resolve_path('out.log', force_exists=False), encoding='utf-8')
    file_handle.setFormatter(formatter)
    logger.addHandler(file_handle)

    if config.log_stdout:
        console_handle = logging.StreamHandler()
        console_handle.setFormatter(formatter)
        logger.addHandler(console_handle)


    store = SimpleStorage(config.storage_dir)
    store.load()
    store.use_collection(COL_GUILD)
    store.use_collection(f'{COL_SOUNDS}-{COL_GLOBAL}')

    bot.add_cog(Soundbyte(bot, config=config, logger=logger, store=store))

    asyncio.get_event_loop().run_until_complete(bot.start(TOKEN))

except (SimpleStorageException, BotLoadError) as e:
    logger.error(str(e))
    exit(1)

except KeyboardInterrupt:
    logger.info('Keyboard interrupt received, stopping bot')
    exit(0)

except Exception as e:
    logger.error(f'[uncaught error] {str(e)}')
    exit(1)