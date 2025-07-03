import sys
import json
import os
import base64
import hashlib
import hmac
import struct
import logging
import pyotp
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget, 
                             QCheckBox, QListWidgetItem, QProgressBar, QTextEdit,
                             QMessageBox, QComboBox, QStackedWidget, QGroupBox, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QSplitter, QTabWidget, QSpinBox, QDateTimeEdit, QSlider,
                             QFormLayout, QGridLayout, QScrollArea, QFrame, QInputDialog, QMenu)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QDateTime, QSettings
from PyQt5.QtGui import QIcon, QPixmap, QFont, QColor, QPalette
#from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtSvg import QSvgWidget, QSvgRenderer
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from urllib.parse import quote
import deezer
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
import threading
from email.utils import parsedate_to_datetime
import secrets

CONFIG_FILE = "app_config.json"
SYNC_CONFIG_FILE = "sync_config.json"
CACHE_FILE = "playlist_cache.json"

# PLAYLIST CACHE CLASS - DEFINED FIRST!
class PlaylistCache:
    def __init__(self):
        self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
        self.load_cache()
    
    def load_cache(self):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    self.cache_data = json.load(f)
                logging.info("Playlist cache loaded successfully")
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
    
    def save_cache(self):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
            logging.info("Playlist cache saved successfully")
        except Exception as e:
            logging.error(f"Error saving cache: {str(e)}")
    
    def get_playlist_data(self, playlist_id):
        return self.cache_data["playlists"].get(playlist_id, None)
    
    def set_playlist_data(self, playlist_id, track_count, tracks_data=None):
        self.cache_data["playlists"][playlist_id] = {
            "track_count": track_count,
            "tracks_data": tracks_data,
            "cached_at": datetime.now().isoformat()
        }
        self.cache_data["last_updated"][playlist_id] = datetime.now().isoformat()
        self.save_cache()
    
    def is_cached(self, playlist_id):
        return playlist_id in self.cache_data["playlists"]
    
    def get_track_count(self, playlist_id):
        data = self.get_playlist_data(playlist_id)
        return data.get("track_count", None) if data else None
    
    def clear_cache(self):
        self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
        self.save_cache()
    
    def remove_playlist(self, playlist_id):
        if playlist_id in self.cache_data["playlists"]:
            del self.cache_data["playlists"][playlist_id]
        if playlist_id in self.cache_data["last_updated"]:
            del self.cache_data["last_updated"][playlist_id]
        self.save_cache()

def resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores the path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not running in a PyInstaller bundle, use the directory of the script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def initialize_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "plex_username": "",
            "server_ip": "127.0.0.1",
            "server_port": "32400",
            "token": "",
            "last_section": None,
            "auto_backup": True,
            "backup_interval": 24
        }
        try:
            with open(CONFIG_FILE, 'w') as config_file:
                json.dump(default_config, config_file, indent=4)
            logging.info(f"Created {CONFIG_FILE} with default values.")
        except Exception as e:
            logging.error(f"Failed to create {CONFIG_FILE}: {str(e)}")
    else:
        logging.info(f"{CONFIG_FILE} already exists.")
        
    if not os.path.exists(SYNC_CONFIG_FILE):
        default_sync_config = {
            "sync_playlists": {},
            "auto_sync": False,
            "sync_interval": 60
        }
        try:
            with open(SYNC_CONFIG_FILE, 'w') as sync_file:
                json.dump(default_sync_config, sync_file, indent=4)
            logging.info(f"Created {SYNC_CONFIG_FILE} with default values.")
        except Exception as e:
            logging.error(f"Failed to create {SYNC_CONFIG_FILE}: {str(e)}")

    # Initialize cache file
    if not os.path.exists(CACHE_FILE):
        default_cache = {
            "playlists": {},
            "last_updated": {},
            "version": "1.0"
        }
        try:
            with open(CACHE_FILE, 'w') as cache_file:
                json.dump(default_cache, cache_file, indent=4)
            logging.info(f"Created {CACHE_FILE} with default values.")
        except Exception as e:
            logging.error(f"Failed to create {CACHE_FILE}: {str(e)}")

def setup_logging():
    # Use a directory where we're sure to have write permissions
    log_dir = tempfile.gettempdir()
    LOG_FILE = os.path.join(log_dir, "plex_playlist_manager.log")

    try:
        # Attempt to remove the existing log file
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except PermissionError:
        # If we can't remove it, we'll append to it instead
        print(f"Unable to remove existing log file. Will append to {LOG_FILE}")
    except Exception as e:
        print(f"Unexpected error when trying to remove log file: {e}")

    try:
        # Configure logging
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Optionally, add a stream handler for console output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(console_handler)

        logging.info(f"Logging started. Log file: {LOG_FILE}")
    except Exception as e:
        print(f"Failed to set up logging: {e}")
        # If we can't set up file logging, we'll log to console only
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.warning("Logging to console only due to file access issues")

class FetchPlaylistsThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    playlists_fetched = pyqtSignal(list)  # playlists list
    error = pyqtSignal(str)

    def __init__(self, plex_server, playlist_cache, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.playlist_cache = playlist_cache
        self.parent_window = parent

    def should_exclude_playlist(self, playlist):
        """Check if playlist should be excluded from operations (large system playlists)"""
        try:
            # Get cached track count if available
            playlist_id = str(playlist.ratingKey)
            cached_count = self.playlist_cache.get_track_count(playlist_id)
            
            # Exclude by name patterns (case insensitive)
            exclude_names = [
                'all music', 'allmusic', 'all songs', 'library', 'entire library',
                'complete library', 'full library', 'music library',
                'recently added', 'recently played'  # Added these
            ]
            
            playlist_title_lower = playlist.title.lower()
            for exclude_name in exclude_names:
                if exclude_name in playlist_title_lower:
                    logging.info(f"Excluding playlist '{playlist.title}' during fetch - matches exclude pattern '{exclude_name}'")
                    return True
            
            # Exclude by size if cached (over 10,000 tracks is likely a system playlist)
            if cached_count and cached_count > 10000:
                logging.info(f"Excluding playlist '{playlist.title}' during fetch - too large ({cached_count} tracks)")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking playlist exclusion during fetch: {str(e)}")
            return False

    def run(self):
        try:
            self.progress_update.emit("Connecting to Plex server...", 10)
            
            # Fetch playlists (just basic info, no track counts)
            self.progress_update.emit("Fetching playlist list...", 30)
            all_playlists = self.plex_server.playlists()
            
            self.progress_update.emit("Filtering playlists...", 50)
            
            # Filter out massive/system playlists
            filtered_playlists = []
            excluded_count = 0
            
            for playlist in all_playlists:
                if self.should_exclude_playlist(playlist):
                    excluded_count += 1
                    continue
                filtered_playlists.append(playlist)
            
            # Prepare playlist data with cached track counts for filtered playlists only
            playlist_data = []
            
            self.progress_update.emit("Preparing playlist data...", 70)
            
            for playlist in filtered_playlists:
                # Check if we have cached track count - convert ratingKey to string
                playlist_id = str(playlist.ratingKey)
                cached_count = self.playlist_cache.get_track_count(playlist_id)
                playlist_data.append((playlist, cached_count))
            
            self.progress_update.emit("Finalizing...", 95)
            
            if excluded_count > 0:
                logging.info(f"Excluded {excluded_count} large/system playlists during fetch")
            
            self.playlists_fetched.emit(playlist_data)
            
        except Exception as e:
            logging.error(f"Error fetching playlists: {str(e)}")
            self.error.emit(str(e))

class LoadTrackCountThread(QThread):
    track_count_loaded = pyqtSignal(str, int)  # playlist_id, track_count
    error = pyqtSignal(str, str)  # playlist_id, error_message
    progress_update = pyqtSignal(str, int)  # message, percentage

    def __init__(self, playlist, playlist_cache, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.playlist_cache = playlist_cache

    def run(self):
        try:
            playlist_id = str(self.playlist.ratingKey)
            
            # Emit progress updates
            self.progress_update.emit(f"Loading tracks for '{self.playlist.title}'...", 25)
            
            # Get track count for this specific playlist
            self.progress_update.emit("Counting tracks...", 50)
            tracks = list(self.playlist.items())
            track_count = len(tracks)
            
            self.progress_update.emit("Caching results...", 75)
            # Cache the result - convert ratingKey to string
            self.playlist_cache.set_playlist_data(playlist_id, track_count)
            
            self.progress_update.emit("Complete!", 100)
            # Emit the result - make sure playlist_id is string
            self.track_count_loaded.emit(playlist_id, track_count)
            
        except Exception as e:
            logging.error(f"Error loading track count for {self.playlist.title}: {str(e)}")
            # Convert ratingKey to string for error signal too
            playlist_id = str(self.playlist.ratingKey)
            self.error.emit(playlist_id, str(e))

class LoadPlaylistTracksThread(QThread):
    progress_update = pyqtSignal(int, int)  # current, total
    tracks_loaded = pyqtSignal(list)  # tracks list
    error = pyqtSignal(str)

    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist

    def run(self):
        try:
            # Emit initial progress
            self.progress_update.emit(0, 0)
            
            # Load tracks with progress tracking
            tracks = list(self.playlist.items())
            total_tracks = len(tracks)
            
            # Emit progress updates
            for i, track in enumerate(tracks):
                if i % 10 == 0:  # Update every 10 tracks
                    self.progress_update.emit(i, total_tracks)
                # Small delay to make progress visible and keep UI responsive
                if i % 50 == 0:
                    self.msleep(10)
            
            # Final progress update
            self.progress_update.emit(total_tracks, total_tracks)
            
            # Emit the complete tracks list
            self.tracks_loaded.emit(tracks)
            
        except Exception as e:
            logging.error(f"Error loading tracks: {str(e)}")
            self.error.emit(str(e))

# NEW: Background thread for backup
class BackupThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    backup_complete = pyqtSignal(int, str)  # backed_up_count, backup_folder
    error = pyqtSignal(str)

    def __init__(self, plex_server, backup_dir, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.backup_dir = backup_dir

    def run(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(self.backup_dir, f"plex_playlists_backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)
            
            playlists = self.plex_server.playlists()
            backed_up = 0
            total_playlists = len(playlists)
            
            for i, playlist in enumerate(playlists):
                try:
                    # Update progress
                    self.progress_update.emit(f"Backing up: {playlist.title}...", 
                                            int((i / total_playlists) * 100))
                    
                    # Sanitize the playlist name for filename
                    safe_name = playlist.title
                    # Basic sanitization for backup thread
                    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                    for char in invalid_chars:
                        safe_name = safe_name.replace(char, '_')
                    safe_name = safe_name.strip().rstrip('.')
                    if not safe_name:
                        safe_name = "Unnamed_Playlist"
                    filename = f"{safe_name}.m3u"
                    filepath = os.path.join(backup_folder, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as file:
                        file.write("#EXTM3U\n")
                        file.write(f"# Playlist: {playlist.title}\n")
                        file.write(f"# Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        for item in playlist.items():
                            try:
                                artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                                file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                                file.write(f"{item.title} - {artist}\n")
                            except Exception as track_error:
                                logging.warning(f"Error backing up track: {str(track_error)}")
                                continue
                    
                    backed_up += 1
                    
                except Exception as playlist_error:
                    logging.error(f"Error backing up playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            self.backup_complete.emit(backed_up, backup_folder)
            
        except Exception as e:
            logging.error(f"Error during backup: {str(e)}")
            self.error.emit(str(e))

class BatchTrackCountThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    all_complete = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, playlists, playlist_cache, max_concurrent=3, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.playlist_cache = playlist_cache
        self.max_concurrent = max_concurrent
        self.stop_requested = False

    def run(self):
        try:
            total_playlists = len(self.playlists)
            completed = 0
            
            # Process playlists in batches to avoid overwhelming the system
            for i in range(0, total_playlists, self.max_concurrent):
                if self.stop_requested:
                    break
                    
                batch = self.playlists[i:i + self.max_concurrent]
                threads = []
                
                # Start threads for this batch
                for playlist, _ in batch:
                    playlist_id = str(playlist.ratingKey)
                    if not self.playlist_cache.is_cached(playlist_id):
                        thread = LoadTrackCountThread(playlist, self.playlist_cache, self)
                        threads.append(thread)
                        thread.start()
                
                # Wait for all threads in this batch to complete
                for thread in threads:
                    thread.wait()
                    completed += 1
                    
                    progress = int((completed / total_playlists) * 100)
                    self.progress_update.emit(f"Loading track counts... ({completed}/{total_playlists})", progress)
            
            self.all_complete.emit()
            
        except Exception as e:
            logging.error(f"Error in batch track count loading: {str(e)}")
            self.error.emit(str(e))

    def stop(self):
        self.stop_requested = True

class ExportThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    export_complete = pyqtSignal(int)  # number of exported playlists
    error = pyqtSignal(str)

    def __init__(self, playlists_to_export, export_dir, parent=None):
        super().__init__(parent)
        self.playlists_to_export = playlists_to_export
        self.export_dir = export_dir

    def run(self):
        try:
            exported_count = 0
            total_playlists = len(self.playlists_to_export)
            
            for i, playlist in enumerate(self.playlists_to_export):
                try:
                    # Update progress
                    self.progress_update.emit(f"Exporting playlist: {playlist.title}...", 
                                            int((i / total_playlists) * 100))
                    
                    # Export the playlist
                    safe_name = self.parent_window.sanitize_filename(playlist.title) if hasattr(self, 'parent_window') else playlist.title.replace('/', '_').replace('\\', '_')
                    filename = f"{safe_name}.m3u"
                    filepath = os.path.join(self.export_dir, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as file:
                        file.write("#EXTM3U\n")
                        file.write(f"# Exported from Plex on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        for item in playlist.items():
                            try:
                                # Use the actual file path from Plex, not just track info
                                for part in item.iterParts():
                                    if hasattr(part, 'file') and part.file:
                                        # Write the full file path as it was before
                                        file.write(f"{part.file}\n")
                                        break
                                else:
                                    # Fallback: if no file path available, use track info
                                    artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                                    file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                                    file.write(f"{item.title} - {artist}\n")
                            except Exception as e:
                                logging.warning(f"Error exporting track: {str(e)}")
                                continue
                    
                    exported_count += 1
                    
                except Exception as playlist_error:
                    logging.error(f"Error exporting playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            self.export_complete.emit(exported_count)
            
        except Exception as e:
            logging.error(f"Error during export: {str(e)}")
            self.error.emit(str(e))

class FindDuplicatesThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    duplicates_found = pyqtSignal(list)  # duplicate tracks list
    error = pyqtSignal(str)

    def __init__(self, plex_server, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server

    def should_exclude_playlist(self, playlist):
        """Check if playlist should be excluded from duplicate scan"""
        try:
            # Exclude by name patterns (case insensitive)
            exclude_names = [
                'all music', 'allmusic', 'all songs', 'library', 'entire library',
                'complete library', 'full library', 'music library',
                'recently added', 'recently played'
            ]
            
            playlist_title_lower = playlist.title.lower()
            for exclude_name in exclude_names:
                if exclude_name in playlist_title_lower:
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking playlist exclusion: {str(e)}")
            return False

    def run(self):
        try:
            self.progress_update.emit("Fetching playlists...", 10)
            
            all_playlists = self.plex_server.playlists()
            
            # Filter out excluded playlists
            filtered_playlists = []
            for playlist in all_playlists:
                if not self.should_exclude_playlist(playlist):
                    filtered_playlists.append(playlist)
            
            self.progress_update.emit(f"Scanning {len(filtered_playlists)} playlists for duplicates...", 20)
            
            track_occurrences = {}
            total_playlists = len(filtered_playlists)
            
            for i, playlist in enumerate(filtered_playlists):
                try:
                    # Skip non-music playlists
                    if hasattr(playlist, 'playlistType') and playlist.playlistType != 'audio':
                        continue
                    
                    self.progress_update.emit(f"Scanning playlist: {playlist.title}...", 
                                            20 + int((i / total_playlists) * 60))
                    
                    for track in playlist.items():
                        try:
                            # Only process audio tracks
                            if not hasattr(track, 'originalTitle') and not hasattr(track, 'artist'):
                                continue
                            
                            # Safely get artist name
                            artist_name = "Unknown"
                            if hasattr(track, 'originalTitle') and track.originalTitle:
                                artist_name = track.originalTitle
                            elif hasattr(track, 'artist') and track.artist():
                                artist_name = track.artist().title
                            
                            signature = f"{track.title}_{artist_name}"
                            
                            if signature not in track_occurrences:
                                track_occurrences[signature] = []
                            track_occurrences[signature].append((playlist.title, track))
                            
                        except Exception as track_error:
                            logging.warning(f"Error processing track in playlist {playlist.title}: {str(track_error)}")
                            continue
                            
                except Exception as playlist_error:
                    logging.warning(f"Error processing playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            self.progress_update.emit("Analyzing results...", 85)
            
            # Find duplicates
            duplicate_tracks = []
            for signature, occurrences in track_occurrences.items():
                if len(occurrences) > 1:
                    duplicate_tracks.append((signature, occurrences))
            
            self.progress_update.emit("Complete!", 100)
            self.duplicates_found.emit(duplicate_tracks)
            
        except Exception as e:
            logging.error(f"Error in duplicate finding thread: {str(e)}")
            self.error.emit(str(e))

class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading...")
        self.setModal(True)
        self.setFixedSize(350, 120)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        layout = QVBoxLayout(self)
        
        self.message_label = QLabel("Please wait...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.detail_label)
    
    def update_progress(self, message, percentage):
        self.message_label.setText(message)
        self.progress_bar.setValue(percentage)
        if percentage < 100:
            self.detail_label.setText(f"{percentage}% complete")
        else:
            self.detail_label.setText("Almost done...")

class PlaylistEditorDialog(QDialog):
    def __init__(self, playlist, plex_server, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.plex_server = plex_server
        self.tracks_loaded = False
        self.tracks = []
        self.load_tracks_thread = None
        self.setWindowTitle(f"Edit Playlist: {playlist.title}")
        self.setModal(True)
        self.resize(800, 600)
        
        # Setup UI immediately (non-blocking)
        self.setup_ui()
        
        # Start loading tracks immediately but asynchronously
        self.start_background_loading()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Playlist info header
        info_layout = QHBoxLayout()
        title_label = QLabel(f"📝 Editing: {self.playlist.title}")
        title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #4CAF50;")
        info_layout.addWidget(title_label)
        
        self.track_count_label = QLabel("⏳ Loading tracks...")
        self.track_count_label.setStyleSheet("color: #888888;")
        info_layout.addWidget(self.track_count_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        
        # Loading section (visible initially)
        self.loading_section = QWidget()
        loading_layout = QVBoxLayout(self.loading_section)
        
        self.loading_label = QLabel("🔄 Loading playlist tracks...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 14px; color: #888888; padding: 20px;")
        loading_layout.addWidget(self.loading_label)
        
        # Enhanced progress bar
        self.loading_progress = QProgressBar()
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 6px;
            }
        """)
        loading_layout.addWidget(self.loading_progress)
        
        # Loading details
        self.loading_detail = QLabel("Initializing...")
        self.loading_detail.setAlignment(Qt.AlignCenter)
        self.loading_detail.setStyleSheet("color: #666666; font-size: 12px; padding: 10px;")
        loading_layout.addWidget(self.loading_detail)
        
        layout.addWidget(self.loading_section)
        
        # Editor section (hidden initially)
        self.editor_section = QWidget()
        self.editor_section.setVisible(False)
        editor_layout = QVBoxLayout(self.editor_section)

        # Search/Filter section
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Search:")
        search_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search tracks by title, artist, or album...")
        self.search_input.textChanged.connect(self.filter_tracks)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                padding: 8px;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        search_layout.addWidget(self.search_input)
        
        clear_search_btn = QPushButton("✖")
        clear_search_btn.setFixedSize(30, 30)
        clear_search_btn.clicked.connect(lambda: self.search_input.clear())
        clear_search_btn.setToolTip("Clear search")
        search_layout.addWidget(clear_search_btn)
        
        editor_layout.addLayout(search_layout)
        
        # Tracks table
        self.tracks_table = QTableWidget()
        self.tracks_table.setColumnCount(4)  # 4 columns total
        self.tracks_table.setHorizontalHeaderLabels(["Title", "Artist", "Album", "Duration"])
        self.tracks_table.horizontalHeader().setStretchLastSection(True)
        self.tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tracks_table.setDragDropMode(QAbstractItemView.InternalMove)

        # Enable right-click context menu
        self.tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tracks_table.customContextMenuRequested.connect(self.show_context_menu)
        
        # FIXED: Remove alternating row colors that cause visibility issues
        self.tracks_table.setAlternatingRowColors(False)
        
        # FIXED: Set proper styling for dark theme compatibility
        self.tracks_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a;
                color: #ffffff;
                gridline-color: #3a3a3a;
                selection-background-color: #4a4a4a;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3a3a3a;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #2a2a2a;
                font-weight: bold;
            }
        """)
        
        # Set column widths - FIXED: 5 columns
        self.tracks_table.setColumnWidth(0, 250)  # Title
        self.tracks_table.setColumnWidth(1, 200)  # Artist
        self.tracks_table.setColumnWidth(2, 200)  # Album
        # Duration column (3) will stretch
        
        editor_layout.addWidget(self.tracks_table)
        
        layout.addWidget(self.editor_section)
        
        # Button section (visible immediately but disabled)
        button_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("🗑️ Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)
        
        self.move_up_button = QPushButton("⬆️ Move Up")
        self.move_up_button.clicked.connect(self.move_up)
        self.move_up_button.setEnabled(False)
        button_layout.addWidget(self.move_up_button)
        
        self.move_down_button = QPushButton("⬇️ Move Down")
        self.move_down_button.clicked.connect(self.move_down)
        self.move_down_button.setEnabled(False)
        button_layout.addWidget(self.move_down_button)
        
        button_layout.addStretch()
        
        self.save_button = QPushButton("💾 Save Changes")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.save_button)
        
        self.cancel_button = QPushButton("X Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def start_background_loading(self):
        """Start loading tracks in background thread immediately"""
        self.loading_progress.setValue(10)
        self.loading_detail.setText("Connecting to Plex server...")
        
        # Start background thread immediately
        self.load_tracks_thread = LoadPlaylistTracksThread(self.playlist, self)
        self.load_tracks_thread.progress_update.connect(self.update_loading_progress)
        self.load_tracks_thread.tracks_loaded.connect(self.on_tracks_loaded)
        self.load_tracks_thread.error.connect(self.on_tracks_error)
        self.load_tracks_thread.start()
    
    def update_loading_progress(self, current, total):
        """Update loading progress with smooth animations"""
        if total > 0:
            percentage = int((current / total) * 90) + 10  # 10-100 range
            self.loading_progress.setValue(percentage)
            self.loading_detail.setText(f"Loading track {current} of {total}...")
        else:
            # Indeterminate progress
            self.loading_progress.setValue(50)
            self.loading_detail.setText("Loading playlist data...")
        
        # Keep UI responsive
        QApplication.processEvents()
    
    def on_tracks_loaded(self, tracks):
        """Handle tracks loaded from background thread with smooth transition"""
        try:
            self.loading_progress.setValue(90)
            self.loading_detail.setText("Processing tracks...")
            QApplication.processEvents()
            
            self.tracks = tracks
            self.populate_tracks_table(tracks)
            
            # Smooth transition to editor
            self.loading_progress.setValue(100)
            self.loading_detail.setText("Ready!")
            QApplication.processEvents()
            
            # Small delay for visual feedback, then switch views
            QTimer.singleShot(300, self.show_editor)
                
        except Exception as e:
            logging.error(f"Error processing loaded tracks: {str(e)}")
            self.on_tracks_error(str(e))
    
    def populate_tracks_table(self, tracks):
        """Populate tracks table efficiently with row numbers"""
        self.tracks_table.setRowCount(len(tracks))
        self.track_count_label.setText(f"🎵 Tracks: {len(tracks)}")
        
        # Batch processing for better performance
        batch_size = 50
        for i in range(0, len(tracks), batch_size):
            batch = tracks[i:i + batch_size]
            for j, track in enumerate(batch):
                row = i + j
                
                # Create items for each column
                title_item = QTableWidgetItem(track.title or "Unknown")
                artist = track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else "Unknown")
                artist_item = QTableWidgetItem(artist)
                album = track.album().title if hasattr(track, 'album') and track.album() else "Unknown"
                album_item = QTableWidgetItem(album)
                duration = f"{track.duration // 60000}:{(track.duration % 60000) // 1000:02d}" if track.duration else "Unknown"
                duration_item = QTableWidgetItem(duration)
                
                # Make all items read-only
                title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
                artist_item.setFlags(artist_item.flags() & ~Qt.ItemIsEditable)
                album_item.setFlags(album_item.flags() & ~Qt.ItemIsEditable)
                duration_item.setFlags(duration_item.flags() & ~Qt.ItemIsEditable)
                
                # Set items in table
                self.tracks_table.setItem(row, 0, title_item)
                self.tracks_table.setItem(row, 1, artist_item)
                self.tracks_table.setItem(row, 2, album_item)
                self.tracks_table.setItem(row, 3, duration_item)
                
                # Store track object for later use (in the title column)
                self.tracks_table.item(row, 0).setData(Qt.UserRole, track)
            
            # Update progress during batch processing
            progress = int(((i + len(batch)) / len(tracks)) * 10) + 90  # 90-100 range
            self.loading_progress.setValue(progress)
            QApplication.processEvents()  # Keep UI responsive during processing
    
    def show_editor(self):
        """Show the editor interface with smooth transition"""
        # Hide loading section
        self.loading_section.setVisible(False)
        
        # Show editor section
        self.editor_section.setVisible(True)
        
        # Enable all buttons
        self.delete_button.setEnabled(True)
        self.move_up_button.setEnabled(True)
        self.move_down_button.setEnabled(True)
        self.save_button.setEnabled(True)
        
        self.tracks_loaded = True
        
        # Update window title
        self.setWindowTitle(f"✏️ Editing: {self.playlist.title} ({len(self.tracks)} tracks)")
    
    def filter_tracks(self, search_text):
        """Filter tracks based on search text"""
        search_text = search_text.lower().strip()
        
        for row in range(self.tracks_table.rowCount()):
            # Get track data from the row
            title_item = self.tracks_table.item(row, 0)  # Title
            artist_item = self.tracks_table.item(row, 1)  # Artist  
            album_item = self.tracks_table.item(row, 2)   # Album
            
            # Check if search text matches any field
            show_row = False
            if not search_text:  # Empty search shows all
                show_row = True
            else:
                # Search in title, artist, and album
                if title_item and search_text in title_item.text().lower():
                    show_row = True
                elif artist_item and search_text in artist_item.text().lower():
                    show_row = True
                elif album_item and search_text in album_item.text().lower():
                    show_row = True
            
            # Show or hide the row
            self.tracks_table.setRowHidden(row, not show_row)
    
    def show_context_menu(self, position):
        """Show right-click context menu"""
        if not self.tracks_loaded:
            return
        
        # Get the row that was right-clicked
        item = self.tracks_table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
        """)
        
        # Add actions
        set_position_action = menu.addAction("📍 Set Position...")
        move_to_top_action = menu.addAction("⬆️ Move to Top")
        move_to_bottom_action = menu.addAction("⬇️ Move to Bottom")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Delete Track")
        
        # Show menu and handle selection
        action = menu.exec_(self.tracks_table.mapToGlobal(position))
        
        if action == set_position_action:
            self.set_track_position(row)
        elif action == move_to_top_action:
            self.move_track_to_position(row, 0)
        elif action == move_to_bottom_action:
            self.move_track_to_position(row, self.tracks_table.rowCount() - 1)
        elif action == delete_action:
            self.delete_track_at_row(row)
    
    def set_track_position(self, current_row):
        """Allow user to set specific position for a track"""
        track_title = self.tracks_table.item(current_row, 0).text()
        current_position = current_row + 1
        total_tracks = self.tracks_table.rowCount()
        
        # Show input dialog
        new_position, ok = QInputDialog.getInt(
            self, 
            "Set Track Position",
            f"Move '{track_title}' to position:\n(Current: {current_position}, Total: {total_tracks})",
            current_position,  # default value
            1,                 # minimum
            total_tracks       # maximum
        )
        
        if ok and new_position != current_position:
            target_row = new_position - 1  # Convert to 0-based index
            self.move_track_to_position(current_row, target_row)
    
    def move_track_to_position(self, from_row, to_row):
        """Move track from one position to another - robust approach"""
        try:
            target_position = to_row + 1  # Store 1-based position for user
            
            # Get all tracks data first
            all_tracks_data = []
            for row in range(self.tracks_table.rowCount()):
                track_data = {
                    'title': self.tracks_table.item(row, 0).text(),
                    'artist': self.tracks_table.item(row, 1).text(),
                    'album': self.tracks_table.item(row, 2).text(),
                    'duration': self.tracks_table.item(row, 3).text(),
                    'track_object': self.tracks_table.item(row, 0).data(Qt.UserRole)
                }
                all_tracks_data.append(track_data)
            
            # Move the track in our data list
            track_to_move = all_tracks_data.pop(from_row)  # Remove from current position
            all_tracks_data.insert(to_row, track_to_move)  # Insert at target position
            
            # Repopulate the entire table with correct order
            for row, track_data in enumerate(all_tracks_data):
                # Create and set title item
                title_item = QTableWidgetItem(track_data['title'])
                title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
                title_item.setData(Qt.UserRole, track_data['track_object'])
                self.tracks_table.setItem(row, 0, title_item)
                
                # Create and set artist item
                artist_item = QTableWidgetItem(track_data['artist'])
                artist_item.setFlags(artist_item.flags() & ~Qt.ItemIsEditable)
                self.tracks_table.setItem(row, 1, artist_item)
                
                # Create and set album item
                album_item = QTableWidgetItem(track_data['album'])
                album_item.setFlags(album_item.flags() & ~Qt.ItemIsEditable)
                self.tracks_table.setItem(row, 2, album_item)
                
                # Create and set duration item
                duration_item = QTableWidgetItem(track_data['duration'])
                duration_item.setFlags(duration_item.flags() & ~Qt.ItemIsEditable)
                self.tracks_table.setItem(row, 3, duration_item)
            
            # Select the moved track at its new position
            self.tracks_table.selectRow(to_row)
            
            # Show success message
            QMessageBox.information(self, "Success", f"Track moved to position {target_position}")
            
        except Exception as e:
            logging.error(f"Error moving track: {str(e)}")
            QMessageBox.warning(self, "Move Error", f"Failed to move track: {str(e)}")
    
    def delete_track_at_row(self, row):
        """Delete a specific track"""
        track_title = self.tracks_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                   f"Delete '{track_title}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.tracks_table.removeRow(row)
            self.track_count_label.setText(f"🎵 Tracks: {self.tracks_table.rowCount()}")
            # Show success message instead of statusBar
            QMessageBox.information(self, "Deleted", f"Deleted '{track_title}'")

    def on_tracks_error(self, error_message):
        """Handle error loading tracks with user-friendly display"""
        self.loading_progress.setValue(0)
        self.loading_progress.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #f44336;
            }
        """)
        self.loading_label.setText("❌ Error Loading Tracks")
        self.loading_detail.setText(f"Error: {error_message}")
        
        # Show retry option
        retry_button = QPushButton("🔄 Retry Loading")
        retry_button.clicked.connect(self.retry_loading)
        self.loading_section.layout().addWidget(retry_button)
        
        QMessageBox.warning(self, "Loading Error", f"Failed to load tracks: {error_message}")
    
    def retry_loading(self):
        """Retry loading tracks"""
        # Reset UI
        for i in range(self.loading_section.layout().count()):
            child = self.loading_section.layout().itemAt(i).widget()
            if isinstance(child, QPushButton):
                child.deleteLater()
        
        self.loading_label.setText("🔄 Retrying...")
        self.loading_detail.setText("Attempting to reload tracks...")
        self.loading_progress.setValue(0)
        self.loading_progress.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        
        # Restart loading
        self.start_background_loading()
            
    def delete_selected(self):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return
            
        selected_rows = set()
        for item in self.tracks_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select tracks to delete.")
            return
            
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                   f"Delete {len(selected_rows)} selected track(s)?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            for row in sorted(selected_rows, reverse=True):
                self.tracks_table.removeRow(row)
                       
            # Update track count
            self.track_count_label.setText(f"🎵 Tracks: {self.tracks_table.rowCount()}")
                
    def move_up(self):
        current_row = self.tracks_table.currentRow()
        if current_row > 0:
            self.swap_rows(current_row, current_row - 1)
            self.tracks_table.setCurrentCell(current_row - 1, 0)
            
    def move_down(self):
        current_row = self.tracks_table.currentRow()
        if current_row < self.tracks_table.rowCount() - 1:
            self.swap_rows(current_row, current_row + 1)
            self.tracks_table.setCurrentCell(current_row + 1, 0)  # Select title column
            
    def swap_rows(self, row1, row2):
        # Handle all 4 columns
        for col in range(self.tracks_table.columnCount()):
            item1 = self.tracks_table.takeItem(row1, col)
            item2 = self.tracks_table.takeItem(row2, col)
            self.tracks_table.setItem(row1, col, item2)
            self.tracks_table.setItem(row2, col, item1)
            
    def save_changes(self):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return
            
        try:
            # Show saving progress
            self.save_button.setText("💾 Saving...")
            self.save_button.setEnabled(False)
            QApplication.processEvents()
            
            # Get current track order - Look at column 0 (title)
            tracks = []
            for row in range(self.tracks_table.rowCount()):
                item = self.tracks_table.item(row, 0)  # Title column now
                if item and item.data(Qt.UserRole):
                    tracks.append(item.data(Qt.UserRole))
                    
            if tracks:
                # Update playlist with new track order
                self.playlist.removeItems(self.playlist.items())
                self.playlist.addItems(tracks)
                
            QMessageBox.information(self, "Success", "🎉 Playlist updated successfully!")
            self.accept()
            
        except Exception as e:
            logging.error(f"Error saving playlist changes: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {str(e)}")
        finally:
            self.save_button.setText("💾 Save Changes")
            self.save_button.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if self.load_tracks_thread and self.load_tracks_thread.isRunning():
            self.load_tracks_thread.terminate()
            self.load_tracks_thread.wait(1000)
        event.accept()

class PlaylistMergerDialog(QDialog):
    def __init__(self, playlists, plex_server, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.plex_server = plex_server
        self.setWindowTitle("Merge Playlists")
        self.setModal(True)
        self.resize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Select playlists to merge and specify the target:"))
        
        # Playlist selection
        self.playlist_list = QListWidget()
        for playlist in self.playlists:
            item = QListWidgetItem(f"{playlist.title} ({len(list(playlist.items()))} tracks)")
            item.setData(Qt.UserRole, playlist)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.playlist_list.addItem(item)
        layout.addWidget(self.playlist_list)
        
        # Merge options
        options_group = QGroupBox("Merge Options")
        options_layout = QVBoxLayout(options_group)
        
        # Target playlist option
        self.target_new = QCheckBox("Create new playlist")
        self.target_new.setChecked(True)
        self.target_new.toggled.connect(self.on_target_changed)
        options_layout.addWidget(self.target_new)
        
        self.target_existing = QCheckBox("Merge into existing playlist")
        self.target_existing.toggled.connect(self.on_target_changed)
        options_layout.addWidget(self.target_existing)
        
        # New playlist name
        self.new_name_layout = QHBoxLayout()
        self.new_name_layout.addWidget(QLabel("New playlist name:"))
        self.new_name_input = QLineEdit("Merged Playlist")
        self.new_name_layout.addWidget(self.new_name_input)
        options_layout.addLayout(self.new_name_layout)
        
        # Existing playlist combo
        self.existing_combo_layout = QHBoxLayout()
        self.existing_combo_layout.addWidget(QLabel("Target playlist:"))
        self.existing_combo = QComboBox()
        self.existing_combo.setEnabled(False)
        self.populate_existing_playlists()
        self.existing_combo_layout.addWidget(self.existing_combo)
        options_layout.addLayout(self.existing_combo_layout)
        
        # Additional options
        self.remove_duplicates = QCheckBox("Remove duplicate tracks")
        self.remove_duplicates.setChecked(True)
        options_layout.addWidget(self.remove_duplicates)
        
        self.delete_source = QCheckBox("Delete source playlists after merge")
        options_layout.addWidget(self.delete_source)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.merge_button = QPushButton("Merge Playlists")
        self.merge_button.clicked.connect(self.merge_playlists)
        button_layout.addWidget(self.merge_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def on_target_changed(self):
        if self.target_new.isChecked():
            self.target_existing.setChecked(False)
            self.new_name_input.setEnabled(True)
            self.existing_combo.setEnabled(False)
        elif self.target_existing.isChecked():
            self.target_new.setChecked(False)
            self.new_name_input.setEnabled(False)
            self.existing_combo.setEnabled(True)
            
    def populate_existing_playlists(self):
        try:
            for playlist in self.plex_server.playlists():
                self.existing_combo.addItem(playlist.title, playlist)
        except Exception as e:
            logging.error(f"Error populating playlists: {str(e)}")
            
    def get_selected_playlists(self):
        selected = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected
        
    def merge_playlists(self):
        selected_playlists = self.get_selected_playlists()
        
        if len(selected_playlists) < 2:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least 2 playlists to merge.")
            return
            
        try:
            # Collect all tracks
            all_tracks = []
            track_signatures = set()  # For duplicate detection
            
            for playlist in selected_playlists:
                for track in playlist.items():
                    if self.remove_duplicates.isChecked():
                        # Create signature for duplicate detection
                        signature = f"{track.title}_{track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else '')}"
                        if signature not in track_signatures:
                            all_tracks.append(track)
                            track_signatures.add(signature)
                    else:
                        all_tracks.append(track)
            
            if not all_tracks:
                QMessageBox.warning(self, "No Tracks", "No tracks found in selected playlists.")
                return
                
            # Create or update target playlist
            if self.target_new.isChecked():
                playlist_name = self.new_name_input.text() or "Merged Playlist"
                target_playlist = self.plex_server.createPlaylist(playlist_name, items=all_tracks)
            else:
                target_playlist = self.existing_combo.currentData()
                if target_playlist:
                    target_playlist.addItems(all_tracks)
                    
            # Delete source playlists if requested
            if self.delete_source.isChecked():
                for playlist in selected_playlists:
                    if playlist != target_playlist:  # Don't delete target if it's in the selection
                        playlist.delete()
                        
            QMessageBox.information(self, "Success", 
                                  f"Successfully merged {len(selected_playlists)} playlists into '{target_playlist.title}' with {len(all_tracks)} tracks.")
            self.accept()
            
        except Exception as e:
            logging.error(f"Error merging playlists: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to merge playlists: {str(e)}")

class SyncThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    sync_complete = pyqtSignal(str, int, int)  # playlist_name, added_tracks, total_tracks
    error = pyqtSignal(str)

    def __init__(self, sync_configs, plex_server, parent=None):
        super().__init__(parent)
        self.sync_configs = sync_configs
        self.plex_server = plex_server
        self.spotify_auth = SpotifyAnonymousAuth()
        self.deezer_client = deezer.Client()
        self.tidal_client = TidalClient()
        self.stop_requested = False

    def run(self):
        try:
            for playlist_name, config in self.sync_configs.items():
                if self.stop_requested:
                    break
                    
                self.progress_update.emit(f"Syncing {playlist_name}...", 0)
                added_tracks = self.sync_playlist(playlist_name, config)
                self.sync_complete.emit(playlist_name, added_tracks, len(config.get('tracks', [])))
                
        except Exception as e:
            logging.error(f"Error in sync thread: {str(e)}")
            self.error.emit(str(e))

    def sync_playlist(self, playlist_name, config):
        try:
            # Get Plex playlist
            plex_playlist = None
            for playlist in self.plex_server.playlists():
                if playlist.title == playlist_name:
                    plex_playlist = playlist
                    break
                    
            if not plex_playlist:
                self.error.emit(f"Plex playlist '{playlist_name}' not found")
                return 0
                
            # Get current tracks in Plex playlist
            plex_tracks = set()
            for track in plex_playlist.items():
                signature = f"{track.title}_{track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else '')}"
                plex_tracks.add(signature.lower())
                
            # Get source tracks
            source_tracks = []
            source_url = config.get('source_url', '')
            
            if "spotify.com" in source_url:
                source_tracks = self.get_spotify_tracks(source_url)
            elif "deezer.com" in source_url:
                source_tracks = self.get_deezer_tracks(source_url)
            elif "tidal.com" in source_url:
                source_tracks = self.get_tidal_tracks(source_url)
            elif source_url.endswith('.m3u') or source_url.endswith('.m3u8'):
                source_tracks = self.get_m3u_tracks(source_url)
                
            # Find missing tracks
            missing_tracks = []
            library_section = self.plex_server.library.sectionByID(config.get('library_section'))
            
            for i, track_info in enumerate(source_tracks):
                if self.stop_requested:
                    break
                    
                track_signature = track_info.lower()
                if track_signature not in plex_tracks:
                    # Try to find track in Plex library
                    plex_track = self.find_best_match(library_section, track_info)
                    if plex_track:
                        missing_tracks.append(plex_track)
                        
                progress = int((i + 1) / len(source_tracks) * 100)
                self.progress_update.emit(f"Checking {playlist_name}... ({i+1}/{len(source_tracks)})", progress)
                
            # Add missing tracks to playlist
            if missing_tracks:
                plex_playlist.addItems(missing_tracks)
                
            return len(missing_tracks)
            
        except Exception as e:
            logging.error(f"Error syncing playlist {playlist_name}: {str(e)}")
            self.error.emit(f"Error syncing {playlist_name}: {str(e)}")
            return 0

    def get_spotify_tracks(self, url):
        try:
            token = self.spotify_auth.get_token()
            playlist_id = url.split('/')[-1].split('?')[0]
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            
            tracks = []
            tracks_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
            
            while tracks_url:
                response = requests.get(tracks_url, headers=headers)
                response.raise_for_status()
                tracks_data = response.json()
                
                for item in tracks_data['items']:
                    if item['track']:
                        track = item['track']
                        artist_name = track['artists'][0]['name'] if track['artists'] else 'Unknown Artist'
                        tracks.append(f"{track['name']} - {artist_name}")
                
                tracks_url = tracks_data.get('next')
                
            return tracks
        except Exception as e:
            logging.error(f"Error getting Spotify tracks: {str(e)}")
            return []

    def get_deezer_tracks(self, url):
        try:
            playlist_id = url.split('/')[-1]
            playlist = self.deezer_client.get_playlist(playlist_id)
            tracks = []
            for track in playlist.tracks:
                tracks.append(f"{track.title} - {track.artist.name}")
            return tracks
        except Exception as e:
            logging.error(f"Error getting Deezer tracks: {str(e)}")
            return []

    def get_tidal_tracks(self, url):
        try:
            playlist_uuid = url.split('/')[-1]
            tracks_data = self.tidal_client.get_playlist_tracks(playlist_uuid)
            tracks = []
            for item in tracks_data['items']:
                tracks.append(f"{item['title']} - {item['artist']['name']}")
            return tracks
        except Exception as e:
            logging.error(f"Error getting Tidal tracks: {str(e)}")
            return []

    def get_m3u_tracks(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.readlines()
            
            tracks = []
            for line in content:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse the track info regardless of format
                    parsed_track = self.parse_track_info_smart(line)
                    if parsed_track:
                        tracks.append(parsed_track)
            
            logging.info(f"Parsed {len(tracks)} tracks from M3U file: {file_path}")
            return tracks
            
        except Exception as e:
            logging.error(f"Error getting M3U tracks: {str(e)}")
            return []

    def parse_track_info_smart(self, track_line):
        """Smart parser that handles multiple M3U formats"""
        try:
            # Format 1: File path (like F:\Music\Artist\Album\Track.flac)
            if '\\' in track_line or '/' in track_line:
                return self.parse_file_path(track_line)
            
            # Format 2: "Track Title - Artist Name"
            elif ' - ' in track_line:
                parts = track_line.split(' - ', 1)
                return f"{parts[0].strip()} - {parts[1].strip()}"
            
            # Format 3: Just track title
            else:
                return track_line.strip()
                
        except Exception as e:
            logging.warning(f"Error parsing track info: {str(e)}")
            return track_line.strip()

    def parse_file_path(self, file_path):
        """Extract artist and track from file path"""
        try:
            # Get filename without extension
            import os
            filename = os.path.splitext(os.path.basename(file_path))[0]
            
            # Try different patterns based on your examples:
            # Pattern 1: "Artist - Track" (most common)
            if ' - ' in filename:
                parts = filename.split(' - ', 1)
                artist = parts[0].strip()
                track = parts[1].strip()
                return f"{track} - {artist}"
            
            # Pattern 2: Extract from folder structure
            # F:\Music\Artist\Album\filename
            path_parts = file_path.replace('\\', '/').split('/')
            if len(path_parts) >= 3:
                # Get artist from folder structure (second to last folder)
                artist = path_parts[-3] if len(path_parts) >= 4 else "Unknown Artist"
                
                # Clean up artist name (remove duplicates like "Calvin Harris" folder with "Calvin Harris - Track")
                if artist in filename:
                    # If artist name is in filename, extract just the track part
                    track = filename.replace(artist, '').strip(' -')
                else:
                    track = filename
                    
                return f"{track} - {artist}"
            
            # Fallback: just use filename
            return filename
            
        except Exception as e:
            logging.warning(f"Error parsing file path {file_path}: {str(e)}")
            return os.path.splitext(os.path.basename(file_path))[0]

    def find_best_match(self, library_section, track):
        try:
            title, artist = self.parse_track_info(track)
            all_tracks = library_section.searchTracks(title=title)
            
            best_match = None
            best_score = 0
            
            for plex_track in all_tracks:
                plex_title = plex_track.title if plex_track.title else ""
                title_score = fuzz.token_set_ratio(title.lower(), plex_title.lower())
                
                artist_score = 0
                if artist and plex_track.originalTitle:
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.originalTitle.lower())
                elif plex_track.artist():
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.artist().title.lower())
                
                combined_score = (title_score * 0.7) + (artist_score * 0.3)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = plex_track
            
            if best_score >= 70:
                return best_match
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error finding match for track: {str(e)}")
            return None

    def parse_track_info(self, track):
        """Legacy method - now just calls the smart parser"""
        parsed = self.parse_track_info_smart(track)
        
        # Return title, artist tuple for compatibility
        if ' - ' in parsed:
            parts = parsed.split(' - ', 1)
            return parts[0].strip(), parts[1].strip()
        else:
            return parsed.strip(), ''

    def stop(self):
        self.stop_requested = True

class PlaylistSortingThread(QThread):
    progress_update = pyqtSignal(str, int)
    sorting_complete = pyqtSignal(str, int, int)  # playlist_name, matched_count, total_count
    error = pyqtSignal(str)

    def __init__(self, playlist, streaming_url, plex_server, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.streaming_url = streaming_url
        self.plex_server = plex_server

    def run(self):
        try:
            self.progress_update.emit("Fetching streaming service playlist...", 10)
            
            # Get tracks from streaming service (reuse existing logic)
            streaming_tracks = self.get_streaming_tracks()
            
            if not streaming_tracks:
                self.error.emit("No tracks found in streaming service playlist.")
                return
            
            self.progress_update.emit("Loading current Plex playlist...", 30)
            
            # Get current Plex playlist tracks
            plex_tracks = list(self.playlist.items())
            
            self.progress_update.emit("Matching tracks...", 50)
            
            # Match and reorder tracks
            ordered_tracks = self.match_and_order_tracks(streaming_tracks, plex_tracks)
            
            if not ordered_tracks:
                self.error.emit("No matching tracks found between streaming service and Plex playlist.")
                return
            
            self.progress_update.emit("Reordering playlist...", 80)
            
            # Clear and rebuild playlist in new order
            self.playlist.removeItems(self.playlist.items())
            self.playlist.addItems(ordered_tracks)
            
            self.progress_update.emit("Complete!", 100)
            self.sorting_complete.emit(self.playlist.title, len(ordered_tracks), len(streaming_tracks))
            
        except Exception as e:
            logging.error(f"Error in playlist sorting: {str(e)}")
            self.error.emit(str(e))

    def get_streaming_tracks(self):
        """Get tracks from streaming service URL"""
        try:
            # Reuse existing PlaylistConverterThread logic
            if "spotify.com" in self.streaming_url:
                return self.get_spotify_tracks()
            elif "deezer.com" in self.streaming_url:
                return self.get_deezer_tracks()
            elif "tidal.com" in self.streaming_url:
                return self.get_tidal_tracks()
            else:
                raise ValueError("Unsupported streaming service")
                
        except Exception as e:
            logging.error(f"Error getting streaming tracks: {str(e)}")
            return []

    def get_spotify_tracks(self):
        """Get Spotify tracks - simplified version"""
        try:
            from main import SpotifyAnonymousAuth  # Import your existing auth
            auth = SpotifyAnonymousAuth()
            token = auth.get_token()
            
            playlist_id = self.streaming_url.split('/')[-1].split('?')[0]
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            }
            
            tracks = []
            tracks_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks'
            
            while tracks_url:
                response = requests.get(tracks_url, headers=headers)
                response.raise_for_status()
                tracks_data = response.json()
                
                for item in tracks_data['items']:
                    if item['track']:
                        track = item['track']
                        artist_name = track['artists'][0]['name'] if track['artists'] else 'Unknown Artist'
                        tracks.append(f"{track['name']} - {artist_name}")
                
                tracks_url = tracks_data.get('next')
                
            return tracks
        except Exception as e:
            logging.error(f"Error getting Spotify tracks: {str(e)}")
            return []

    def match_and_order_tracks(self, streaming_tracks, plex_tracks):
        """Match streaming tracks to Plex tracks and return in streaming order"""
        try:
            ordered_tracks = []
            
            for streaming_track in streaming_tracks:
                # Parse and clean streaming track info
                if ' - ' in streaming_track:
                    title, artist = streaming_track.split(' - ', 1)
                else:
                    title, artist = streaming_track, ''
                
                # ENHANCED: Clean the title to improve matching
                clean_title = self.clean_track_title(title)
                
                # Find best match in Plex tracks
                best_match = None
                best_score = 0
                
                for plex_track in plex_tracks:
                    try:
                        # Clean Plex track title too
                        clean_plex_title = self.clean_track_title(plex_track.title) if plex_track.title else ""
                        
                        # Calculate similarity with cleaned titles
                        from fuzzywuzzy import fuzz
                        
                        # Try multiple matching approaches
                        title_score = max(
                            fuzz.ratio(clean_title.lower(), clean_plex_title.lower()),
                            fuzz.partial_ratio(clean_title.lower(), clean_plex_title.lower()),
                            fuzz.token_set_ratio(clean_title.lower(), clean_plex_title.lower())
                        )
                        
                        artist_score = 0
                        if artist:
                            clean_artist = self.clean_artist_name(artist)
                            if plex_track.originalTitle:
                                plex_artist = self.clean_artist_name(plex_track.originalTitle)
                                artist_score = fuzz.token_set_ratio(clean_artist.lower(), plex_artist.lower())
                            elif hasattr(plex_track, 'artist') and plex_track.artist():
                                plex_artist = self.clean_artist_name(plex_track.artist().title)
                                artist_score = fuzz.token_set_ratio(clean_artist.lower(), plex_artist.lower())
                        
                        # Adjust weights - if no artist info, rely more on title
                        if artist:
                            combined_score = (title_score * 0.7) + (artist_score * 0.3)
                        else:
                            combined_score = title_score  # Pure title matching
                        
                        # LOWERED threshold and added logging for debugging
                        if combined_score > best_score and combined_score > 60:  # Was 70, now 60
                            best_score = combined_score
                            best_match = plex_track
                            
                    except Exception as e:
                        logging.warning(f"Error matching track: {str(e)}")
                        continue
                
                if best_match and best_match not in ordered_tracks:
                    ordered_tracks.append(best_match)
                    logging.info(f"✅ Matched '{streaming_track}' to '{best_match.title}' (score: {best_score:.1f})")
                else:
                    logging.warning(f"❌ No match for '{streaming_track}' (best score: {best_score:.1f})")
            
            return ordered_tracks
            
        except Exception as e:
            logging.error(f"Error matching tracks: {str(e)}")
            return []
    
    def clean_track_title(self, title):
        """Clean track title for better matching"""
        if not title:
            return ""
        
        import re
        
        # Remove common additions that cause matching issues
        cleaned = title
        
        # Remove feat/featuring variations (case insensitive)
        feat_patterns = [
            r'\(feat\.?\s+[^)]+\)',     # (feat. Artist)
            r'\(ft\.?\s+[^)]+\)',      # (ft. Artist)
            r'\(featuring\s+[^)]+\)',  # (featuring Artist)
            r'\(with\s+[^)]+\)',       # (with Artist)
            r'feat\.?\s+.+$',          # feat. Artist (at end)
            r'ft\.?\s+.+$',            # ft. Artist (at end)
            r'featuring\s+.+$',        # featuring Artist (at end)
        ]
        
        for pattern in feat_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove extra whitespace and common suffixes
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
        cleaned = cleaned.strip(' -()[]')       # Trim common chars
        
        return cleaned
    
    def clean_artist_name(self, artist):
        """Clean artist name for better matching"""
        if not artist:
            return ""
        
        import re
        
        # Remove "feat" mentions from artist field too
        cleaned = re.sub(r'\s*feat\.?\s+.+$', '', artist, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*ft\.?\s+.+$', '', artist, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*featuring\s+.+$', '', artist, flags=re.IGNORECASE)
        
        return cleaned.strip()

class SpotifyAnonymousAuth:
    def __init__(self):
        self.access_token = None
        self.token_expiration = 0
        self.client_id = None
        # Use a modern browser user agent for better compatibility
        self.spotify_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.user_agent = self.spotify_user_agent  # For compatibility
        self.session = requests.Session()
        
        # Configure session with retries
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        retry_strategy = Retry(
            total=3,
            connect=2,
            read=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def generate_totp(self):
        """
        Generate TOTP using the exact same method as the working JavaScript version
        """
        try:
            # cipher
            secret_cipher_bytes = [37, 84, 32, 76, 87, 90, 87, 47, 13, 75, 48, 54, 44, 28, 19, 21, 22]
            
            # Apply transformation: e ^ ((t % 33) + 9)
            transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_cipher_bytes)]
            
            # Join as string and encode
            joined = "".join(str(num) for num in transformed)
            secret_bytes = joined.encode('utf-8')
            secret = base64.b32encode(secret_bytes).decode().rstrip("=")
            
            # Create TOTP object
            totp_obj = pyotp.TOTP(secret, digits=6, interval=30)
            
            logging.info(f"Generated TOTP secret successfully")
            return totp_obj
            
        except Exception as e:
            logging.error(f"Error generating TOTP: {str(e)}")
            raise

    def fetch_server_time(self):
        """
        Fetch server time from Spotify using Date header
        """
        headers = {
            "User-Agent": self.spotify_user_agent,
            "Accept": "*/*",
        }
        
        try:
            response = self.session.head("https://open.spotify.com/", headers=headers, timeout=10)
            response.raise_for_status()
            
            # Extract server time from Date header
            date_header = response.headers.get("Date")
            if date_header:
                server_time = int(parsedate_to_datetime(date_header).timestamp())
                logging.info(f"Successfully obtained server time: {server_time}")
                return server_time
            else:
                raise Exception("No Date header found in response")
                
        except Exception as e:
            logging.warning(f"Failed to get server time from Date header: {str(e)}")
            # Fallback to local time
            return int(time.time())

    def generate_random_hex(self, length=8):
        """Generate random hex string for unique requests"""
        return secrets.token_hex(length // 2)

    def validate_token(self, access_token, client_id=None):
        """
        Test if token is valid by making a lightweight API call
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'User-Agent': self.spotify_user_agent,
            }
            
            if client_id:
                headers['Client-Id'] = client_id

            # Try markets endpoint first (public data)
            response = self.session.get('https://api.spotify.com/v1/markets', 
                                      headers=headers, timeout=10)
            
            logging.info(f"Token validation response: {response.status_code}")
            
            if response.status_code == 200:
                return True
            
            # Fallback: try a track endpoint
            response = self.session.get('https://api.spotify.com/v1/tracks/4iV5W9uYEdYUVa79Axb7Rh', 
                                      headers=headers, timeout=10)
            
            # Consider token valid if we don't get 401 Unauthorized
            return response.status_code != 401
            
        except Exception as e:
            logging.warning(f"Token validation failed: {str(e)}")
            return False

    def refresh_access_token(self, mode='transport'):
        """
        Refresh access token using the updated method
        """
        try:
            server_time = self.fetch_server_time()
            client_time = int(time.time() * 1000)  # milliseconds
            
            # Generate TOTP
            totp_obj = self.generate_totp()
            otp_value = totp_obj.at(server_time)
            
            logging.info(f"Generated OTP: {otp_value} for server time: {server_time}")
            
            # Build parameters
            params = {
                "reason": mode,
                "productType": "web-player",
                "totp": otp_value,
                "totpServer": otp_value,
                "totpVer": 8,
                "sTime": server_time,
                "cTime": client_time,
                "buildDate": time.strftime("%Y-%m-%d", time.gmtime(server_time)),
                "buildVer": f"web-player_{time.strftime('%Y-%m-%d', time.gmtime(server_time))}_{server_time * 1000}_{self.generate_random_hex(8)}",
            }
            
            # Headers
            headers = {
                "User-Agent": self.spotify_user_agent,
                "Accept": "application/json",
                "Referer": "https://open.spotify.com/",
                "App-Platform": "WebPlayer",
                "Origin": "https://open.spotify.com",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            
            # Try the updated token URL
            response = self.session.get(
                "https://open.spotify.com/api/token",
                params=params,
                headers=headers,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if 'accessToken' in data:
                    token_data = {
                        'access_token': data['accessToken'],
                        'expires_at': data.get('accessTokenExpirationTimestampMs', time.time() * 1000 + 3600000) / 1000,
                        'client_id': data.get('clientId', ''),
                    }
                    
                    logging.info(f"Successfully obtained token from {mode} mode")
                    return token_data
            
            raise Exception(f"Failed to get token in {mode} mode: HTTP {response.status_code}")
            
        except Exception as e:
            logging.error(f"Error in refresh_access_token ({mode}): {str(e)}")
            raise

    def get_token(self):
        """
        Get Spotify token using the updated authentication method with fallbacks
        """
        # Return cached token if still valid
        if self.access_token and time.time() < self.token_expiration:
            if self.validate_token(self.access_token, self.client_id):
                logging.info("✅ Using cached valid token")
                return self.access_token
            else:
                logging.info("❌ Cached token is invalid, refreshing...")
                self.access_token = None

        max_retries = 3
        last_error = None

        # Try transport mode first
        logging.info("🚀 Trying transport mode...")
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"📡 Transport mode attempt {attempt}/{max_retries}...")
                
                token_data = self.refresh_access_token('transport')
                
                # Validate token
                logging.info("🔐 Validating token...")
                if self.validate_token(token_data['access_token'], token_data.get('client_id')):
                    logging.info("✅ Transport mode token validated successfully!")
                    
                    # Cache the successful token
                    self.access_token = token_data['access_token']
                    self.token_expiration = token_data['expires_at']
                    self.client_id = token_data.get('client_id')
                    
                    return self.access_token
                else:
                    logging.warning("⚠️ Token validation failed, but proceeding anyway")
                    # Accept token even if validation fails (for anonymous tokens)
                    self.access_token = token_data['access_token']
                    self.token_expiration = token_data['expires_at']
                    self.client_id = token_data.get('client_id')
                    
                    return self.access_token
                    
            except Exception as e:
                last_error = e
                logging.warning(f"❌ Transport mode attempt {attempt} failed: {str(e)}")
                
                if attempt < max_retries:
                    delay = 2 ** (attempt - 1)  # Exponential backoff
                    logging.info(f"⏳ Waiting {delay}s before retry...")
                    time.sleep(delay)

        # If transport mode failed, try init mode
        logging.info("🔄 Transport mode failed, trying init mode...")
        
        for attempt in range(1, max_retries + 1):
            try:
                logging.info(f"📡 Init mode attempt {attempt}/{max_retries}...")
                
                token_data = self.refresh_access_token('init')
                
                # Validate token
                logging.info("🔐 Validating token...")
                if self.validate_token(token_data['access_token'], token_data.get('client_id')):
                    logging.info("✅ Init mode token validated successfully!")
                else:
                    logging.warning("⚠️ Token validation failed, but proceeding anyway")
                
                # Accept token regardless of validation result
                self.access_token = token_data['access_token']
                self.token_expiration = token_data['expires_at']
                self.client_id = token_data.get('client_id')
                
                logging.info("✅ Token set successfully!")
                return self.access_token
                
            except Exception as e:
                last_error = e
                logging.warning(f"❌ Init mode attempt {attempt} failed: {str(e)}")
                
                if attempt < max_retries:
                    delay = 2 ** (attempt - 1)
                    logging.info(f"⏳ Waiting {delay}s before retry...")
                    time.sleep(delay)

        # If all methods failed, try fallback methods
        logging.info("🔄 All primary methods failed, trying fallbacks...")
        try:
            return self._try_fallback_methods()
        except Exception as fallback_error:
            logging.error(f"❌ All fallback methods failed: {str(fallback_error)}")

        # Final failure
        error_msg = f"Failed to obtain valid Spotify token after all attempts. Last error: {str(last_error)}"
        logging.error(error_msg)
        raise Exception(error_msg)

    def _try_fallback_methods(self):
        """
        Try fallback authentication methods
        """
        fallback_methods = [
            self._try_without_totp,
            self._try_embed_method,
            self._try_web_player_method
        ]
        
        for method in fallback_methods:
            try:
                logging.info(f"Trying fallback method: {method.__name__}")
                token = method()
                if token:
                    return token
            except Exception as e:
                logging.warning(f"Fallback method {method.__name__} failed: {str(e)}")
                continue
                
        raise Exception("All fallback methods failed")

    def _try_without_totp(self):
        """Try to get token without TOTP"""
        headers = {
            "User-Agent": self.spotify_user_agent,
            "Accept": "application/json",
            "Referer": "https://open.spotify.com/",
            "App-Platform": "WebPlayer",
        }
        
        params = {
            "reason": "transport",
            "productType": "web_player"
        }
        
        response = self.session.get(
            "https://open.spotify.com/api/token",
            params=params,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if 'accessToken' in data:
                self.access_token = data['accessToken']
                self.token_expiration = data.get('accessTokenExpirationTimestampMs', time.time() * 1000 + 3600000) / 1000
                self.client_id = data.get('clientId')
                
                logging.info("Successfully obtained token without TOTP")
                return self.access_token
        
        raise Exception("No-TOTP method failed")

    def _try_embed_method(self):
        """Try embed method"""
        headers = {
            "User-Agent": self.spotify_user_agent,
            "Accept": "application/json",
        }
        
        params = {
            "reason": "transport",
            "productType": "embed"
        }
        
        response = self.session.get(
            "https://open.spotify.com/api/token",
            params=params,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if 'accessToken' in data:
                self.access_token = data['accessToken']
                self.token_expiration = data.get('accessTokenExpirationTimestampMs', time.time() * 1000 + 3600000) / 1000
                self.client_id = data.get('clientId')
                
                logging.info("Successfully obtained token using embed method")
                return self.access_token
        
        raise Exception("Embed method failed")

    def _try_web_player_method(self):
        """Try alternative web player method"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://open.spotify.com/',
        }
        
        # Try different parameter combinations
        param_sets = [
            {"reason": "transport", "productType": "web_player"},
            {"reason": "init", "productType": "web_player"},
            {"productType": "web_player"},
        ]
        
        for params in param_sets:
            try:
                response = self.session.get(
                    "https://open.spotify.com/get_access_token",  # Alternative URL
                    params=params,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'accessToken' in data:
                        self.access_token = data['accessToken']
                        self.token_expiration = data.get('accessTokenExpirationTimestampMs', time.time() * 1000 + 3600000) / 1000
                        self.client_id = data.get('clientId')
                        
                        logging.info(f"Successfully obtained token with params: {params}")
                        return self.access_token
            except Exception as e:
                continue
                
        raise Exception("Web player method failed")

    def is_token_valid(self):
        """Check if current token is still valid"""
        return self.access_token and time.time() < self.token_expiration

    def refresh_token_if_needed(self):
        """Refresh token if it's about to expire"""
        if not self.is_token_valid():
            self.access_token = None
            self.token_expiration = 0
            return self.get_token()
        return self.access_token


class TidalClient:
    BASE_URL = 'https://api.tidal.com/v1/'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'user-agent': 'TIDAL/3704 CFNetwork/1220.1 Darwin/20.3.0',
            'x-tidal-token': 'i4ZDjcyhed7Mu47q'
        })
    
    def get_playlist(self, uuid):
        response = self.session.get(f"{self.BASE_URL}playlists/{uuid}", params={'countryCode': 'US'})
        response.raise_for_status()
        return response.json()
    
    def get_playlist_tracks(self, uuid):
        response = self.session.get(f"{self.BASE_URL}playlists/{uuid}/tracks", params={'limit': 500, 'countryCode': 'US'})
        response.raise_for_status()
        return response.json()

class PlaylistConverterThread(QThread):
    progress_update = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, playlist_source, plex_server, library_section):
        super().__init__()
        self.playlist_source = playlist_source
        self.plex_server = plex_server
        self.library_section = library_section
        self.spotify_auth = SpotifyAnonymousAuth()
        self.deezer_client = deezer.Client()
        self.tidal_client = TidalClient()

    def run(self):
        try:
            if "open.spotify.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_spotify_playlist_info()
            elif "deezer.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_deezer_playlist_info()
            elif "tidal.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_tidal_playlist_info()    
            else:
                raise ValueError("Unsupported playlist source")

            self.create_plex_playlist(tracks, playlist_name, playlist_image_url)
            self.finished.emit()
        except Exception as e:
            logging.error(f"Error in PlaylistConverterThread: {str(e)}", exc_info=True)
            self.error.emit(str(e))

    def get_tidal_playlist_info(self):
        try:
            playlist_uuid = self.playlist_source.split('/')[-1]
            playlist_data = self.tidal_client.get_playlist(playlist_uuid)
            tracks_data = self.tidal_client.get_playlist_tracks(playlist_uuid)

            playlist_name = playlist_data['title']
            playlist_image_url = playlist_data['image']

            tracks = []
            with ThreadPoolExecutor(max_workers=25) as executor:
                future_to_track = {executor.submit(self.process_tidal_track, item): item for item in tracks_data['items']}
                for future in as_completed(future_to_track):
                    track = future.result()
                    if track:
                        tracks.append(track)
                    self.progress_update.emit(int(len(tracks) / tracks_data['totalNumberOfItems'] * 50))

            logging.info(f"Fetched {len(tracks)} tracks from Tidal playlist '{playlist_name}'")
            return tracks, playlist_name, playlist_image_url
        except Exception as e:
            logging.error(f"Error fetching Tidal playlist: {str(e)}")
            raise

    def process_tidal_track(self, item):
        try:
            return f"{item['title']} - {item['artist']['name']}"
        except Exception as e:
            logging.error(f"Error processing Tidal track: {str(e)}")
            return None

    def get_spotify_playlist_info(self):
        """
        Get Spotify playlist info with improved error handling and the fixed authentication
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Use the new authentication method
                token = self.spotify_auth.refresh_token_if_needed()
                playlist_id = self.playlist_source.split('/')[-1].split('?')[0]
                
                logging.info(f"Processing Spotify playlist ID: {playlist_id} (attempt {retry_count + 1})")
                
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'User-Agent': self.spotify_auth.spotify_user_agent,
                    'Accept': 'application/json',
                    'Referer': 'https://open.spotify.com/',
                }
                
                # Get playlist details
                logging.info("Fetching playlist details from Spotify API")
                response = requests.get(
                    f'https://api.spotify.com/v1/playlists/{playlist_id}',
                    headers=headers,
                    timeout=30
                )
                
                # Handle different HTTP status codes
                if response.status_code == 401:  # Unauthorized
                    logging.warning("Token expired or invalid, attempting to refresh...")
                    self.spotify_auth.access_token = None  # Force token refresh
                    retry_count += 1
                    time.sleep(2)  # Brief pause before retry
                    continue
                elif response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logging.warning(f"Rate limited, waiting {retry_after} seconds...")
                    time.sleep(min(retry_after, 60))
                    retry_count += 1
                    continue
                elif response.status_code == 403:  # Forbidden
                    raise ValueError("Access denied. Playlist may be private or unavailable.")
                elif response.status_code == 404:  # Not found
                    raise ValueError("Playlist not found. Please check the URL.")
                
                response.raise_for_status()
                playlist_data = response.json()
                
                playlist_name = playlist_data['name']
                playlist_image_url = playlist_data['images'][0]['url'] if playlist_data['images'] else None
                total_tracks = playlist_data['tracks']['total']
                
                logging.info(f"Found playlist: {playlist_name} with {total_tracks} tracks")
                
                # Get all tracks with pagination
                tracks = []
                tracks_url = f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=50'
                processed_tracks = 0
                
                while tracks_url:
                    try:
                        logging.info(f"Fetching tracks batch: {processed_tracks}/{total_tracks}")
                        
                        response = requests.get(tracks_url, headers=headers, timeout=30)
                        
                        # Handle rate limiting for tracks
                        if response.status_code == 429:
                            retry_after = int(response.headers.get('Retry-After', 30))
                            logging.warning(f"Rate limited on tracks, waiting {retry_after} seconds...")
                            time.sleep(min(retry_after, 30))
                            continue
                        elif response.status_code == 401:
                            # Token expired during track fetching
                            logging.warning("Token expired during track fetching, refreshing...")
                            token = self.spotify_auth.get_token()  # Get fresh token
                            headers['Authorization'] = f'Bearer {token}'
                            continue
                        
                        response.raise_for_status()
                        tracks_data = response.json()
                        
                        for item in tracks_data['items']:
                            if item and item.get('track'):
                                track = item['track']
                                if track and track.get('name'):
                                    artist_name = 'Unknown Artist'
                                    if track.get('artists') and len(track['artists']) > 0:
                                        artist_name = track['artists'][0]['name']
                                    
                                    tracks.append(f"{track['name']} - {artist_name}")
                                    processed_tracks += 1
                                    
                                    # Update progress
                                    if total_tracks > 0:
                                        progress = int((processed_tracks / total_tracks) * 50)
                                        self.progress_update.emit(progress)
                        
                        # Get next page
                        tracks_url = tracks_data.get('next')
                        
                        # Small delay to avoid rate limits
                        if tracks_url:
                            time.sleep(0.1)
                            
                    except requests.exceptions.Timeout:
                        logging.warning("Request timeout, retrying...")
                        time.sleep(2)
                        continue
                    except requests.exceptions.ConnectionError:
                        logging.warning("Connection error, retrying...")
                        time.sleep(5)
                        continue
        
                logging.info(f"Successfully fetched {len(tracks)} tracks from Spotify playlist '{playlist_name}'")
                return tracks, playlist_name, playlist_image_url
                
            except ValueError as e:
                # Don't retry on these errors
                logging.error(f"Spotify playlist error: {str(e)}")
                raise
                
            except Exception as e:
                logging.error(f"Unexpected error on attempt {retry_count + 1}: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logging.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"Failed to fetch Spotify playlist after {max_retries} attempts: {str(e)}")
        
        raise ValueError("Failed to fetch Spotify playlist after all retry attempts")

    def get_deezer_playlist_info(self):
        playlist_id = self.playlist_source.split('/')[-1]
        playlist = self.deezer_client.get_playlist(playlist_id)
        
        tracks = []
        for track in playlist.tracks:
            tracks.append(f"{track.title} - {track.artist.name}")
            self.progress_update.emit(int(len(tracks) / playlist.nb_tracks * 50))

        playlist_name = playlist.title
        playlist_image_url = playlist.picture_xl

        logging.info(f"Fetched {len(tracks)} tracks from Deezer playlist '{playlist_name}'")
        return tracks, playlist_name, playlist_image_url

    def create_plex_playlist(self, tracks, playlist_name, playlist_image_url):
        try:
            library_section = self.plex_server.library.sectionByID(self.library_section)
            
            plex_tracks = []
            not_found_tracks = []
            total_tracks = len(tracks)
            for i, track in enumerate(tracks):
                plex_track = self.find_best_match(library_section, track)
                if plex_track:
                    plex_tracks.append(plex_track)
                else:
                    not_found_tracks.append(track)
                self.progress_update.emit(50 + int((i + 1) / total_tracks * 50))
            if plex_tracks:
                plex_playlist = self.plex_server.createPlaylist(playlist_name, items=plex_tracks)
                
                # Set the playlist image if available
                if playlist_image_url:
                    try:
                        # First, try to download the image to a temporary file
                        import tempfile
                        import os
                        
                        # Create a temporary file
                        temp_dir = tempfile.gettempdir()
                        temp_file = os.path.join(temp_dir, "playlist_image.jpg")
                        
                        # Download the image
                        img_response = requests.get(playlist_image_url, 
                                                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})
                        img_response.raise_for_status()
                        
                        # Save the image to the temporary file
                        with open(temp_file, 'wb') as f:
                            f.write(img_response.content)
                        
                        # Upload the local file to Plex
                        plex_playlist.uploadPoster(filepath=temp_file)
                        logging.info(f"Successfully set thumbnail for playlist '{playlist_name}' using local file")
                        
                        # Clean up the temporary file
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    except Exception as thumb_error:
                        logging.error(f"Failed to upload thumbnail file: {str(thumb_error)}")
                        # Fall back to the original URL method
                        try:
                            from urllib.parse import quote
                            encoded_url = quote(playlist_image_url)
                            poster_url = f"{self.plex_server._baseurl}/library/metadata/{plex_playlist.ratingKey}/posters"
                            params = {
                                'url': encoded_url,
                                'X-Plex-Token': self.plex_server._token
                            }
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                            response = requests.post(poster_url, params=params, headers=headers)
                            response.raise_for_status()
                            logging.info(f"Successfully set thumbnail for playlist '{playlist_name}'")
                        except Exception as url_thumb_error:
                            logging.error(f"Failed to set thumbnail: {str(url_thumb_error)}")
                
                logging.info(f"Successfully created playlist '{playlist_name}' with {len(plex_tracks)} tracks")
                if not_found_tracks:
                    logging.warning(f"Could not find matches for {len(not_found_tracks)} tracks in your Plex library")
                    for track in not_found_tracks:
                        logging.warning(f"Not found: {track}")
            else:
                raise ValueError("No matching tracks found in your Plex library")
        except Exception as e:
            logging.error(f"Error creating Plex playlist: {str(e)}", exc_info=True)
            raise ValueError(f"Error creating Plex playlist: {e}")

    def find_best_match(self, library_section, track):
        title, artist = self.parse_track_info(track)
        all_tracks = library_section.searchTracks(title=title)
        
        best_match = None
        best_score = 0
        
        for plex_track in all_tracks:
            # Calculate similarity score for title
            plex_title = plex_track.title if plex_track.title else ""
            title_score = fuzz.token_set_ratio(title.lower(), plex_title.lower())
            
            # Calculate similarity score for artist if available
            artist_score = 0
            if artist and plex_track.originalTitle:
                artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.originalTitle.lower())
            elif plex_track.artist():
                artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.artist().title.lower())
            
            # Weighted average of title and artist scores
            combined_score = (title_score * 0.7) + (artist_score * 0.3)
            
            if combined_score > best_score:
                best_score = combined_score
                best_match = plex_track
        
        if best_score >= 70:  # Lowered threshold for more matches
            logging.info(f"Matched '{track}' to '{best_match.title} - {best_match.originalTitle or best_match.artist().title}' (score: {best_score})")
            return best_match
        else:
            logging.warning(f"No good match found for '{track}' (best score: {best_score})")
            return None

    def parse_track_info(self, track):
        parts = track.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        else:
            return track.strip(), ''

class ModernButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "modern-button")

class ModernLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(40)

class PlexPlaylistManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.playlists = []
        self.playlist_data = []  # Store playlist objects with track counts
        self.plex_server = None
        self.spotify_client = None
        self.sync_thread = None
        self.fetch_thread = None
        self.export_thread = None  # Add export thread tracking
        self.backup_thread = None  # Add backup thread tracking
        self.batch_track_count_thread = None  # Add batch track count thread
        self.loading_dialog = None
        self.playlist_cache = PlaylistCache()  # Initialize cache system
        self.track_count_threads = {}  # Keep track of background track count loading
        self.auto_sync_timer = QTimer()
        self.auto_sync_timer.timeout.connect(self.perform_auto_sync)
        self.initUI()
        self.load_config()
        self.setStyleSheet(self.get_stylesheet())
        self.setWindowTitle('Syncra - Playlist Manager')
        self.setWindowIcon(QIcon('Syncra Icon.ico'))
        self.resize(1400, 900)
        
    def get_logo_svg(self):
        """Return the complete SVG logo code"""
        return """
        <svg width="250" height="100" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <!-- Original vibrant gradient -->
                <linearGradient id="mainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#00E676"/>
                    <stop offset="50%" style="stop-color:#00BCD4"/>
                    <stop offset="100%" style="stop-color:#2196F3"/>
                </linearGradient>
                
                <!-- Text gradient - Subtle blue gradient -->
                <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style="stop-color:#42A5F5"/>
                    <stop offset="100%" style="stop-color:#2196F3"/>
                </linearGradient>
                
                <!-- Radial gradient for depth -->
                <radialGradient id="radialGrad" cx="50%" cy="30%">
                    <stop offset="0%" style="stop-color:#00E676"/>
                    <stop offset="100%" style="stop-color:#2196F3"/>
                </radialGradient>
            </defs>
            
            <!-- Overlapping vinyl records -->
            <g transform="translate(10, 20)">
                <!-- First record -->
                <circle cx="25" cy="30" r="25" fill="none" stroke="url(#mainGrad)" stroke-width="4"/>
                <circle cx="25" cy="30" r="15" fill="none" stroke="url(#mainGrad)" stroke-width="2" opacity="0.7"/>
                <circle cx="25" cy="30" r="5" fill="url(#mainGrad)"/>
                
                <!-- Second record (overlapping) -->
                <circle cx="45" cy="30" r="25" fill="none" stroke="url(#mainGrad)" stroke-width="4" opacity="0.8"/>
                <circle cx="45" cy="30" r="15" fill="none" stroke="url(#mainGrad)" stroke-width="2" opacity="0.6"/>
                <circle cx="45" cy="30" r="5" fill="url(#mainGrad)" opacity="0.8"/>
                
                <!-- SYNCRA text -->
                <text x="85" y="40" font-family="Inter, sans-serif" font-size="32" font-weight="800" fill="url(#textGrad)" letter-spacing="-1px">SYNCRA</text>
            </g>
        </svg>
        """

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        # REPLACE the logo section with SVG
        from PyQt5.QtSvg import QSvgWidget
        from PyQt5.QtCore import QByteArray
        
        # Create SVG logo
        logo_widget = QSvgWidget()
        svg_data = QByteArray(self.get_logo_svg().encode('utf-8'))
        logo_widget.load(svg_data)
        logo_widget.setFixedSize(250, 100)
        sidebar_layout.addWidget(logo_widget)
        
        self.connection_btn = ModernButton('Connection')
        self.playlists_btn = ModernButton('Playlists')
        # REMOVED: self.import_export_btn = ModernButton('Import/Export')
        self.streaming_btn = ModernButton('Streaming Import')
        self.local_tracks_btn = ModernButton('Local Tracks')
        self.sync_btn = ModernButton('Sync Manager')
        self.tools_btn = ModernButton('Tools & Utilities')
        
        sidebar_layout.addWidget(self.connection_btn)
        sidebar_layout.addWidget(self.playlists_btn)
        # REMOVED: sidebar_layout.addWidget(self.import_export_btn)
        sidebar_layout.addWidget(self.streaming_btn)
        sidebar_layout.addWidget(self.local_tracks_btn)
        sidebar_layout.addWidget(self.sync_btn)
        sidebar_layout.addWidget(self.tools_btn)
        sidebar_layout.addStretch()
        
        main_layout.addWidget(sidebar)
        
        # Main content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)
        
        # Create pages
        self.create_connection_page()
        self.create_playlists_page()
        # REMOVED: self.create_import_export_page()
        self.create_streaming_services_page()
        self.create_local_tracks_page()
        self.create_sync_manager_page()
        self.create_tools_page()
        
        # Connect buttons to switch pages (updated indices)
        self.connection_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.playlists_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        # REMOVED: self.import_export_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.streaming_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))  # Changed from 3 to 2
        self.local_tracks_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))  # Changed from 4 to 3
        self.sync_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(4))  # Changed from 5 to 4
        self.tools_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(5))  # Changed from 6 to 5
        
        # Status bar
        self.statusBar().showMessage('Ready')

    def create_sync_manager_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("<h2>Playlist Synchronization Manager</h2>"))
        header_layout.addStretch()
        
        # Auto-sync controls
        self.auto_sync_checkbox = QCheckBox("Enable Auto-Sync")
        self.auto_sync_checkbox.stateChanged.connect(self.toggle_auto_sync)
        header_layout.addWidget(self.auto_sync_checkbox)
        
        self.sync_interval_spinbox = QSpinBox()
        self.sync_interval_spinbox.setMinimum(5)
        self.sync_interval_spinbox.setMaximum(1440)  # 24 hours
        self.sync_interval_spinbox.setValue(60)
        self.sync_interval_spinbox.setSuffix(" minutes")
        header_layout.addWidget(QLabel("Interval:"))
        header_layout.addWidget(self.sync_interval_spinbox)
        
        layout.addLayout(header_layout)
        
        # Sync configurations
        sync_group = QGroupBox("Sync Configurations")
        sync_layout = QVBoxLayout(sync_group)
        
        # Add new sync config
        add_config_layout = QHBoxLayout()
        
        self.sync_playlist_combo = QComboBox()
        self.sync_playlist_combo.setMinimumWidth(200)
        add_config_layout.addWidget(QLabel("Plex Playlist:"))
        add_config_layout.addWidget(self.sync_playlist_combo)
        
        self.sync_source_input = QLineEdit()
        self.sync_source_input.setPlaceholderText("Enter streaming service URL or M3U file path")
        add_config_layout.addWidget(QLabel("Source:"))
        add_config_layout.addWidget(self.sync_source_input)
        
        self.add_sync_config_btn = ModernButton("Add Sync Config")
        self.add_sync_config_btn.clicked.connect(self.add_sync_config)
        add_config_layout.addWidget(self.add_sync_config_btn)
        
        sync_layout.addLayout(add_config_layout)
        
        # Sync configurations table
        self.sync_configs_table = QTableWidget()
        self.sync_configs_table.setColumnCount(4)
        self.sync_configs_table.setHorizontalHeaderLabels(["Playlist", "Source", "Last Sync", "Actions"])
        self.sync_configs_table.horizontalHeader().setStretchLastSection(True)
        
        # HIDE THE VERTICAL HEADER (row numbers) - this removes the white bar
        self.sync_configs_table.verticalHeader().setVisible(False)
        
        # FIXED: Set proper column widths for buttons to be visible
        self.sync_configs_table.setColumnWidth(0, 200)  # Playlist
        self.sync_configs_table.setColumnWidth(1, 300)  # Source
        self.sync_configs_table.setColumnWidth(2, 150)  # Last Sync
        self.sync_configs_table.setColumnWidth(3, 180)  # Actions - wider for buttons
        sync_layout.addWidget(self.sync_configs_table)
        
        layout.addWidget(sync_group)
        
        # Manual sync controls
        manual_group = QGroupBox("Manual Sync")
        manual_layout = QHBoxLayout(manual_group)
        
        self.sync_selected_btn = ModernButton("Sync Selected")
        self.sync_selected_btn.clicked.connect(self.sync_selected_playlists)
        manual_layout.addWidget(self.sync_selected_btn)
        
        self.sync_all_btn = ModernButton("Sync All")
        self.sync_all_btn.clicked.connect(self.sync_all_playlists)
        manual_layout.addWidget(self.sync_all_btn)
        
        manual_layout.addStretch()
        
        layout.addWidget(manual_group)
        
        # Sync progress
        self.sync_progress_group = QGroupBox("Sync Progress")
        self.sync_progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self.sync_progress_group)
        
        self.sync_status_label = QLabel("Ready")
        progress_layout.addWidget(self.sync_status_label)
        
        self.sync_progress_bar = QProgressBar()
        progress_layout.addWidget(self.sync_progress_bar)
        
        self.stop_sync_btn = ModernButton("Stop Sync")
        self.stop_sync_btn.clicked.connect(self.stop_sync)
        progress_layout.addWidget(self.stop_sync_btn)
        
        layout.addWidget(self.sync_progress_group)
        
        # Sync log
        log_group = QGroupBox("Sync Log")
        log_layout = QVBoxLayout(log_group)
        
        self.sync_log = QTextEdit()
        self.sync_log.setMaximumHeight(150)
        self.sync_log.setReadOnly(True)
        log_layout.addWidget(self.sync_log)
        
        layout.addWidget(log_group)
        
        self.content_stack.addWidget(page)
        
    def create_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Tools header
        layout.addWidget(QLabel("<h2>Tools & Utilities</h2>"))
        
        # Playlist operations
        playlist_ops_group = QGroupBox("Playlist Operations")
        playlist_ops_layout = QGridLayout(playlist_ops_group)
        
        # Merge playlists
        self.merge_playlists_btn = ModernButton("Merge Playlists")
        self.merge_playlists_btn.clicked.connect(self.show_playlist_merger)
        playlist_ops_layout.addWidget(self.merge_playlists_btn, 0, 0)
        
        # Duplicate detection
        self.find_duplicates_btn = ModernButton("Find Duplicate Tracks")
        self.find_duplicates_btn.clicked.connect(self.find_duplicate_tracks)
        playlist_ops_layout.addWidget(self.find_duplicates_btn, 0, 1)
        
        # Backup playlists
        self.backup_playlists_btn = ModernButton("Backup All Playlists")
        self.backup_playlists_btn.clicked.connect(self.backup_all_playlists)
        playlist_ops_layout.addWidget(self.backup_playlists_btn, 1, 0)
        
        # Restore playlists
        self.restore_playlists_btn = ModernButton("Restore Playlists")
        self.restore_playlists_btn.clicked.connect(self.restore_playlists)
        playlist_ops_layout.addWidget(self.restore_playlists_btn, 1, 1)
        
        layout.addWidget(playlist_ops_group)
        
        # Statistics
        stats_group = QGroupBox("Playlist Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_text)
        
        self.update_stats_btn = ModernButton("Update Statistics")
        self.update_stats_btn.clicked.connect(self.update_playlist_statistics)
        stats_layout.addWidget(self.update_stats_btn)
        
        layout.addWidget(stats_group)
        
        # Library analysis
        analysis_group = QGroupBox("Library Analysis")
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMaximumHeight(200)
        analysis_layout.addWidget(self.analysis_text)
        
        self.analyze_library_btn = ModernButton("Analyze Music Library")
        self.analyze_library_btn.clicked.connect(self.analyze_music_library)
        analysis_layout.addWidget(self.analyze_library_btn)
        
        layout.addWidget(analysis_group)
        
        layout.addStretch()
        self.content_stack.addWidget(page)

    def create_local_tracks_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
    
        # Folder selection section
        folder_group = QGroupBox("Select Music Folder")
        folder_layout = QVBoxLayout()
    
        folder_select_layout = QHBoxLayout()
        self.folder_path_input = ModernLineEdit()
        self.folder_path_input.setPlaceholderText("Select a folder containing music tracks")
        folder_select_layout.addWidget(self.folder_path_input)
    
        browse_folder_button = ModernButton('Browse')
        browse_folder_button.clicked.connect(self.browse_music_folder)
        folder_select_layout.addWidget(browse_folder_button)
        folder_layout.addLayout(folder_select_layout)
    
        # Option to include subfolders
        self.include_subfolders_checkbox = QCheckBox("Include subfolders")
        self.include_subfolders_checkbox.setChecked(True)
        folder_layout.addWidget(self.include_subfolders_checkbox)
    
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
    
        # Track list section
        track_group = QGroupBox("Available Tracks")
        track_layout = QVBoxLayout()
    
        self.track_listwidget = QListWidget()
        self.track_listwidget.setSelectionMode(QListWidget.ExtendedSelection)
        track_layout.addWidget(self.track_listwidget)
    
        # Controls for track list
        track_controls_layout = QHBoxLayout()
        self.scan_folder_button = ModernButton('Scan Folder')
        self.scan_folder_button.clicked.connect(self.scan_music_folder)
        track_controls_layout.addWidget(self.scan_folder_button)
    
        self.select_all_tracks_checkbox = QCheckBox("Select All")
        self.select_all_tracks_checkbox.stateChanged.connect(self.select_all_tracks)
        track_controls_layout.addWidget(self.select_all_tracks_checkbox)
        track_layout.addLayout(track_controls_layout)
    
        track_group.setLayout(track_layout)
        layout.addWidget(track_group)
    
        # Playlist creation section
        playlist_group = QGroupBox("Create Playlist")
        playlist_layout = QVBoxLayout()
    
        # Playlist name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Playlist Name:"))
        self.local_playlist_name_input = ModernLineEdit()
        self.local_playlist_name_input.setPlaceholderText("Enter a name for your playlist")
        name_layout.addWidget(self.local_playlist_name_input)
        playlist_layout.addLayout(name_layout)
    
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self.create_m3u_button = ModernButton('Create M3U File')
        self.create_m3u_button.clicked.connect(self.create_m3u_from_selection)
        buttons_layout.addWidget(self.create_m3u_button)
        
        self.add_to_plex_button = ModernButton('Add to Plex')
        self.add_to_plex_button.clicked.connect(self.add_tracks_to_plex)
        buttons_layout.addWidget(self.add_to_plex_button)
        
        playlist_layout.addLayout(buttons_layout)
        playlist_group.setLayout(playlist_layout)
        layout.addWidget(playlist_group)
    
        self.content_stack.addWidget(page)
    
    def show_playlist_context_menu(self, position):
        """Show context menu for main playlist list"""
        item = self.playlist_listwidget.itemAt(position)
        if not item:
            return
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
        """)
        
        # Add actions
        sort_action = menu.addAction("🔄 Sort by Streaming Service...")
        menu.addSeparator()
        edit_action = menu.addAction("✏️ Edit Playlist")
        delete_action = menu.addAction("🗑️ Delete Playlist")
        
        # Show menu and handle selection
        action = menu.exec_(self.playlist_listwidget.mapToGlobal(position))
        
        if action == sort_action:
            self.sort_playlist_by_streaming_service(item)
        elif action == edit_action:
            self.edit_playlist_item(item)
        elif action == delete_action:
            # Temporarily select the item and delete
            self.playlist_listwidget.setCurrentItem(item)
            item.setCheckState(Qt.Checked)
            self.delete_selected_playlist()

    def sort_playlist_by_streaming_service(self, playlist_item):
        """Sort playlist by streaming service order"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Get playlist object
        playlist = playlist_item.data(Qt.UserRole)
        if not playlist:
            # Fallback: find by name
            playlist_name = playlist_item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '')
            playlist = next((p for p in self.playlists if p.title == playlist_name), None)
        
        if not playlist:
            QMessageBox.warning(self, "Playlist Not Found", "Could not find the playlist.")
            return
        
        # Show URL input dialog
        url, ok = QInputDialog.getText(
            self,
            "Sort by Streaming Service",
            f"Enter Spotify, Deezer, or Tidal playlist URL to sort '{playlist.title}' by:\n\n"
            "The playlist will be reordered to match the streaming service order.",
            text=""
        )
        
        if ok and url.strip():
            self.start_playlist_sorting(playlist, url.strip())
    
    def start_playlist_sorting(self, playlist, streaming_url):
        """Start the playlist sorting process"""
        if not streaming_url:
            return
        
        # Validate URL
        if not any(service in streaming_url for service in ['spotify.com', 'deezer.com', 'tidal.com']):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid Spotify, Deezer, or Tidal playlist URL.")
            return
        
        # Show loading dialog
        self.show_loading("Sorting playlist...", "Fetching streaming service playlist...")
        
        # Start sorting thread
        self.sort_thread = PlaylistSortingThread(playlist, streaming_url, self.plex_server, self)
        self.sort_thread.progress_update.connect(self.update_sorting_progress)
        self.sort_thread.sorting_complete.connect(self.on_sorting_complete)
        self.sort_thread.error.connect(self.on_sorting_error)
        self.sort_thread.start()
    
    def update_sorting_progress(self, message, percentage):
        """Update sorting progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
    
    def on_sorting_complete(self, playlist_name, matched_count, total_count):
        """Handle sorting completion"""
        self.hide_loading()
        QMessageBox.information(self, "Sorting Complete", 
                              f"✅ Sorted '{playlist_name}' successfully!\n\n"
                              f"Matched {matched_count} out of {total_count} tracks from streaming service.")
        self.fetch_playlists()  # Refresh playlist list
    
    def on_sorting_error(self, error_message):
        """Handle sorting error"""
        self.hide_loading()
        QMessageBox.critical(self, "Sorting Error", f"Failed to sort playlist:\n{error_message}")

    def browse_music_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if folder:
            self.folder_path_input.setText(folder)
            self.scan_music_folder()
    
    def scan_music_folder(self):
        folder_path = self.folder_path_input.text()
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid folder.")
            return
        
        self.track_listwidget.clear()
        
        # Supported audio file extensions
        audio_extensions = ['.mp3', '.flac', '.m4a', '.wav', '.ogg', '.aac', '.wma']
        
        try:
            if self.include_subfolders_checkbox.isChecked():
                # Walk through the directory and all subdirectories
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in audio_extensions:
                            full_path = os.path.join(root, file)
                            # Display relative path from the selected folder
                            relative_path = os.path.relpath(full_path, folder_path)
                            item = QListWidgetItem(relative_path)
                            item.setData(Qt.UserRole, full_path)  # Store the full path as data
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Unchecked)
                            self.track_listwidget.addItem(item)
            else:
                # Only list files in the current directory, not subdirectories
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in audio_extensions:
                            item = QListWidgetItem(file)
                            item.setData(Qt.UserRole, file_path)  # Store the full path as data
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Unchecked)
                            self.track_listwidget.addItem(item)
            
            self.statusBar().showMessage(f"Found {self.track_listwidget.count()} audio files.")
        except Exception as e:
            logging.error(f"Error scanning music folder: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Scan Error", f"Error scanning folder: {str(e)}")
    
    def select_all_tracks(self, state):
        for index in range(self.track_listwidget.count()):
            item = self.track_listwidget.item(index)
            item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)
    
    def get_selected_tracks(self):
        selected_tracks = []
        for index in range(self.track_listwidget.count()):
            item = self.track_listwidget.item(index)
            if item.checkState() == Qt.Checked:
                selected_tracks.append(item.data(Qt.UserRole))  # Get the full path
        return selected_tracks
    
    def create_m3u_from_selection(self):
        selected_tracks = self.get_selected_tracks()
        if not selected_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to include in the playlist.")
            return
        
        playlist_name = self.local_playlist_name_input.text() or "New Playlist"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save M3U Playlist", 
                                                 f"{playlist_name}.m3u", 
                                                 "M3U Playlist (*.m3u)")
        if not save_path:
            return
        
        try:
            with open(save_path, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")
                for track_path in selected_tracks:
                    file.write(f"{track_path}\n")
            
            self.statusBar().showMessage(f"Playlist saved to {save_path}")
            
            reply = QMessageBox.question(self, 'Import to Plex', 
                                       'Would you like to import this playlist to Plex?',
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.upload_playlist(save_path)
        except Exception as e:
            logging.error(f"Error creating M3U file: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to create playlist file: {str(e)}")
    
    def add_tracks_to_plex(self):
        selected_tracks = self.get_selected_tracks()
        if not selected_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to add to Plex.")
            return
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        playlist_name = self.local_playlist_name_input.text() or "New Playlist"
        
        section_id = self.section_combo.currentData()
        if not section_id:
            QMessageBox.warning(self, "No Library Selected", "Please select a music library section.")
            return
        
        try:
            # Create a temporary M3U file
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"{playlist_name}.m3u")
            
            with open(temp_file, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")
                for track_path in selected_tracks:
                    file.write(f"{track_path}\n")
            
            # Upload the playlist to Plex
            self.upload_playlist(temp_file)
            
            # Delete the temporary file
            try:
                os.remove(temp_file)
            except:
                pass
                
        except Exception as e:
            logging.error(f"Error adding tracks to Plex: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to add tracks to Plex: {str(e)}")    

    def create_connection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        self.plex_username_input = ModernLineEdit()
        self.plex_username_input.setPlaceholderText("Plex Username")
        form_layout.addWidget(self.plex_username_input)

        self.plex_password_input = ModernLineEdit()
        self.plex_password_input.setPlaceholderText("Plex Password")
        self.plex_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.plex_password_input)

        self.server_ip_input = ModernLineEdit()
        self.server_ip_input.setPlaceholderText("Plex Server IP")
        form_layout.addWidget(self.server_ip_input)

        self.server_port_input = ModernLineEdit()
        self.server_port_input.setPlaceholderText("Plex Server Port")
        form_layout.addWidget(self.server_port_input)

        self.token_input = ModernLineEdit()
        self.token_input.setPlaceholderText("Plex Token (Optional)")
        form_layout.addWidget(self.token_input)

        self.section_combo = QComboBox()
        self.section_combo.addItem("Library Section")
        self.section_combo.setCurrentIndex(0)
        form_layout.addWidget(self.section_combo)

        layout.addLayout(form_layout)

        connect_button = ModernButton('Connect to Plex')
        connect_button.clicked.connect(self.connect_to_plex)
        layout.addWidget(connect_button)

        layout.addStretch()
        self.content_stack.addWidget(page)

    def create_playlists_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Top buttons row
        buttons_layout = QHBoxLayout()
        self.fetch_playlists_button = ModernButton('Fetch Playlists')
        self.fetch_playlists_button.clicked.connect(self.fetch_playlists)
        buttons_layout.addWidget(self.fetch_playlists_button)
        
        self.delete_playlist_button = ModernButton('Delete Selected')
        self.delete_playlist_button.clicked.connect(self.delete_selected_playlist)
        buttons_layout.addWidget(self.delete_playlist_button)
        
        self.edit_playlist_button = ModernButton('Edit Selected')
        self.edit_playlist_button.clicked.connect(self.edit_selected_playlist)
        buttons_layout.addWidget(self.edit_playlist_button)
        
        # Cache management buttons
        self.refresh_all_button = ModernButton('Refresh All Counts')
        self.refresh_all_button.clicked.connect(self.refresh_all_track_counts)
        self.refresh_all_button.setToolTip("Refresh track counts for all playlists")
        buttons_layout.addWidget(self.refresh_all_button)
        
        self.clear_cache_button = ModernButton('Clear Cache')
        self.clear_cache_button.clicked.connect(self.clear_playlist_cache)
        self.clear_cache_button.setToolTip("Clear all cached playlist data")
        buttons_layout.addWidget(self.clear_cache_button)
        
        layout.addLayout(buttons_layout)
        
        # Info label with better instructions
        self.cache_info_label = QLabel("💡 Track counts load instantly when cached. Click any playlist to load tracks on-demand. Double-click to edit.")
        self.cache_info_label.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        layout.addWidget(self.cache_info_label)
        
        # NEW: Import/Export section
        import_export_group = QGroupBox("Import & Export")
        ie_layout = QVBoxLayout(import_export_group)
        
        # Import section
        import_layout = QHBoxLayout()
        self.playlist_input = ModernLineEdit()
        self.playlist_input.setPlaceholderText("Path to .m3u Playlist or Directory")
        import_layout.addWidget(self.playlist_input)
        
        browse_button = ModernButton('Browse')
        browse_button.clicked.connect(self.browse_files)
        import_layout.addWidget(browse_button)
        
        import_button = ModernButton('Import Playlist(s)')
        import_button.clicked.connect(self.import_playlist)
        import_layout.addWidget(import_button)
        
        ie_layout.addLayout(import_layout)
        
        # Progress bar
        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        ie_layout.addWidget(self.import_progress)
        
        # Export button
        export_button = ModernButton('Export Selected Playlists')
        export_button.clicked.connect(self.export_selected_playlists)
        ie_layout.addWidget(export_button)
        
        layout.addWidget(import_export_group)
        
        # Playlist list
        self.playlist_listwidget = QListWidget()
        self.playlist_listwidget.setSelectionMode(QListWidget.ExtendedSelection)
        self.playlist_listwidget.itemDoubleClicked.connect(self.edit_playlist_item)
        # NEW: Add single-click handler for responsive track count loading
        self.playlist_listwidget.itemClicked.connect(self.on_playlist_clicked)

        self.playlist_listwidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_listwidget.customContextMenuRequested.connect(self.show_playlist_context_menu)

        layout.addWidget(self.playlist_listwidget)
        
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.select_all_playlists)
        layout.addWidget(self.select_all_checkbox)
        
        self.content_stack.addWidget(page)
    
    def on_playlist_clicked(self, item):
        """Handle single click on playlist to load track count responsively"""
        try:
            playlist = item.data(Qt.UserRole)
            if not playlist:
                return
            
            playlist_id = str(playlist.ratingKey)
            cached_count = self.playlist_cache.get_track_count(playlist_id)
            
            # If not cached, load track count with minimal UI feedback
            if cached_count is None and playlist_id not in self.track_count_threads:
                # Update status bar immediately to show responsiveness
                self.statusBar().showMessage(f"Loading track count for '{playlist.title}'...")
                
                # Start async loading without blocking dialog
                self.load_track_count_on_demand_silent(playlist)
                
        except Exception as e:
            logging.error(f"Error handling playlist click: {str(e)}")
    
    def load_track_count_on_demand_silent(self, playlist):
        """Load track count silently in background without blocking UI"""
        playlist_id = str(playlist.ratingKey)
        
        if playlist_id in self.track_count_threads:
            return  # Already loading
        
        # Update UI to show loading immediately (non-blocking)
        self.update_playlist_item_loading(playlist_id)
        
        # Start background loading
        thread = LoadTrackCountThread(playlist, self.playlist_cache, self)
        thread.progress_update.connect(lambda msg, pct: self.statusBar().showMessage(f"{msg}"))
        thread.track_count_loaded.connect(self.on_track_count_loaded_silent)
        thread.error.connect(self.on_track_count_error)
        thread.finished.connect(lambda: self.track_count_threads.pop(playlist_id, None))
        
        self.track_count_threads[playlist_id] = thread
        thread.start()
    
    def on_track_count_loaded_silent(self, playlist_id, track_count):
        """Handle track count loaded silently (for single clicks)"""
        # Update the display
        self.update_playlist_item_count(playlist_id, track_count)
        
        # Update the playlist_data cache in memory
        for i, (playlist, _) in enumerate(self.playlist_data):
            if str(playlist.ratingKey) == playlist_id:
                self.playlist_data[i] = (playlist, track_count)
                break
        
        # Show completion in status bar
        self.statusBar().showMessage(f"Loaded {track_count} tracks", 2000)  # Clear after 2 seconds

    def create_streaming_services_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        streaming_group = QGroupBox("Import from Streaming Services")
        streaming_layout = QVBoxLayout()

        self.playlist_url_input = ModernLineEdit()
        self.playlist_url_input.setPlaceholderText("Enter Spotify, Deezer, or Tidal Playlist URL")
        streaming_layout.addWidget(self.playlist_url_input)

        self.import_playlist_button = ModernButton("Import Playlist to Plex")
        self.import_playlist_button.clicked.connect(self.import_streaming_playlist)
        streaming_layout.addWidget(self.import_playlist_button)

        streaming_group.setLayout(streaming_layout)
        layout.addWidget(streaming_group)

        self.streaming_progress = QProgressBar()
        self.streaming_progress.setVisible(False)
        layout.addWidget(self.streaming_progress)

        layout.addStretch()
        self.content_stack.addWidget(page)

    # Enhanced playlist management methods
    def edit_playlist_item(self, item):
        """Handle double-click on playlist item - opens immediately, no blocking"""
        try:
            # Get the playlist name from the item text (remove track count)
            playlist_name = item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '').replace('❌ ', '')
            
            # Immediate feedback in status bar
            self.statusBar().showMessage(f"🎵 Opening '{playlist_name}' for editing...")
            
            # Open editor without any blocking
            self.edit_playlist_by_name(playlist_name)
            
        except Exception as e:
            logging.error(f"Error handling playlist double-click: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to open playlist editor: {str(e)}")
    
    def edit_selected_playlist(self):
        """Open playlist editor for selected playlist - completely non-blocking"""
        current_item = self.playlist_listwidget.currentItem()
        if not current_item:
            # Try to get checked items if no current selection
            selected_items = []
            for index in range(self.playlist_listwidget.count()):
                item = self.playlist_listwidget.item(index)
                if item.checkState() == Qt.Checked:
                    selected_items.append(item)
            
            if not selected_items:
                QMessageBox.warning(self, "No Selection", "Please select a playlist to edit.")
                return
            
            if len(selected_items) > 1:
                QMessageBox.warning(self, "Multiple Selection", "Please select only one playlist to edit.")
                return
            
            current_item = selected_items[0]
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Get the playlist name from the item text (remove track count and emojis)
        playlist_name = current_item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '').replace('❌ ', '')
        
        # Immediate feedback
        self.statusBar().showMessage(f"🎵 Opening '{playlist_name}' for editing...")
        
        # Open editor without blocking
        self.edit_playlist_by_name(playlist_name)
    
    def edit_playlist_by_name(self, playlist_name):
        """Edit playlist by name with on-demand loading"""
        try:
            # Find the playlist object
            playlist = None
            for plex_playlist, _ in self.playlist_data:
                if plex_playlist.title == playlist_name:
                    playlist = plex_playlist
                    break
            
            if not playlist:
                # Fallback: search in the original playlists list
                for plex_playlist in self.playlists:
                    if plex_playlist.title == playlist_name:
                        playlist = plex_playlist
                        break
            
            if playlist:
                # Load track count on-demand if not already loaded
                self.load_track_count_on_demand(playlist)
                
                try:
                    dialog = PlaylistEditorDialog(playlist, self.plex_server, self)
                    
                    if dialog.exec_() == QDialog.Accepted:
                        # Refresh playlist list after editing and invalidate cache for this playlist
                        playlist_id = str(playlist.ratingKey)  # Convert to string
                        self.playlist_cache.remove_playlist(playlist_id)
                        self.fetch_playlists()
                        
                except Exception as dialog_error:
                    logging.error(f"Error opening playlist editor: {str(dialog_error)}")
                    QMessageBox.critical(self, "Editor Error", f"Failed to open playlist editor: {str(dialog_error)}")
            else:
                QMessageBox.warning(self, "Playlist Not Found", f"Could not find playlist: {playlist_name}")
                
        except Exception as e:
            logging.error(f"Error editing playlist: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to edit playlist: {str(e)}")
    
    def show_loading(self, message="Loading...", detail="Please wait..."):
        """Show loading dialog"""
        if not self.loading_dialog:
            self.loading_dialog = LoadingDialog(self)
        
        self.loading_dialog.message_label.setText(message)
        self.loading_dialog.detail_label.setText(detail)
        self.loading_dialog.progress_bar.setValue(0)
        self.loading_dialog.show()
        QApplication.processEvents()  # Update UI immediately
    
    def hide_loading(self):
        """Hide loading dialog"""
        if self.loading_dialog:
            self.loading_dialog.hide()
    
    def show_playlist_merger(self):
        """Show playlist merger dialog"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        if not self.playlists:
            QMessageBox.warning(self, "No Playlists", "Please fetch playlists first.")
            return
        
        dialog = PlaylistMergerDialog(self.playlists, self.plex_server, self)
        if dialog.exec_() == QDialog.Accepted:
            self.fetch_playlists()  # Refresh playlist list
    
    # Sync management methods
    def toggle_auto_sync(self, state):
        """Toggle auto-sync functionality"""
        if state == Qt.Checked:
            interval = self.sync_interval_spinbox.value() * 60 * 1000  # Convert to milliseconds
            self.auto_sync_timer.start(interval)
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-sync enabled (interval: {self.sync_interval_spinbox.value()} minutes)")
        else:
            self.auto_sync_timer.stop()
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-sync disabled")
    
    def add_sync_config(self):
        """Add new sync configuration"""
        playlist_name = self.sync_playlist_combo.currentText()
        source_url = self.sync_source_input.text().strip()
        
        if not playlist_name or playlist_name == "Select playlist...":
            QMessageBox.warning(self, "Invalid Selection", "Please select a playlist.")
            return
        
        if not source_url:
            QMessageBox.warning(self, "Invalid Source", "Please enter a source URL or file path.")
            return
        
        # Add to sync configurations table
        row = self.sync_configs_table.rowCount()
        self.sync_configs_table.insertRow(row)
        
        # Create read-only items
        playlist_item = QTableWidgetItem(playlist_name)
        playlist_item.setFlags(playlist_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 0, playlist_item)
        
        source_item = QTableWidgetItem(source_url)
        source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 1, source_item)
        
        sync_item = QTableWidgetItem("Never")
        sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 2, sync_item)
        
        # Create better styled action buttons
        self.create_action_buttons_for_row(row)
        
        # Clear inputs
        self.sync_source_input.clear()
        
        self.save_sync_config()
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Added sync config for '{playlist_name}'")
    
    def create_action_buttons_for_row(self, row):
        """Create properly sized and visible action buttons for sync config row"""
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        actions_layout.setSpacing(5)
        
        # FIXED: Properly sized buttons with clear text labels
        sync_btn = QPushButton("Sync Now")
        sync_btn.setToolTip("Sync this playlist now")
        sync_btn.setFixedSize(80, 32)  # Fixed size for visibility
        sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        sync_btn.clicked.connect(lambda: self.sync_single_playlist(row))
        actions_layout.addWidget(sync_btn)
        
        # Delete button with proper sizing
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete this sync configuration")
        delete_btn.setFixedSize(80, 32)  # Fixed size for visibility
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_sync_config(row))
        actions_layout.addWidget(delete_btn)
        
        # FIXED: Set the widget properly and ensure table row height accommodates buttons
        self.sync_configs_table.setCellWidget(row, 3, actions_widget)
        self.sync_configs_table.setRowHeight(row, 40)  # Ensure row is tall enough
    
    def sync_single_playlist(self, row):
        """Sync a single playlist"""
        try:
            playlist_name = self.sync_configs_table.item(row, 0).text()
            source_url = self.sync_configs_table.item(row, 1).text()
            
            config = {
                playlist_name: {
                    'source_url': source_url,
                    'library_section': self.section_combo.currentData()
                }
            }
            
            self.start_sync(config)
        except Exception as e:
            logging.error(f"Error syncing single playlist: {str(e)}")
            QMessageBox.warning(self, "Sync Error", f"Failed to sync playlist: {str(e)}")
    
    def delete_sync_config(self, row):
        """Delete sync configuration"""
        try:
            playlist_name = self.sync_configs_table.item(row, 0).text()
            reply = QMessageBox.question(self, "Confirm Deletion", 
                                       f"Delete sync configuration for '{playlist_name}'?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.sync_configs_table.removeRow(row)
                self.save_sync_config()
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Deleted sync config for '{playlist_name}'")
                # FIXED: Refresh buttons after deletion to maintain correct row indices
                self.refresh_sync_table_buttons()
        except Exception as e:
            logging.error(f"Error deleting sync config: {str(e)}")
            QMessageBox.warning(self, "Delete Error", f"Failed to delete sync config: {str(e)}")
    
    def refresh_sync_table_buttons(self):
        """Refresh all sync table buttons after row operations"""
        for row in range(self.sync_configs_table.rowCount()):
            self.create_action_buttons_for_row(row)
    
    def load_sync_config(self):
        """Load sync configurations from file"""
        try:
            if os.path.exists(SYNC_CONFIG_FILE):
                with open(SYNC_CONFIG_FILE, 'r') as f:
                    sync_config = json.load(f)
                
                # Load sync configurations into table
                for playlist_name, config in sync_config.get('sync_playlists', {}).items():
                    row = self.sync_configs_table.rowCount()
                    self.sync_configs_table.insertRow(row)
                    
                    # Create read-only items
                    playlist_item = QTableWidgetItem(playlist_name)
                    playlist_item.setFlags(playlist_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 0, playlist_item)
                    
                    source_item = QTableWidgetItem(config.get('source_url', ''))
                    source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 1, source_item)
                    
                    sync_item = QTableWidgetItem(config.get('last_sync', 'Never'))
                    sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 2, sync_item)
                    
                    # Add styled action buttons
                    self.create_action_buttons_for_row(row)
                
                # Load auto-sync settings
                self.auto_sync_checkbox.setChecked(sync_config.get('auto_sync', False))
                self.sync_interval_spinbox.setValue(sync_config.get('sync_interval', 60))
                
        except Exception as e:
            logging.error(f"Error loading sync config: {str(e)}")
    
    def sync_selected_playlists(self):
        """Sync selected playlists from the table"""
        selected_configs = {}
        
        for row in range(self.sync_configs_table.rowCount()):
            if self.sync_configs_table.item(row, 0).isSelected():
                playlist_name = self.sync_configs_table.item(row, 0).text()
                source_url = self.sync_configs_table.item(row, 1).text()
                selected_configs[playlist_name] = {
                    'source_url': source_url,
                    'library_section': self.section_combo.currentData()
                }
        
        if not selected_configs:
            QMessageBox.warning(self, "No Selection", "Please select sync configurations to sync.")
            return
        
        self.start_sync(selected_configs)
    
    def sync_all_playlists(self):
        """Sync all configured playlists"""
        all_configs = {}
        
        for row in range(self.sync_configs_table.rowCount()):
            playlist_name = self.sync_configs_table.item(row, 0).text()
            source_url = self.sync_configs_table.item(row, 1).text()
            all_configs[playlist_name] = {
                'source_url': source_url,
                'library_section': self.section_combo.currentData()
            }
        
        if not all_configs:
            QMessageBox.warning(self, "No Configurations", "No sync configurations found.")
            return
        
        self.start_sync(all_configs)
    
    def start_sync(self, sync_configs):
        """Start sync process"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        self.sync_progress_group.setVisible(True)
        self.sync_status_label.setText("Initializing sync...")
        self.sync_progress_bar.setValue(0)
        
        self.sync_thread = SyncThread(sync_configs, self.plex_server, self)
        self.sync_thread.progress_update.connect(self.update_sync_progress)
        self.sync_thread.sync_complete.connect(self.sync_playlist_complete)
        self.sync_thread.error.connect(self.sync_error)
        self.sync_thread.finished.connect(self.sync_finished)
        self.sync_thread.start()
    
    def update_sync_progress(self, message, percentage):
        """Update sync progress"""
        self.sync_status_label.setText(message)
        self.sync_progress_bar.setValue(percentage)
    
    def sync_playlist_complete(self, playlist_name, added_tracks, total_tracks):
        """Handle individual playlist sync completion"""
        message = f"[{datetime.now().strftime('%H:%M:%S')}] {playlist_name}: Added {added_tracks} new tracks"
        self.sync_log.append(message)
        
        # Update last sync time in table
        for row in range(self.sync_configs_table.rowCount()):
            if self.sync_configs_table.item(row, 0).text() == playlist_name:
                sync_time_item = QTableWidgetItem(datetime.now().strftime('%Y-%m-%d %H:%M'))
                sync_time_item.setFlags(sync_time_item.flags() & ~Qt.ItemIsEditable)
                self.sync_configs_table.setItem(row, 2, sync_time_item)
                break
    
    def sync_error(self, error_message):
        """Handle sync error"""
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_message}")
        QMessageBox.warning(self, "Sync Error", error_message)
    
    def sync_finished(self):
        """Handle sync completion"""
        self.sync_progress_group.setVisible(False)
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sync completed")
        self.statusBar().showMessage("Sync completed")
    
    def stop_sync(self):
        """Stop sync process"""
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.stop()
            self.sync_thread.wait()
            self.sync_progress_group.setVisible(False)
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sync stopped by user")
    
    def perform_auto_sync(self):
        """Perform automatic sync"""
        if self.auto_sync_checkbox.isChecked():
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting auto-sync...")
            self.sync_all_playlists()
    
    def save_sync_config(self):
        """Save sync configurations to file"""
        try:
            configs = {}
            for row in range(self.sync_configs_table.rowCount()):
                playlist_name = self.sync_configs_table.item(row, 0).text()
                source_url = self.sync_configs_table.item(row, 1).text()
                last_sync = self.sync_configs_table.item(row, 2).text()
                
                configs[playlist_name] = {
                    'source_url': source_url,
                    'last_sync': last_sync,
                    'library_section': self.section_combo.currentData()
                }
            
            sync_config = {
                'sync_playlists': configs,
                'auto_sync': self.auto_sync_checkbox.isChecked(),
                'sync_interval': self.sync_interval_spinbox.value()
            }
            
            with open(SYNC_CONFIG_FILE, 'w') as f:
                json.dump(sync_config, f, indent=4)
                
        except Exception as e:
            logging.error(f"Error saving sync config: {str(e)}")

    # Tools and utilities methods
    def find_duplicate_tracks(self):
        """Find duplicate tracks across all playlists using background thread"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Prevent multiple simultaneous scans
        if hasattr(self, 'duplicates_thread') and self.duplicates_thread.isRunning():
            QMessageBox.information(self, "Scan in Progress", "Duplicate scan is already running. Please wait...")
            return
        
        # Show loading dialog
        self.show_loading("Scanning for duplicates...", "Initializing scan...")
        
        # Disable the button to prevent multiple clicks
        self.find_duplicates_btn.setEnabled(False)
        self.find_duplicates_btn.setText("Scanning...")
        
        # Start background scan
        self.duplicates_thread = FindDuplicatesThread(self.plex_server, self)
        self.duplicates_thread.progress_update.connect(self.update_duplicates_progress)
        self.duplicates_thread.duplicates_found.connect(self.on_duplicates_found)
        self.duplicates_thread.error.connect(self.on_duplicates_error)
        self.duplicates_thread.finished.connect(self.on_duplicates_finished)
        self.duplicates_thread.start()
    
    def sanitize_filename(self, filename, max_length=255):
        """
        Sanitize filename by replacing invalid characters with safe alternatives
        """
        import re
        
        # Dictionary of replacements for common invalid characters
        replacements = {
            '/': '_',           # Forward slash
            '\\': '_',          # Backslash  
            ':': ' -',          # Colon
            '*': '',            # Asterisk
            '?': '',            # Question mark
            '"': "'",           # Double quote to single quote
            '<': '(',           # Less than
            '>': ')',           # Greater than
            '|': '-',           # Pipe
            '\n': ' ',          # Newline
            '\r': ' ',          # Carriage return
            '\t': ' ',          # Tab
        }
        
        # Apply character replacements
        sanitized = filename
        for invalid_char, replacement in replacements.items():
            sanitized = sanitized.replace(invalid_char, replacement)
        
        # Remove any remaining control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # Clean up multiple spaces and trim
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Handle Windows reserved names
        windows_reserved = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                           'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                           'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = sanitized.rsplit('.', 1)[0] if '.' in sanitized else sanitized
        if name_without_ext.upper() in windows_reserved:
            sanitized = f"Playlist_{sanitized}"
        
        # Ensure filename isn't empty
        if not sanitized or sanitized.isspace():
            sanitized = "Unnamed_Playlist"
        
        # Truncate if too long (leave room for .m3u extension)
        if len(sanitized) > max_length - 4:
            sanitized = sanitized[:max_length - 4].rstrip()
        
        # Remove trailing periods (Windows issue)
        sanitized = sanitized.rstrip('.')
        
        return sanitized

    def update_duplicates_progress(self, message, percentage):
        """Update duplicate scan progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(f"{message} ({percentage}%)")
    
    def on_duplicates_found(self, duplicate_tracks):
        """Handle duplicate tracks found"""
        self.hide_loading()
        
        if duplicate_tracks:
            # Display duplicates in a dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Tracks Found")
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f"Found {len(duplicate_tracks)} duplicate tracks:"))
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            for signature, occurrences in duplicate_tracks:
                text_edit.append(f"\nTrack: {signature.replace('_', ' - ')}")
                for playlist_name, track in occurrences:
                    text_edit.append(f"  - In playlist: {playlist_name}")
            
            layout.addWidget(text_edit)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec_()
            
            self.statusBar().showMessage(f"Found {len(duplicate_tracks)} duplicate tracks")
        else:
            QMessageBox.information(self, "No Duplicates", "No duplicate tracks found across playlists.")
            self.statusBar().showMessage("No duplicate tracks found")
    
    def on_duplicates_error(self, error_message):
        """Handle duplicate scan error"""
        self.hide_loading()
        logging.error(f"Duplicate scan error: {error_message}")
        QMessageBox.critical(self, "Scan Error", f"Error scanning for duplicates: {error_message}")
        self.statusBar().showMessage("Duplicate scan failed")
    
    def on_duplicates_finished(self):
        """Handle duplicate scan completion"""
        # Re-enable the button
        self.find_duplicates_btn.setEnabled(True)
        self.find_duplicates_btn.setText("Find Duplicate Tracks")
    
    def backup_all_playlists(self):
        """FIXED: Backup all playlists using background thread to prevent UI freezing"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if not backup_dir:
            return
        
        # Prevent multiple simultaneous backups
        if self.backup_thread and self.backup_thread.isRunning():
            QMessageBox.information(self, "Backup in Progress", "A backup is already in progress. Please wait...")
            return
        
        # Show loading dialog
        self.show_loading("Starting backup...", "Preparing playlist backup...")
        
        # Disable backup button to prevent multiple clicks
        self.backup_playlists_btn.setEnabled(False)
        self.backup_playlists_btn.setText("Backing up...")
        
        # Start background backup
        self.backup_thread = BackupThread(self.plex_server, backup_dir, self)
        self.backup_thread.progress_update.connect(self.update_backup_progress)
        self.backup_thread.backup_complete.connect(self.on_backup_complete)
        self.backup_thread.error.connect(self.on_backup_error)
        self.backup_thread.finished.connect(self.on_backup_finished)
        self.backup_thread.start()
    
    def update_backup_progress(self, message, percentage):
        """Update backup progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(f"{message} ({percentage}%)")
    
    def on_backup_complete(self, backed_up_count, backup_folder):
        """Handle backup completion"""
        self.hide_loading()
        QMessageBox.information(self, "Backup Complete", 
                              f"Successfully backed up {backed_up_count} playlists to:\n{backup_folder}")
        self.statusBar().showMessage(f"Backup completed: {backed_up_count} playlists")
    
    def on_backup_error(self, error_message):
        """Handle backup error"""
        self.hide_loading()
        logging.error(f"Backup error: {error_message}")
        QMessageBox.critical(self, "Backup Error", f"Backup failed: {error_message}")
        self.statusBar().showMessage("Backup failed")
    
    def on_backup_finished(self):
        """Handle backup thread finished (success or error)"""
        # Re-enable backup button
        self.backup_playlists_btn.setEnabled(True)
        self.backup_playlists_btn.setText("Backup All Playlists")
    
    def restore_playlists(self):
        """Restore playlists from backup directory"""
        backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if not backup_dir:
            return
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        try:
            m3u_files = [f for f in os.listdir(backup_dir) if f.endswith('.m3u')]
            
            if not m3u_files:
                QMessageBox.warning(self, "No Files", "No M3U files found in the selected directory.")
                return
            
            reply = QMessageBox.question(self, "Confirm Restore", 
                                       f"Found {len(m3u_files)} playlist files. Restore all?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                restored = 0
                for m3u_file in m3u_files:
                    try:
                        file_path = os.path.join(backup_dir, m3u_file)
                        self.upload_playlist(file_path)
                        restored += 1
                    except Exception as file_error:
                        logging.error(f"Error restoring {m3u_file}: {str(file_error)}")
                        continue
                
                QMessageBox.information(self, "Restore Complete", 
                                      f"Successfully restored {restored} playlists.")
                self.fetch_playlists()  # Refresh playlist list
                
        except Exception as e:
            logging.error(f"Error during restore: {str(e)}")
            QMessageBox.critical(self, "Restore Error", f"Failed to restore playlists: {str(e)}")
    
    def update_playlist_statistics(self):
        """Update and display playlist statistics"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        try:
            playlists = self.plex_server.playlists()
            
            total_playlists = len(playlists)
            total_tracks = 0
            playlist_sizes = []
            largest_playlist = None
            smallest_playlist = None
            
            for playlist in playlists:
                try:
                    track_count = len(list(playlist.items()))
                    total_tracks += track_count
                    playlist_sizes.append(track_count)
                    
                    if largest_playlist is None or track_count > len(list(largest_playlist.items())):
                        largest_playlist = playlist
                    
                    if smallest_playlist is None or track_count < len(list(smallest_playlist.items())):
                        smallest_playlist = playlist
                        
                except Exception as playlist_error:
                    logging.warning(f"Error analyzing playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            if playlist_sizes:
                avg_tracks = sum(playlist_sizes) / len(playlist_sizes)
                
                stats_text = f"""
Playlist Statistics:
━━━━━━━━━━━━━━━━━━━━━━

📊 Total Playlists: {total_playlists}
🎵 Total Tracks: {total_tracks:,}
📈 Average Tracks per Playlist: {avg_tracks:.1f}

📍 Largest Playlist: {largest_playlist.title if largest_playlist else 'N/A'} ({len(list(largest_playlist.items())) if largest_playlist else 0} tracks)
📍 Smallest Playlist: {smallest_playlist.title if smallest_playlist else 'N/A'} ({len(list(smallest_playlist.items())) if smallest_playlist else 0} tracks)

🔢 Distribution:
  • Empty playlists: {sum(1 for size in playlist_sizes if size == 0)}
  • Small (1-10 tracks): {sum(1 for size in playlist_sizes if 1 <= size <= 10)}
  • Medium (11-50 tracks): {sum(1 for size in playlist_sizes if 11 <= size <= 50)}
  • Large (51-100 tracks): {sum(1 for size in playlist_sizes if 51 <= size <= 100)}
  • Very Large (100+ tracks): {sum(1 for size in playlist_sizes if size > 100)}

Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                self.stats_text.setText(stats_text)
            else:
                self.stats_text.setText("No playlist data available.")
                
        except Exception as e:
            logging.error(f"Error updating statistics: {str(e)}")
            QMessageBox.critical(self, "Statistics Error", f"Failed to update statistics: {str(e)}")
    
    def analyze_music_library(self):
        """Analyze the music library"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        section_id = self.section_combo.currentData()
        if not section_id:
            QMessageBox.warning(self, "No Library Selected", "Please select a music library section.")
            return
        
        try:
            library_section = self.plex_server.library.sectionByID(section_id)
            
            # Get artists, albums, and tracks
            artists = library_section.searchArtists()
            albums = library_section.searchAlbums()
            tracks = library_section.searchTracks()
            
            # Calculate total duration
            total_duration = 0
            for track in tracks[:1000]:  # Limit to first 1000 tracks for performance
                if hasattr(track, 'duration') and track.duration:
                    total_duration += track.duration
            
            # Estimate total duration based on sample
            if len(tracks) > 1000:
                avg_duration = total_duration / 1000
                estimated_total = avg_duration * len(tracks)
            else:
                estimated_total = total_duration
            
            # Convert milliseconds to hours
            total_hours = estimated_total / (1000 * 60 * 60)
            
            # Get top genres (if available)
            genres = set()
            for track in tracks[:500]:  # Sample for genres
                if hasattr(track, 'genres'):
                    for genre in track.genres:
                        genres.add(genre.tag)
            
            analysis_text = f"""
Music Library Analysis:
━━━━━━━━━━━━━━━━━━━━━━

📚 Library: {library_section.title}
🎤 Artists: {len(artists):,}
💿 Albums: {len(albums):,}
🎵 Tracks: {len(tracks):,}

⏱️ Total Duration: ~{total_hours:.1f} hours
📊 Average Album Size: {len(tracks) / len(albums) if albums else 0:.1f} tracks

🎭 Unique Genres: {len(genres)}
Top Genres: {', '.join(list(genres)[:10]) if genres else 'Not available'}

📈 Collection Insights:
  • Tracks per Artist: {len(tracks) / len(artists) if artists else 0:.1f}
  • Albums per Artist: {len(albums) / len(artists) if artists else 0:.1f}
  • Your library would take ~{total_hours / 24:.1f} days to play through

🔍 Quality Metrics:
  • {"Well-organized" if len(albums) / len(artists) > 2 else "Could use more albums per artist"}
  • {"Rich collection" if len(tracks) > 1000 else "Growing collection"}

Last Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            self.analysis_text.setText(analysis_text)
            
        except Exception as e:
            logging.error(f"Error analyzing library: {str(e)}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze library: {str(e)}")

    def fetch_playlists(self):
        """Fetch playlists with on-demand track count loading"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        # Prevent multiple simultaneous fetches
        if self.fetch_thread and self.fetch_thread.isRunning():
            QMessageBox.information(self, "Already Loading", "Playlists are already being fetched. Please wait...")
            return

        try:
            # Show loading dialog
            if not self.loading_dialog:
                self.loading_dialog = LoadingDialog(self)
            
            self.loading_dialog.update_progress("Initializing...", 0)
            self.loading_dialog.show()
            
            # Disable fetch button to prevent multiple clicks
            self.fetch_playlists_button.setEnabled(False)
            self.fetch_playlists_button.setText("Loading...")
            
            # Start background fetch (now much faster - no track counts!)
            self.fetch_thread = FetchPlaylistsThread(self.plex_server, self.playlist_cache, self)
            self.fetch_thread.progress_update.connect(self.update_fetch_progress)
            self.fetch_thread.playlists_fetched.connect(self.on_playlists_fetched)
            self.fetch_thread.error.connect(self.on_fetch_error)
            self.fetch_thread.finished.connect(self.on_fetch_finished)
            self.fetch_thread.start()
            
        except Exception as e:
            self.on_fetch_error(f"Failed to start playlist fetch: {str(e)}")

    def update_fetch_progress(self, message, percentage):
        """Update fetch progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        
        # Also update status bar
        self.statusBar().showMessage(f"{message} ({percentage}%)")

    def on_playlists_fetched(self, playlist_data):
        """Handle successful playlist fetch"""
        try:
            self.playlist_data = playlist_data
            self.playlists = [playlist for playlist, _ in playlist_data]
            self.update_playlist_listwidget()
            self.populate_sync_playlist_combo()  # Update sync combo too
            
            total_playlists = len(self.playlists)
            cached_count = sum(1 for _, count in playlist_data if count is not None)
            
            status_msg = f"Loaded {total_playlists} playlists ({cached_count} with cached track counts)"
            self.statusBar().showMessage(status_msg)
            
            # Update cache info
            self.cache_info_label.setText(f"💡 {total_playlists} playlists loaded. {cached_count} have cached track counts. Click 'Refresh All Counts' to load missing counts.")
            
        except Exception as e:
            logging.error(f"Error processing fetched playlists: {str(e)}")
            self.statusBar().showMessage(f"Error processing playlists: {str(e)}")

    def on_fetch_error(self, error_message):
        """Handle fetch error"""
        logging.error(f"Playlist fetch error: {error_message}")
        QMessageBox.critical(self, "Fetch Error", f"Error fetching playlists:\n{error_message}")
        self.statusBar().showMessage("Failed to fetch playlists.")

    def on_fetch_finished(self):
        """Handle fetch completion (success or error)"""
        # Hide loading dialog
        if self.loading_dialog:
            self.loading_dialog.hide()
        
        # Re-enable fetch button
        self.fetch_playlists_button.setEnabled(True)
        self.fetch_playlists_button.setText("Fetch Playlists")

    def update_playlist_listwidget(self):
        """Update playlist list widget with on-demand track count loading"""
        self.playlist_listwidget.clear()
        
        for playlist, track_count in self.playlist_data:
            try:
                # Display playlist with track count (or "..." if not cached)
                if track_count is not None:
                    item_text = f"{playlist.title} ({track_count} tracks)"
                else:
                    item_text = f"{playlist.title} (click to load tracks...)"
                
                item = QListWidgetItem(item_text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                
                # Store playlist object for easy access
                item.setData(Qt.UserRole, playlist)
                
                self.playlist_listwidget.addItem(item)
                
            except Exception as e:
                logging.warning(f"Error adding playlist {playlist.title} to list: {str(e)}")
                # Fallback: add without track count
                item = QListWidgetItem(playlist.title)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, playlist)
                self.playlist_listwidget.addItem(item)

    def load_track_count_on_demand(self, playlist):
        """Load track count for a specific playlist on-demand"""
        playlist_id = str(playlist.ratingKey)  # Convert to string
        
        if playlist_id in self.track_count_threads:
            return  # Already loading
        
        # Check if already cached
        cached_count = self.playlist_cache.get_track_count(playlist_id)
        if cached_count is not None:
            self.update_playlist_item_count(playlist_id, cached_count)
            return
        
        # Start background loading
        thread = LoadTrackCountThread(playlist, self.playlist_cache, self)
        thread.track_count_loaded.connect(self.on_track_count_loaded)
        thread.error.connect(self.on_track_count_error)
        thread.finished.connect(lambda: self.track_count_threads.pop(playlist_id, None))
        
        self.track_count_threads[playlist_id] = thread
        thread.start()
        
        # Update UI to show loading
        self.update_playlist_item_loading(playlist_id)

    def on_track_count_loaded(self, playlist_id, track_count):
        """Handle track count loaded event"""
        self.update_playlist_item_count(playlist_id, track_count)
        
        # Update the playlist_data cache in memory too
        for i, (playlist, _) in enumerate(self.playlist_data):
            if str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                self.playlist_data[i] = (playlist, track_count)
                break

    def on_track_count_error(self, playlist_id, error_message):
        """Handle track count loading error"""
        logging.error(f"Error loading track count for playlist {playlist_id}: {error_message}")
        self.update_playlist_item_error(playlist_id)

    def update_playlist_item_count(self, playlist_id, track_count):
        """Update playlist item with track count"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} ({track_count} tracks)")
                break

    def update_playlist_item_loading(self, playlist_id):
        """Update playlist item to show loading state"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} (loading...)")
                break

    def update_playlist_item_error(self, playlist_id):
        """Update playlist item to show error state"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} (error loading tracks)")
                break

    def refresh_all_track_counts(self):
        """FIXED: Refresh track counts for all playlists using optimized batch processing"""
        if not self.playlists:
            QMessageBox.warning(self, "No Playlists", "Please fetch playlists first.")
            return
        
        # Prevent multiple simultaneous refresh operations
        if self.batch_track_count_thread and self.batch_track_count_thread.isRunning():
            QMessageBox.information(self, "Already Loading", "Track counts are already being refreshed. Please wait...")
            return
        
        reply = QMessageBox.question(self, "Refresh All Track Counts", 
                                   f"This will load track counts for all {len(self.playlists)} playlists. This may take a while. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Show loading dialog
            self.show_loading("Loading track counts...", "Initializing batch processing...")
            
            # Disable refresh button
            self.refresh_all_button.setEnabled(False)
            self.refresh_all_button.setText("Loading...")
            
            # Start batch track count loading
            self.batch_track_count_thread = BatchTrackCountThread(self.playlist_data, self.playlist_cache, max_concurrent=3, parent=self)
            self.batch_track_count_thread.progress_update.connect(self.update_batch_progress)
            self.batch_track_count_thread.all_complete.connect(self.on_batch_complete)
            self.batch_track_count_thread.error.connect(self.on_batch_error)
            self.batch_track_count_thread.finished.connect(self.on_batch_finished)
            self.batch_track_count_thread.start()
    
    def update_batch_progress(self, message, percentage):
        """Update batch track count loading progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(message)
    
    def on_batch_complete(self):
        """Handle batch track count loading completion"""
        self.hide_loading()
        # Refresh the playlist display to show all loaded counts
        self.fetch_playlists()
        QMessageBox.information(self, "Refresh Complete", "All track counts have been loaded and cached.")
    
    def on_batch_error(self, error_message):
        """Handle batch track count loading error"""
        self.hide_loading()
        logging.error(f"Batch track count error: {error_message}")
        QMessageBox.warning(self, "Loading Error", f"Some track counts failed to load: {error_message}")
    
    def on_batch_finished(self):
        """Handle batch track count loading finished"""
        # Re-enable refresh button
        self.refresh_all_button.setEnabled(True)
        self.refresh_all_button.setText("Refresh All Counts")

    def clear_playlist_cache(self):
        """Clear the playlist cache"""
        reply = QMessageBox.question(self, "Clear Cache", 
                                   "This will clear all cached playlist data. Track counts will need to be reloaded. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.playlist_cache.clear_cache()
            QMessageBox.information(self, "Cache Cleared", "Playlist cache has been cleared.")
            
            # Refresh the display
            if self.playlists:
                # Reset playlist_data to remove cached counts
                self.playlist_data = [(playlist, None) for playlist, _ in self.playlist_data]
                self.update_playlist_listwidget()
                self.cache_info_label.setText("💡 Cache cleared. Track counts will load on-demand.")

    def connect_to_plex(self):
        
        self.section_combo.clear()
        self.section_combo.addItem("Library Section")
        self.section_combo.setCurrentIndex(0)
        
        try:
            username = self.plex_username_input.text()
            password = self.plex_password_input.text()
            server_ip = self.server_ip_input.text()
            server_port = self.server_port_input.text()
            token = self.token_input.text()
        
            base_url = f"http://{server_ip}:{server_port}"
        
            if token:
                # Use the provided token to connect directly
                self.plex_server = PlexServer(base_url, token)
            else:
                # Authenticate with username and password to get the token
                account = MyPlexAccount(username, password)
                token = account.authenticationToken
                self.token_input.setText(token)
                self.plex_server = PlexServer(base_url, token)
        
            self.populate_library_sections()
            self.populate_sync_playlist_combo()
            self.statusBar().showMessage("Successfully connected to Plex.")
            self.save_config()
        except Exception as e:
            logging.error(f"Error connecting to Plex: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Connection Error", f"Error connecting to Plex: {str(e)}")
            
    def populate_library_sections(self):
        try:
            self.section_combo.clear()
            music_sections = []
            for section in self.plex_server.library.sections():
                if section.type == 'artist':  # Assuming 'artist' type for music
                    music_sections.append(section)
                    self.section_combo.addItem(section.title, section.key)
            
            if music_sections:
                # Automatically select the first music section
                self.section_combo.setCurrentIndex(0)
                self.last_section_id = music_sections[0].key
                logging.info(f"Auto-selected music library: {music_sections[0].title}")
            elif self.section_combo.count() == 0:
                QMessageBox.warning(self, "No Music Sections", "No music library sections found in your Plex server.")
        except Exception as e:
            logging.error(f"Error populating library sections: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Section Error", f"Error loading library sections: {str(e)}")

    def populate_sync_playlist_combo(self):
        """Populate the sync playlist combo box"""
        try:
            self.sync_playlist_combo.clear()
            self.sync_playlist_combo.addItem("Select playlist...")
            
            for playlist in self.plex_server.playlists():
                self.sync_playlist_combo.addItem(playlist.title, playlist)
                
        except Exception as e:
            logging.error(f"Error populating sync playlist combo: {str(e)}")

    def select_all_playlists(self, state):
        for index in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(index)
            item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)

    def get_selected_playlists(self):
        selected_playlists = []
        for index in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(index)
            if item.checkState() == Qt.Checked or item.isSelected():
                selected_playlists.append(item)
        return selected_playlists

    def delete_selected_playlist(self):
        selected_items = self.get_selected_playlists()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select playlists to delete.")
            return

        reply = QMessageBox.question(self, 'Confirm Deletion', 
                                     f"Are you sure you want to delete {len(selected_items)} playlist(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for item in selected_items:
                # Get playlist object from item data
                playlist = item.data(Qt.UserRole)
                if playlist:
                    try:
                        playlist.delete()
                        deleted_count += 1
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Error", f"Error deleting {playlist.title}: {str(e)}")
                else:
                    # Fallback: try to find by name
                    playlist_name = item.text().split(' (')[0]
                    playlist = next((p for p in self.playlists if p.title == playlist_name), None)
                    if playlist:
                        try:
                            playlist.delete()
                            deleted_count += 1
                        except Exception as e:
                            QMessageBox.warning(self, "Deletion Error", f"Error deleting {playlist.title}: {str(e)}")
            
            if deleted_count > 0:
                self.fetch_playlists()
                self.statusBar().showMessage(f"Deleted {deleted_count} playlist(s).")

    def import_playlist(self):
        m3u_path = self.playlist_input.text()
        if os.path.isdir(m3u_path):  # If it's a directory, perform bulk upload
            imported_playlists = []
            for filename in os.listdir(m3u_path):
                if filename.endswith('.m3u') or filename.endswith('.m3u8'):
                    full_path = os.path.join(m3u_path, filename)
                    self.upload_playlist(full_path)
                    imported_playlists.append(os.path.basename(full_path))
            self.statusBar().showMessage("Imported: " + ", ".join(imported_playlists))
        else:  # Single file upload
            self.upload_playlist(m3u_path)

    def upload_playlist(self, path):
        # Enhanced upload with conflict detection
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"File not found: {path}")
            return
            
        # Get playlist name from file
        playlist_name = os.path.splitext(os.path.basename(path))[0]
        
        # Check if playlist already exists
        existing_playlist = None
        try:
            for playlist in self.plex_server.playlists():
                if playlist.title.lower() == playlist_name.lower():
                    existing_playlist = playlist
                    break
        except:
            pass  # If we can't check, proceed with upload
        
        if existing_playlist:
            # Show conflict resolution dialog
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Playlist Conflict")
            dialog.setText(f"A playlist named '{playlist_name}' already exists.")
            dialog.setInformativeText("What would you like to do?")
            
            replace_btn = dialog.addButton("Replace", QMessageBox.DestructiveRole)
            merge_btn = dialog.addButton("Merge", QMessageBox.AcceptRole)
            rename_btn = dialog.addButton("Rename New", QMessageBox.AcceptRole)
            cancel_btn = dialog.addButton("Cancel", QMessageBox.RejectRole)
            
            dialog.exec_()
            
            if dialog.clickedButton() == cancel_btn:
                return
            elif dialog.clickedButton() == replace_btn:
                # Delete existing playlist
                existing_playlist.delete()
                # Proceed with normal upload
                self._perform_upload(path)
            elif dialog.clickedButton() == merge_btn:
                # Merge with existing playlist
                self._merge_with_existing(path, existing_playlist)
                return
            elif dialog.clickedButton() == rename_btn:
                # Rename and upload
                new_name, ok = QInputDialog.getText(self, "Rename Playlist", 
                                                  "Enter new name:", text=f"{playlist_name}_new")
                if ok and new_name:
                    self._perform_upload(path, new_name)
                return
        else:
            # No conflict, proceed with normal upload
            self._perform_upload(path)
    
    def _perform_upload(self, path, custom_name=None):
        """Perform the actual playlist upload"""
        try:
            # Rename .m3u8 to .m3u if necessary
            if path.endswith('.m3u8'):
                new_path = path.rsplit('.', 1)[0] + '.m3u'
                os.rename(path, new_path)
                path = new_path
        
            plex_server = self.server_ip_input.text()
            plex_port = self.server_port_input.text()
            library_section_id = self.section_combo.currentData()
            plex_token = self.token_input.text()
        
            if not library_section_id:
                self.statusBar().showMessage("Please select a library section before importing.")
                return
        
            url = f"http://{plex_server}:{plex_port}/playlists/upload"
            params = {'sectionID': library_section_id, 'path': path, 'X-Plex-Token': plex_token}
            
            if custom_name:
                # If custom name provided, we need to handle it differently
                # For now, just proceed and rename after upload
                pass
            
            response = requests.post(url, params=params)
            response.raise_for_status()
            
            filename = custom_name or os.path.basename(path)
            self.statusBar().showMessage(f"{filename} imported successfully.")
            
        except requests.RequestException as e:
            error_message = f"Failed to import {os.path.basename(path)}. Error: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
        
        # Refresh the playlist list after import
        self.fetch_playlists()
    
    def _merge_with_existing(self, file_path, existing_playlist):
        """Merge M3U file tracks with existing playlist"""
        try:
            # Read tracks from M3U file
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.readlines()
            
            new_tracks = [line.strip() for line in content if line.strip() and not line.startswith('#')]
            
            if not new_tracks:
                QMessageBox.warning(self, "Empty Playlist", "No tracks found in the M3U file.")
                return
            
            # Get library section
            library_section_id = self.section_combo.currentData()
            library_section = self.plex_server.library.sectionByID(library_section_id)
            
            # Get existing tracks in playlist
            existing_tracks = set()
            for track in existing_playlist.items():
                signature = f"{track.title}_{track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else '')}"
                existing_tracks.add(signature.lower())
            
            # Find new tracks to add
            tracks_to_add = []
            for track_info in new_tracks:
                track_signature = track_info.lower()
                if track_signature not in existing_tracks:
                    # Try to find track in Plex library
                    plex_track = self.find_best_match_for_merge(library_section, track_info)
                    if plex_track:
                        tracks_to_add.append(plex_track)
            
            if tracks_to_add:
                existing_playlist.addItems(tracks_to_add)
                QMessageBox.information(self, "Merge Complete", 
                                      f"Added {len(tracks_to_add)} new tracks to '{existing_playlist.title}'.")
            else:
                QMessageBox.information(self, "No New Tracks", 
                                      "No new tracks found to add to the existing playlist.")
            
            self.fetch_playlists()  # Refresh playlist list
            
        except Exception as e:
            logging.error(f"Error merging playlist: {str(e)}")
            QMessageBox.critical(self, "Merge Error", f"Failed to merge playlist: {str(e)}")
    
    def find_best_match_for_merge(self, library_section, track):
        """Find best match for a track during merge operation"""
        try:
            title, artist = self.parse_track_info(track)
            all_tracks = library_section.searchTracks(title=title)
            
            best_match = None
            best_score = 0
            
            for plex_track in all_tracks:
                plex_title = plex_track.title if plex_track.title else ""
                title_score = fuzz.token_set_ratio(title.lower(), plex_title.lower())
                
                artist_score = 0
                if artist and plex_track.originalTitle:
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.originalTitle.lower())
                elif hasattr(plex_track, 'artist') and plex_track.artist():
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.artist().title.lower())
                
                combined_score = (title_score * 0.7) + (artist_score * 0.3)
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_match = plex_track
            
            if best_score >= 70:
                return best_match
            else:
                return None
                
        except Exception as e:
            logging.error(f"Error finding match for track: {str(e)}")
            return None

    def parse_track_info(self, track):
        """Parse track info into title and artist"""
        parts = track.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        else:
            return track.strip(), ''

    def export_selected_playlists(self):
        selected_items = [self.playlist_listwidget.item(i) for i in range(self.playlist_listwidget.count()) 
                          if self.playlist_listwidget.item(i).checkState() == Qt.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select playlists to export.")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return

        # Get playlist objects from selected items
        playlists_to_export = []
        for item in selected_items:
            playlist = item.data(Qt.UserRole)
            if playlist:
                playlists_to_export.append(playlist)
            else:
                # Fallback: find by name
                playlist_name = item.text().split(' (')[0]
                playlist = next((p for p in self.playlists if p.title == playlist_name), None)
                if playlist:
                    playlists_to_export.append(playlist)

        if not playlists_to_export:
            QMessageBox.warning(self, "No Playlists", "No valid playlists found to export.")
            return

        # Show loading dialog and start background export
        self.show_loading("Exporting playlists...", f"0 of {len(playlists_to_export)} exported")
        
        # Start export thread
        self.export_thread = ExportThread(playlists_to_export, export_dir, self)
        self.export_thread.progress_update.connect(self.update_export_progress)
        self.export_thread.export_complete.connect(self.on_export_complete)
        self.export_thread.error.connect(self.on_export_error)
        self.export_thread.start()

    def update_export_progress(self, message, percentage):
        """Update export progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)

    def on_export_complete(self, exported_count):
        """Handle export completion"""
        self.hide_loading()
        self.statusBar().showMessage(f"Successfully exported {exported_count} playlist(s).")
        QMessageBox.information(self, "Export Complete", f"Successfully exported {exported_count} playlist(s).")

    def on_export_error(self, error_message):
        """Handle export error"""
        self.hide_loading()
        logging.error(f"Export error: {error_message}")
        QMessageBox.critical(self, "Export Error", f"Export failed: {error_message}")

    def export_playlist(self, playlist, export_dir):
        safe_name = self.sanitize_filename(playlist.title)
        filename = f"{safe_name}.m3u"
        filepath = os.path.join(export_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as file:
            file.write("#EXTM3U\n")
            file.write(f"# Exported from Plex on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for item in playlist.items():
                try:
                    # Use the actual file path from Plex, not just track info
                    for part in item.iterParts():
                        if hasattr(part, 'file') and part.file:
                            # Write the full file path as it was before
                            file.write(f"{part.file}\n")
                            break
                    else:
                        # Fallback: if no file path available, use track info
                        artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                        file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                        file.write(f"{item.title} - {artist}\n")
                except Exception as e:
                    logging.warning(f"Error exporting track: {str(e)}")
                    continue

    def browse_files(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', "Playlist files (*.m3u *.m3u8)")
        if path:
            self.playlist_input.setText(path)

    def import_streaming_playlist(self):
        playlist_url = self.playlist_url_input.text()
        if not playlist_url:
            QMessageBox.warning(self, "Missing Information", "Please enter a Spotify, Deezer, or Tidal playlist URL.")
            return

        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        self.start_playlist_conversion(playlist_url)

    def start_playlist_conversion(self, playlist_url):
        self.converter_thread = PlaylistConverterThread(
            playlist_url, 
            self.plex_server, 
            self.section_combo.currentData()
        )
        self.converter_thread.progress_update.connect(self.update_streaming_progress)
        self.converter_thread.finished.connect(self.conversion_finished)
        self.converter_thread.error.connect(self.conversion_error)

        self.streaming_progress.setVisible(True)
        self.streaming_progress.setValue(0)
        self.converter_thread.start()

    def update_streaming_progress(self, value):
        self.streaming_progress.setValue(value)

    def conversion_finished(self):
        self.streaming_progress.setVisible(False)
        self.statusBar().showMessage("Playlist conversion completed successfully.")
        self.fetch_playlists()

    def conversion_error(self, error_msg):
        self.streaming_progress.setVisible(False)
        logging.error(f"Conversion error: {error_msg}")
        QMessageBox.warning(self, "Conversion Error", f"Error during playlist conversion: {error_msg}")

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as config_file:
                config = json.load(config_file)
                self.plex_username_input.setText(config.get("plex_username", ""))
                self.server_ip_input.setText(config.get("server_ip", "127.0.0.1"))
                self.server_port_input.setText(config.get("server_port", "32400"))
                self.token_input.setText(config.get("token", ""))
                self.last_section_id = config.get("last_section")
            
            # If we have a saved section, select it in the combo box
            if self.last_section_id and self.section_combo.count() > 0:
                index = self.section_combo.findData(self.last_section_id)
                if index >= 0:
                    self.section_combo.setCurrentIndex(index)
                    
            # Load sync configurations
            self.load_sync_config()
            
        except Exception as e:
            logging.error(f"Error loading configuration: {str(e)}")

    def save_config(self):
        config = {
            "plex_username": self.plex_username_input.text(),
            "server_ip": self.server_ip_input.text(),
            "server_port": self.server_port_input.text(),
            "token": self.token_input.text(),
            "last_section": self.section_combo.currentData()
        }
        try:
            with open(CONFIG_FILE, 'w') as config_file:
                json.dump(config, config_file, indent=4)
            logging.info("Configuration saved successfully.")
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")

    def get_stylesheet(self):
        return """
        QMainWindow, QMessageBox, QMenu, QDialog {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QWidget {
            color: #ffffff;
            font-size: 14px;
        }
        QPushButton, QComboBox {
            background-color: #3a3a3a;
            border: none;
            padding: 10px 15px;
            margin: 5px;
            border-radius: 5px;
            min-height: 20px;
            color: #ffffff;
        }
        QPushButton:hover, QComboBox:hover {
            background-color: #4a4a4a;
        }
        QPushButton:pressed, QComboBox:on {
            background-color: #2a2a2a;
        }
        .modern-button {
            padding: 0px 15px;
            text-align: center;
        }
        QLineEdit, QTextEdit, QPlainTextEdit {
            background-color: #2a2a2a;
            border: 1px solid #3a3a3a;
            padding: 5px;
            border-radius: 3px;
            min-height: 20px;
            color: #ffffff;
        }
        QListWidget, QTreeWidget, QTableWidget {
            background-color: #2a2a2a;
            border: 1px solid #3a3a3a;
            border-radius: 5px;
            color: #ffffff;
        }
        QListWidget::item, QTreeWidget::item, QTableWidget::item {
            padding: 5px;
        }
        QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
            background-color: #3a3a3a;
        }
        QCheckBox {
            spacing: 5px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QCheckBox::indicator:unchecked {
            border: 2px solid #3a3a3a;
            background-color: #2a2a2a;
        }
        QCheckBox::indicator:checked {
            border: 2px solid #3a3a3a;
            background-color: #4a4a4a;
        }
        QProgressBar {
            border: 1px solid #3a3a3a;
            border-radius: 5px;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #4a4a4a;
        }
        QScrollBar:vertical {
            border: none;
            background-color: #2a2a2a;
            width: 10px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #4a4a4a;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QGroupBox {
            border: 1px solid #3a3a3a;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QMenu::item {
            background-color: #1e1e1e;
            color: #ffffff;
            padding: 5px 20px;
        }
        QMenu::item:selected {
            background-color: #3a3a3a;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left-width: 1px;
            border-left-color: #3a3a3a;
            border-left-style: solid;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
        }
        QComboBox::down-arrow {
            image: url(down_arrow.png);
        }
        QComboBox QAbstractItemView {
            background-color: #2a2a2a;
            border: 1px solid #3a3a3a;
            selection-background-color: #3a3a3a;
            selection-color: #ffffff;
        }
        QToolTip {
            background-color: #2a2a2a;
            color: #ffffff;
            border: 1px solid #3a3a3a;
            padding: 5px;
        }
        QStatusBar {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QHeaderView::section {
            background-color: #3a3a3a;
            color: #ffffff;
            padding: 5px;
            border: 1px solid #2a2a2a;
        }
        QSpinBox {
            background-color: #2a2a2a;
            border: 1px solid #3a3a3a;
            padding: 5px;
            border-radius: 3px;
            color: #ffffff;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background-color: #3a3a3a;
            border: none;
        }
        QTabWidget::pane {
            border: 1px solid #3a3a3a;
            background-color: #2a2a2a;
        }
        QTabBar::tab {
            background-color: #3a3a3a;
            color: #ffffff;
            padding: 8px 15px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: #4a4a4a;
        }
        QTableWidget::item:selected {
            background-color: #4a4a4a;
        }
        """

    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop any running threads
            if self.sync_thread and self.sync_thread.isRunning():
                self.sync_thread.stop()
                self.sync_thread.wait(3000)  # Wait up to 3 seconds
            
            if self.fetch_thread and self.fetch_thread.isRunning():
                self.fetch_thread.terminate()
                self.fetch_thread.wait(3000)
            
            if self.backup_thread and self.backup_thread.isRunning():
                self.backup_thread.terminate()
                self.backup_thread.wait(3000)
            
            if self.batch_track_count_thread and self.batch_track_count_thread.isRunning():
                self.batch_track_count_thread.stop()
                self.batch_track_count_thread.wait(3000)
                
            if hasattr(self, 'duplicates_thread') and self.duplicates_thread.isRunning():
                self.duplicates_thread.terminate()
                self.duplicates_thread.wait(3000)
            
            # Stop track count loading threads
            for thread in list(self.track_count_threads.values()):
                if thread.isRunning():
                    thread.terminate()
                    thread.wait(1000)
            
            # Stop auto-sync timer
            if self.auto_sync_timer.isActive():
                self.auto_sync_timer.stop()
            
            # Save configuration and cache
            self.save_config()
            self.save_sync_config()
            self.playlist_cache.save_cache()
            
            # Close loading dialog if open
            if self.loading_dialog:
                self.loading_dialog.close()
            
            event.accept()
            
        except Exception as e:
            logging.error(f"Error during application close: {str(e)}")
            event.accept()  # Close anyway

def main():
    setup_logging()
    initialize_config()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # This can help with some styling issues
    ex = PlexPlaylistManager()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()