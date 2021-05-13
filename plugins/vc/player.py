"""
tgvc-userbot, Telegram Voice Chat Userbot
Copyright (C) 2021  Dash Eclipse

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Putar dan Kontrol Audio yang diputar di Telegram Voice Chat

Dependencies:
- ffmpeg

Izin admin grup yang diperlukan:
- Menghapus Pesan
- Kelola obrolan suara (pilihan)

Cara Penggunaan:
- Mulai bot pengguna
- kirim! bergabung dengan obrolan grup yang mendukung obrolan suara
  dari akun userbot itu sendiri atau kontaknya
- balas audio dengan / putar untuk mulai memutar
  itu di obrolan suara, setiap anggota grup
  dapat menggunakan perintah! play sekarang
- periksa! bantuan untuk lebih banyak perintah
"""

import asyncio
import os
from datetime import datetime, timedelta

from pyrogram import Client, filters, emoji
from pyrogram.methods.messages.download_media import DEFAULT_DOWNLOAD_DIR
from pyrogram.types import Message

from utils.filters import main_filter, self_or_contact_filter
from utils.vc import mp

DELETE_DELAY = 8
DURATION_AUTOPLAY_MIN = 10
DURATION_PLAY_HOUR = 3

USERBOT_HELP = f"""{emoji.LABEL}  **Perintah Umum**:
__tersedia untuk anggota grup obrolan suara saat ini__
__dimulai dengan/(slash) atau! (tanda seru)__

\u2022 **/play**  balas dengan audio untuk memutar/mengantri, atau melihat daftar music
\u2022 **/current**  menunjukkan waktu putar trek saat ini
\u2022 **/repo**  tunjukkan repositori git dari userbot King
\u2022 `!help`  tunjukkan bantuan untuk help


{emoji.LABEL}  **Perintah Admin**:
__tersedia untuk akun userbot itu sendiri dan kontaknya__
__dimulai dengan ! (tanda seru)__

\u2022 `!skip` [n] ...  lewati saat ini atau n di mana n >= 2
\u2022 `!join`  bergabung dengan obrolan suara grup saat ini 
\u2022 `!leave`  keluar dari obrolan suara saat ini
\u2022 `!vc`  periksa VC mana yang bergabung
\u2022 `!stop`  stop memulai
\u2022 `!replay`  mainkan dari awal
\u2022 `!clean`  hapus file RAW PCM yang tidak digunakan
\u2022 `!pause` jeda pemulaian 
\u2022 `!resume` lanjutkan memulai
\u2022 `!mute`  mematikan suara bot pengguna VC
\u2022 `!unmute`  aktifkan robot pengguna VC
"""

USERBOT_REPO = f"""{emoji.ROBOT} **Telegram Voice Chat RE**

- ⚡️𝙍𝙀𝙋𝙊 𝙂𝙄𝙏𝙃𝙐𝘽⚡️: [Repo](https://github.com/yunosainth/tgvc-King)
- ⚡️𝙇𝙄𝘾𝙀𝙉𝙎𝙀⚡️: AGPL-3.0-or-later"""


# - Pyrogram filters


async def current_vc_filter(_, __, m: Message):
    group_call = mp.group_call
    if not group_call.is_connected:
        return False
    chat_id = int("-100" + str(group_call.full_chat.id))
    if m.chat.id == chat_id:
        return True
    return False


current_vc = filters.create(current_vc_filter)


# - Pyrogram handlers


