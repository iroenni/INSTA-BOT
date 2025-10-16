import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
import instagrapi
from config import *

app = Client("instagram_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
ig = instagrapi.Client()

# Estados del usuario
user_states = {}

class UserState:
    def __init__(self):
        self.waiting_for_caption = False
        self.video_path = None
        self.video_duration = None

def login_instagram():
    try:
        ig.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        return True
    except Exception as e:
        print(f"Error Instagram login: {e}")
        return False

def check_video_requirements(duration, file_size):
    """Verificar requisitos de Instagram"""
    if duration > 60:
        return False, "❌ El video debe ser menor a 60 segundos"
    if file_size > 100 * 1024 * 1024:  # 100MB
        return False, "❌ El video es demasiado grande (máx 100MB)"
    return True, ""

def upload_to_instagram(video_path, caption):
    try:
        media = ig.clip_upload(video_path, caption=caption)
        return True, media.code
    except Exception as e:
        return False, str(e)

@app.on_message(filters.video)
async def handle_video(client, message: Message):
    user_id = message.from_user.id
    
    # Verificar duración del video
    duration = message.video.duration
    file_size = message.video.file_size
    
    valid, error_msg = check_video_requirements(duration, file_size)
    if not valid:
        await message.reply(error_msg)
        return
    
    # Guardar estado del usuario
    user_states[user_id] = UserState()
    user_states[user_id].waiting_for_caption = True
    user_states[user_id].video_duration = duration
    
    # Crear teclado para cancelar
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_upload")]
    ])
    
    await message.reply(
        f"🎥 Video recibido ({duration}s)\n"
        "📝 **Envía el caption para Instagram:**\n"
        "(Máximo 2200 caracteres)",
        reply_markup=keyboard
    )

@app.on_message(filters.text & filters.private)
async def handle_caption(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in user_states and user_states[user_id].waiting_for_caption:
        caption = message.text
        
        if len(caption) > 2200:
            await message.reply("❌ El caption es demasiado largo (máx 2200 caracteres)")
            return
        
        # Descargar el video
        processing_msg = await message.reply("⏳ Descargando video...")
        
        try:
            video_path = await message.download(
                file_name=os.path.join(TEMP_DIR, f"{user_id}_{message.id}.mp4")
            )
            
            user_states[user_id].video_path = video_path
            user_states[user_id].waiting_for_caption = False
            
            await processing_msg.edit_text("📤 Subiendo a Instagram...")
            
            # Subir a Instagram
            success, result = upload_to_instagram(video_path, caption)
            
            if success:
                await processing_msg.edit_text(
                    f"✅ **¡Publicado exitosamente!**\n"
                    f"📱 **Instagram:** @{INSTAGRAM_USERNAME}\n"
                    f"🔗 Código: {result}"
                )
            else:
                await processing_msg.edit_text(f"❌ Error al publicar: {result}")
            
            # Limpiar
            if os.path.exists(video_path):
                os.remove(video_path)
            if user_id in user_states:
                del user_states[user_id]
                
        except Exception as e:
            await processing_msg.edit_text(f"❌ Error: {str(e)}")
            if user_id in user_states:
                del user_states[user_id]

@app.on_callback_query(filters.regex("cancel_upload"))
async def cancel_upload(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    await callback_query.message.edit_text("❌ Subida cancelada")

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply(
        "🤖 **Instagram Uploader Bot**\n\n"
        "**Cómo usar:**\n"
        "1. Envíame un video (≤60 segundos)\n"
        "2. Proporciona un caption\n"
        "3. ¡Se publicará automáticamente!\n\n"
        "**Requisitos:**\n"
        "• Video: MP4, ≤60s, ≤100MB\n"
        "• Caption: ≤2200 caracteres\n\n"
        "⚠️ **Advertencia:** Asegúrate de tener los derechos del contenido."
    )

@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    try:
        user_info = ig.user_info(ig.user_id)
        await message.reply(
            f"📊 **Estado de Instagram**\n"
            f"👤 Usuario: @{user_info.username}\n"
            f"📝 Publicaciones: {user_info.media_count}\n"
            f"👥 Seguidores: {user_info.follower_count}\n"
            f"✅ Conectado: Sí"
        )
    except:
        await message.reply("❌ No conectado a Instagram")

if __name__ == "__main__":
    if login_instagram():
        print("✅ Conectado a Instagram")
        print("🤖 Iniciando bot de Telegram...")
        app.run()
    else:
        print("❌ Error al conectar con Instagram")