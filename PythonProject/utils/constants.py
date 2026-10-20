"""Constants used throughout the DeepFocus application."""

import os
import json
import threading

_CONFIG_LOCK = threading.RLock()
from enum import Enum

APP_NAME = "Focus"
APP_VERSION = "1.0.0"
APP_SUITE = "Spertulo Utility"

WINDOW_WIDTH = 1240
WINDOW_HEIGHT = 800

# Paddock-inspired graphite, warm white and precision red.
BG_PRIMARY = ("#F3F2F0", "#090B0F")
BG_SECONDARY = ("#E8E7E4", "#1B222C")
BG_CARD = ("#FFFFFF", "#12151B")
SIDEBAR_BG = ("#ECEBE8", "#0A0E16")
HOVER_BG = ("#E6E4E1", "#232C3B")
SEPARATOR_COLOR = ("#D7D6D2", "#272C35")
INPUT_BG = ("#EEEDEB", "#1B222C")
INPUT_BTN_COLOR = INPUT_BG
INPUT_BTN_HOVER = HOVER_BG
BLUE = "#CF352B"
RED = "#E73A2E"
BLUE_HOVER = "#B82B22"
RED_HOVER = "#FF5441"
ACCENT_COLOR = (BLUE, RED)
ACCENT_HOVER = (BLUE_HOVER, RED_HOVER)
ACCENT_FOCUS = ACCENT_COLOR
ACCENT_BREAK = ("#087C74", "#97D8E9")
ACCENT_SOUND = ACCENT_COLOR
ACCENT_STATS = ACCENT_COLOR
ACCENT_CUSTOM = ACCENT_COLOR
ACCENT_DANGER = ("#B12D26", "#CC3830")
ACCENT_HOVER_PRIMARY = ACCENT_HOVER
ACCENT_HOVER_BREAK = ACCENT_HOVER
ACCENT_HOVER_SOUND = ACCENT_HOVER
ACCENT_HOVER_STATS = ACCENT_HOVER
ACCENT_HOVER_DARK = ACCENT_HOVER
TEXT_PRIMARY = ("#1E252F", "#EFF2F7")
TEXT_SECONDARY = ("#586373", "#A6B0BF")
TEXT_MUTED = ("#677180", "#8F9BAD")
ICE = ("#276A7A", "#97D8E9")
SELECTED_BG = ("#F6E5E2", "#241E26")
SELECTED_BORDER = ("#DBA49D", "#68373A")

# Timer defaults
DEFAULT_FOCUS_MINUTES = 25
DEFAULT_SHORT_BREAK_MINUTES = 5
DEFAULT_LONG_BREAK_MINUTES = 15
SESSIONS_BEFORE_LONG_BREAK = 4

# Default blocked websites (www. variants are auto-added when blocking)
DEFAULT_BLOCKED_SITES = [
    "facebook.com",
    "youtube.com",
    "tiktok.com",
    "reddit.com",
    "x.com",
    "instagram.com",
    "threads.net",
]

# Default blocked apps list
DEFAULT_BLOCKED_APPS = ["Discord.exe", "Steam.exe", "Zalo.exe", "Telegram.exe"]

# Sound constants
SAMPLE_RATE = 44100
CHUNK_SIZE = 1024
SOUND_TYPES = [
    "rain",
    "brown_noise",
    "pink_noise",
    "white_noise",
    "432hz_focus",
    "binaural_alpha",
    "binaural_gamma"
]
SOUND_LABELS = {
    "432hz_focus": "432 Hz Tone",
    "binaural_alpha": "10 Hz Binaural",
    "binaural_gamma": "40 Hz Binaural",
    "brown_noise": "Brown Noise",
    "pink_noise": "Pink Noise",
    "white_noise": "White Noise",
    "rain": "Steady Rain"
}
SOUND_DESCRIPTIONS = {
    "rain": "Recorded rainfall with a soft, steady texture.",
    "brown_noise": "Deep, bass-heavy noise with a gentle upper end.",
    "pink_noise": "Warm, balanced noise with equal energy per octave.",
    "white_noise": "Bright, even noise across the audible spectrum.",
    "432hz_focus": "A pure, sustained 432 Hz sine tone.",
    "binaural_alpha": "220 Hz left · 230 Hz right. Use stereo headphones.",
    "binaural_gamma": "220 Hz left · 260 Hz right. Use stereo headphones."
}

# Health tips list (English)
HEALTH_TIPS = [
    "👀 Look at something 20 feet away for 20 seconds",
    "💧 Drink a glass of water",
    "🧘 Stretch your neck and shoulders gently",
    "🚶 Stand up and walk around for a minute",
    "🫁 Take 5 deep breaths",
    "✋ Rotate your wrists to reduce strain",
    "😌 Close your eyes and relax for 30 seconds"
]

# Database path
DB_DIR = os.path.join(os.path.expanduser("~"), ".deepfocus")
DB_PATH = os.path.join(DB_DIR, "deepfocus.db")
CONFIG_PATH = os.path.join(DB_DIR, "config.json")