@Client.on_message(
    filters.group
    & ~filters.edited
    & current_vc
    & (filters.regex("^(\\/|!)play$") | filters.audio)
)
async def play_track(client, m: Message):
    group_call = mp.group_call
    playlist = mp.playlist
    # check audio
    if m.audio:
        if m.audio.duration > (DURATION_AUTOPLAY_MIN * 60):
            reply = await m.reply_text(
                f"{emoji.ROBOT} audio yang durasinya lebih lama dari "
                f"{str(DURATION_AUTOPLAY_MIN)} min tidak akan otomatis"
                "ditambahkan ke playlist"
            )
            await _delay_delete_messages((reply,), DELETE_DELAY)
            return
        m_audio = m
    elif m.reply_to_message and m.reply_to_message.audio:
        m_audio = m.reply_to_message
        if m_audio.audio.duration > (DURATION_PLAY_HOUR * 60 * 60):
            reply = await m.reply_text(
                f"{emoji.ROBOT} audio yang durasinya lebih lama dari "
                f"{str(DURATION_PLAY_HOUR)} jam tidak akan ditambahkan ke playlist"
            )
            await _delay_delete_messages((reply,), DELETE_DELAY)
            return
    else:
        await mp.send_playlist()
        await m.delete()
        return
    # check already added
    if playlist and playlist[-1].audio.file_unique_id \
            == m_audio.audio.file_unique_id:
        reply = await m.reply_text(f"{emoji.ROBOT} Telah ditambahkan")
        await _delay_delete_messages((reply, m), DELETE_DELAY)
        return
    # add to playlist
    playlist.append(m_audio)
    if len(playlist) == 1:
        m_status = await m.reply_text(
            f"{emoji.INBOX_TRAY} mengunduh dan transcoding..."
        )
        await mp.download_audio(playlist[0])
        group_call.input_filename = os.path.join(
            client.workdir,
            DEFAULT_DOWNLOAD_DIR,
            f"{playlist[0].audio.file_unique_id}.raw"
        )
        await mp.update_start_time()
        await m_status.delete()
        print(f"- Memulai Lagu: {playlist[0].audio.title}")
    await mp.send_playlist()
    for track in playlist[:2]:
        await mp.download_audio(track)
    if not m.audio:
        await m.delete()


@Client.on_message(main_filter
                   & current_vc
                   & filters.regex("^(\\/|!)current$"))
async def show_current_playing_time(_, m: Message):
    start_time = mp.start_time
    playlist = mp.playlist
    if not start_time:
        reply = await m.reply_text(f"{emoji.PLAY_BUTTON} Tidak dikenal")
        await _delay_delete_messages((reply, m), DELETE_DELAY)
        return
    utcnow = datetime.utcnow().replace(microsecond=0)
    if mp.msg.get('current') is not None:
        await mp.msg['current'].delete()
    mp.msg['current'] = await playlist[0].reply_text(
        f"{emoji.PLAY_BUTTON}  {utcnow - start_time} / "
        f"{timedelta(seconds=playlist[0].audio.duration)}",
        disable_notification=True
    )
    await m.delete()


@Client.on_message(main_filter
                   & (self_or_contact_filter | current_vc)
                   & filters.regex("^(\\/|!)help$"))
async def show_help(_, m: Message):
    if mp.msg.get('help') is not None:
        await mp.msg['help'].delete()
    mp.msg['help'] = await m.reply_text(USERBOT_HELP, quote=False)
    await m.delete()


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.command("skip", prefixes="!"))
async def skip_track(_, m: Message):
    playlist = mp.playlist
    if len(m.command) == 1:
        await mp.skip_current_playing()
    else:
        try:
            items = list(dict.fromkeys(m.command[1:]))
            items = [int(x) for x in items if x.isdigit()]
            items.sort(reverse=True)
            text = []
            for i in items:
                if 2 <= i <= (len(playlist) - 1):
                    audio = f"[{playlist[i].audio.title}]({playlist[i].link})"
                    playlist.pop(i)
                    text.append(f"{emoji.WASTEBASKET} {i}. **{audio}**")
                else:
                    text.append(f"{emoji.CROSS_MARK} {i}")
            reply = await m.reply_text("\n".join(text))
            await mp.send_playlist()
        except (ValueError, TypeError):
            reply = await m.reply_text(f"{emoji.NO_ENTRY} masukan tidak valid",
                                       disable_web_page_preview=True)
        await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & filters.regex("^!join$"))
