import asyncio
import os
import tempfile
import time
from PyQt6.QtCore import QThread, pyqtSignal

from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus
from winsdk.windows.storage.streams import DataReader


class MediaWorker(QThread):
    media_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.manager = None
        self.last_thumb_path = ""
        self._last_emitted_key = None
        
    def run(self):
        asyncio.run(self.poll_loop())
        
    async def poll_loop(self):
        self.loop = asyncio.get_running_loop()
        try:
            self.manager = await MediaManager.request_async()
        except Exception:
            return
            
        while self.running:
            session = self.manager.get_current_session()
            if not session:
                if self._last_emitted_key != ("inactive",):
                    self._last_emitted_key = ("inactive",)
                    self.media_updated.emit({"active": False})
                await asyncio.sleep(2.5)
                continue
                
            try:
                playback = session.get_playback_info()
                is_playing = (playback.playback_status == PlaybackStatus.PLAYING)

                props = await session.try_get_media_properties_async()
                timeline = session.get_timeline_properties()
                
                title = props.title if (props and props.title) else "Unknown"
                artist = props.artist if (props and props.artist) else ""
                thumb_path = ""
                if props and props.thumbnail:
                    try:
                        thumb_path = await self.save_thumbnail(props.thumbnail)
                    except Exception:
                        pass
                
                raw_pos_sec = timeline.position.total_seconds() if timeline else 0
                end_sec = timeline.end_time.total_seconds() if timeline else 0
                
                pos_sec = raw_pos_sec
                if is_playing and timeline and hasattr(timeline, 'last_updated_time') and timeline.last_updated_time:
                    try:
                        import datetime
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        lut = timeline.last_updated_time
                        if lut.tzinfo is None:
                            diff = (now_utc.replace(tzinfo=None) - lut).total_seconds()
                        else:
                            diff = (now_utc - lut).total_seconds()
                        if 0 < diff < 14400: # within reasonable bounds
                            pos_sec = raw_pos_sec + diff
                    except Exception:
                        pass

                if end_sec > 0:
                    pos_sec = min(end_sec, max(0.0, pos_sec))
                
                pos_str = f"{int(pos_sec//60):02d}:{int(pos_sec%60):02d}"
                dur_str = f"{int(end_sec//60):02d}:{int(end_sec%60):02d}" if end_sec > 0 else "00:00"
                rem_sec = max(0, end_sec - pos_sec)
                rem_str = f"-{int(rem_sec//60):02d}:{int(rem_sec%60):02d}"
                progress = int(pos_sec / end_sec * 100) if end_sec > 0 else 0
                
                source_app = session.source_app_user_model_id if session.source_app_user_model_id else "Media Player"
                if "Spotify" in source_app:
                    source_app = "Spotify"
                elif "chrome" in source_app.lower():
                    source_app = "Google Chrome"
                elif "msedge" in source_app.lower():
                    source_app = "Microsoft Edge"
                
                # Only emit to Qt GUI thread when state or visible second changes
                cur_key = ("active", is_playing, title, artist, source_app, pos_str if is_playing else "")
                if cur_key != self._last_emitted_key:
                    self._last_emitted_key = cur_key
                    self.media_updated.emit({
                        "active": True,
                        "playing": is_playing,
                        "title": title,
                        "artist": artist,
                        "source_app": source_app,
                        "pos_str": pos_str,
                        "dur_str": dur_str,
                        "rem_str": rem_str,
                        "pos_sec": pos_sec,
                        "end_sec": end_sec,
                        "sync_time": time.time(),
                        "progress": progress,
                        "thumb": thumb_path
                    })
                await asyncio.sleep(1.5 if is_playing else 2.5)
            except Exception:
                await asyncio.sleep(2.5)

    async def save_thumbnail(self, thumbnail_ref):
        try:
            stream = await thumbnail_ref.open_read_async()
            reader = DataReader(stream)
            await reader.load_async(stream.size)
            buffer = reader.read_buffer(stream.size)
            data = bytes(memoryview(buffer))
            
            path = os.path.join(tempfile.gettempdir(), "emo_ai_notch_album_art.jpg")
            with open(path, "wb") as f:
                f.write(data)
            return path
        except Exception:
            return ""

    def _dispatch_coroutine(self, coro):
        loop = getattr(self, 'loop', None)
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            try:
                asyncio.run(coro)
            except Exception:
                pass

    def toggle_play_pause(self):
        self._dispatch_coroutine(self._toggle())
        
    async def _toggle(self):
        if not self.manager:
            return
        s = self.manager.get_current_session()
        if s:
            await s.try_toggle_play_pause_async()
        
    def next_track(self):
        self._dispatch_coroutine(self._next())
        
    async def _next(self):
        if not self.manager:
            return
        s = self.manager.get_current_session()
        if s:
            await s.try_skip_next_async()
        
    def prev_track(self):
        self._dispatch_coroutine(self._prev())
        
    async def _prev(self):
        if not self.manager:
            return
        s = self.manager.get_current_session()
        if s:
            await s.try_skip_previous_async()

    def seek_to_position(self, target_sec: float):
        self._dispatch_coroutine(self._seek(target_sec))

    async def _seek(self, target_sec: float):
        if not self.manager:
            return
        s = self.manager.get_current_session()
        if s:
            try:
                import datetime
                await s.try_change_playback_position_async(datetime.timedelta(seconds=float(target_sec)))
            except Exception:
                try:
                    # Fallback to 100-nanosecond intervals (1 second = 10,000,000 units)
                    await s.try_change_playback_position_async(int(target_sec * 10_000_000))
                except Exception:
                    pass
            self._last_emitted_key = None

    def stop_worker(self):
        self.running = False