class TimerState(Enum):
    """Timer states enum."""
    IDLE = "idle"
    FOCUSING = "focusing"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    PAUSED = "paused"


def resolve_color(color) -> str:
    """Resolve a (light, dark) color tuple to a single hex string based on current theme.
    Used for Canvas/matplotlib which don't support CTk color tuples."""
    if isinstance(color, (list, tuple)) and len(color) == 2:
        import customtkinter as ctk
        mode = ctk.get_appearance_mode()
        return color[0] if mode == "Light" else color[1]
    return color


def load_config() -> dict:
    """Load app config from JSON file."""
    default_config = {
        "close_to_tray": True,
        "theme": "dark", 
        "active_mode": "Default",
        "run_on_startup": False,
        "mini_player_enabled": False,
        "global_hotkeys": False,
        "global_hotkey_bind": "ctrl+shift+space",
        "hardcore_sites": [
            "facebook.com",
            "youtube.com",
            "tiktok.com",
            "reddit.com",
            "x.com",
            "instagram.com",
            "threads.net",
            "netflix.com",
            "twitch.tv",
            "twitter.com",
            "pinterest.com",
            "snapchat.com",
            "tumblr.com",
            "linkedin.com",
            "vimeo.com",
            "dailymotion.com",
            "hulu.com",
            "disneyplus.com",
            "primevideo.com",
            "hbomax.com",
            "crunchyroll.com",
            "9gag.com",
            "buzzfeed.com",
            "vkontakte.ru",
            "weibo.com",
            "discord.com",
            "whatsapp.com",
            "web.whatsapp.com",
            "telegram.org",
            "messenger.com",
            "quora.com",
            "medium.com",
            "news.ycombinator.com",
            "digg.com",
            "spotify.com",
            "soundcloud.com",
            "apple.com/music",
            "pandora.com",
            "4chan.org",
            "imgur.com",
            "gfycat.com",
            "flickr.com",
            "devianart.com",
            "wattpad.com",
            "fanfiction.net",
            "archiveofourown.org",
            "roblox.com",
            "minecraft.net",
            "epicgames.com",
            "steampowered.com",
            "origin.com",
            "uplay.com",
            "ea.com",
            "riotgames.com",
            "bilibili.com",
            "wechat.com",
            "tinder.com",
            "bumble.com",
            "omegle.com",
            "chatroulette.com",
            "pornhub.com",
            "xvideos.com",
            "onlyfans.com"
],
        "hardcore_apps": [
            "Discord.exe",
            "Steam.exe",
            "Zalo.exe",
            "Telegram.exe",
            "LeagueClient.exe",
            "VALORANT-Win64-Shipping.exe",
            "Spotify.exe",
            "GenshinImpact.exe",
            "EpicGamesLauncher.exe",
            "csgo.exe",
            "cs2.exe",
            "dota2.exe",
            "Overwatch.exe",
            "Wow.exe",
            "gtav.exe",
            "Cyberpunk2077.exe",
            "r5apex.exe",
            "FortniteClient-Win64-Shipping.exe",
            "PUBG_EXEC.exe",
            "TslGame.exe",
            "hl2.exe",
            "minecraft.exe",
            "RobloxPlayerBeta.exe",
            "osu!.exe",
            "vlc.exe",
            "WhatsApp.exe",
            "Messenger.exe",
            "Netflix.exe",
            "iTunes.exe",
            "AmazonMusic.exe",
            "Battle.net.exe",
            "Origin.exe",
            "upc.exe",
            "EAConnect_CX.exe",
            "GalaxyClient.exe",
            "qbittorrent.exe",
            "uTorrent.exe",
            "BitTorrent.exe",
            "League of Legends.exe",
            "WeChat.exe",
            "Line.exe",
            "Viber.exe",
            "TikTok.exe",
            "Instagram.exe",
            "Facebook.exe",
            "Twitter.exe",
            "Pinterest.exe",
            "Reddit.exe",
            "9gag.exe",
            "CandyCrush.exe",
            "Solitaire.exe",
            "Minesweeper.exe",
            "mpc-hc64.exe",
            "potplayermini64.exe",
            "Rockstar-Games-Launcher.exe",
            "RiotClientServices.exe",
            "SteamService.exe"
]
    }
    
    os.makedirs(DB_DIR, exist_ok=True)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Merge defaults
                for k, v in default_config.items():
                    if k not in user_config:
                        user_config[k] = v
                return user_config
        except Exception:
            pass
    return default_config


def save_config(config: dict) -> None:
    """Save app config to JSON file atomically."""
    os.makedirs(DB_DIR, exist_ok=True)
    temp_path = f"{CONFIG_PATH}.tmp"
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        os.replace(temp_path, CONFIG_PATH)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Could not save settings")
        raise OSError("Could not save settings. Check the data folder permissions.") from e


def update_config(changes: dict) -> dict:
    """Merge only changed keys into the latest file, never a stale app snapshot."""
    with _CONFIG_LOCK:
        config = load_config()
        config.update(changes)
        save_config(config)
        return config