async def join_group_call(client, m: Message):
    group_call = mp.group_call
    group_call.client = client
    if group_call.is_connected:
        await m.reply_text(f"{emoji.ROBOT} sudah bergabung dengan obrolan suara")
        return
    await group_call.start(m.chat.id)
    await m.delete()


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!leave$"))
async def leave_voice_chat(_, m: Message):
    group_call = mp.group_call
    mp.playlist.clear()
    group_call.input_filename = ''
    await group_call.stop()
    await m.delete()


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & filters.regex("^!vc$"))
async def list_voice_chat(client, m: Message):
    group_call = mp.group_call
    if group_call.is_connected:
        chat_id = int("-100" + str(group_call.full_chat.id))
        chat = await client.get_chat(chat_id)
        reply = await m.reply_text(
            f"{emoji.MUSICAL_NOTES} **saat ini di obrolan suara**:\n"
            f"- **{chat.title}**"
        )
    else:
        reply = await m.reply_text(emoji.NO_ENTRY
                                   + "belum bergabung dengan obrolan suara apa pun")
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!stop$"))
async def stop_playing(_, m: Message):
    group_call = mp.group_call
    group_call.stop_playout()
    reply = await m.reply_text(f"{emoji.STOP_BUTTON} Memberhentikan lagu")
    await mp.update_start_time(reset=True)
    mp.playlist.clear()
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!replay$"))
async def restart_playing(_, m: Message):
    group_call = mp.group_call
    if not mp.playlist:
        return
    group_call.restart_playout()
    await mp.update_start_time()
    reply = await m.reply_text(
        f"{emoji.COUNTERCLOCKWISE_ARROWS_BUTTON}  "
        "Memulai dari awal..."
    )
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!pause"))
async def pause_playing(_, m: Message):
    mp.group_call.pause_playout()
    await mp.update_start_time(reset=True)
    reply = await m.reply_text(f"{emoji.PLAY_OR_PAUSE_BUTTON} jeda",
                               quote=False)
    mp.msg['pause'] = reply
    await m.delete()


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!resume"))
async def resume_playing(_, m: Message):
    mp.group_call.resume_playout()
    reply = await m.reply_text(f"{emoji.PLAY_OR_PAUSE_BUTTON} lanjutkan",
                               quote=False)
    if mp.msg.get('pause') is not None:
        await mp.msg['pause'].delete()
    await m.delete()
    await _delay_delete_messages((reply,), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!clean$"))
async def clean_raw_pcm(client, m: Message):
    download_dir = os.path.join(client.workdir, DEFAULT_DOWNLOAD_DIR)
    all_fn: list[str] = os.listdir(download_dir)
    for track in mp.playlist[:2]:
        track_fn = f"{track.audio.file_unique_id}.raw"
        if track_fn in all_fn:
            all_fn.remove(track_fn)
    count = 0
    if all_fn:
        for fn in all_fn:
            if fn.endswith(".raw"):
                count += 1
                os.remove(os.path.join(download_dir, fn))
    reply = await m.reply_text(f"{emoji.WASTEBASKET} dibersihkan {count} file")
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!mute$"))
async def mute(_, m: Message):
    group_call = mp.group_call
    group_call.set_is_mute(True)
    reply = await m.reply_text(f"{emoji.MUTED_SPEAKER} bisu")
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & self_or_contact_filter
                   & current_vc
                   & filters.regex("^!unmute$"))
async def unmute(_, m: Message):
    group_call = mp.group_call
    group_call.set_is_mute(False)
    reply = await m.reply_text(f"{emoji.SPEAKER_MEDIUM_VOLUME} tidak dibisukan")
    await _delay_delete_messages((reply, m), DELETE_DELAY)


@Client.on_message(main_filter
                   & current_vc
                   & filters.regex("^(\\/|!)repo$"))
async def show_repository(_, m: Message):
    if mp.msg.get('repo') is not None:
        await mp.msg['repo'].delete()
    mp.msg['repo'] = await m.reply_text(
        USERBOT_REPO,
        disable_web_page_preview=True,
        quote=False
    )
    await m.delete()


# - Other functions

async def _delay_delete_messages(messages: tuple, delay: int):
    await asyncio.sleep(delay)
    for m in messages:
        await m.delete()
