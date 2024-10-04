import sys
import json
import os
import logging
import tempfile
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget, 
                             QCheckBox, QListWidgetItem, QProgressBar, 
                             QMessageBox, QComboBox, QStackedWidget, QGroupBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from urllib.parse import quote
import deezer
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import re
from fuzzywuzzy import fuzz

CONFIG_FILE = "app_config.json"

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
            "last_section": None
        }
        try:
            with open(CONFIG_FILE, 'w') as config_file:
                json.dump(default_config, config_file, indent=4)
            logging.info(f"Created {CONFIG_FILE} with default values.")
        except Exception as e:
            logging.error(f"Failed to create {CONFIG_FILE}: {str(e)}")
    else:
        logging.info(f"{CONFIG_FILE} already exists.")

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

class SpotifyAnonymousAuth:
    def __init__(self):
        self.access_token = None
        self.token_expiration = 0

    def get_token(self):
        if self.access_token and time.time() < self.token_expiration:
            return self.access_token

        try:
            response = requests.get(
                'https://open.spotify.com/get_access_token',
                params={
                    'reason': 'transport',
                    'productType': 'embed'
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
            response.raise_for_status()
            data = response.json()

            self.access_token = data['accessToken']
            self.token_expiration = data['accessTokenExpirationTimestampMs'] / 1000  # Convert to seconds

            return self.access_token
        except Exception as e:
            logging.error(f"Failed to get Spotify anonymous token: {str(e)}")
            raise

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
        try:
            token = self.spotify_auth.get_token()
            playlist_id = self.playlist_source.split('/')[-1].split('?')[0]
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}', headers=headers)
            response.raise_for_status()
            playlist_data = response.json()

            tracks = []
            for item in playlist_data['tracks']['items']:
                track = item['track']
                tracks.append(f"{track['name']} - {track['artists'][0]['name']}")

            playlist_name = playlist_data['name']
            playlist_image_url = playlist_data['images'][0]['url'] if playlist_data['images'] else None

            logging.info(f"Fetched {len(tracks)} tracks from Spotify playlist '{playlist_name}'")
            return tracks, playlist_name, playlist_image_url
        except Exception as e:
            logging.error(f"Error fetching Spotify playlist: {str(e)}")
            raise

    def get_spotify_tracks(self):
        try:
            playlist_id = self.playlist_source.split('/')[-1].split('?')[0]
            results = self.spotify_client.playlist_tracks(playlist_id)
            tracks = []
            while results:
                for item in results['items']:
                    track = item['track']
                    tracks.append(f"{track['name']} - {track['artists'][0]['name']}")
                if results['next']:
                    results = self.spotify_client.next(results)
                else:
                    results = None
                self.progress_update.emit(int(len(tracks) / results['total'] * 50))
            return tracks
        except Exception as e:
            raise ValueError(f"Error fetching Spotify playlist: {e}")

    def get_deezer_tracks(self):
        try:
            playlist_id = self.playlist_source.split('/')[-1]
            logging.info(f"Fetching Deezer playlist with ID: {playlist_id}")
            playlist = self.deezer_client.get_playlist(playlist_id)
            tracks = []
            total_tracks = playlist.nb_tracks
            logging.info(f"Total tracks in Deezer playlist: {total_tracks}")
            for i, track in enumerate(playlist.tracks):
                tracks.append(f"{track.title} - {track.artist.name}")
                self.progress_update.emit(int((i + 1) / total_tracks * 50))
            logging.info(f"Successfully fetched {len(tracks)} tracks from Deezer playlist")
            return tracks
        except Exception as e:
            logging.error(f"Error fetching Deezer playlist: {str(e)}", exc_info=True)
            raise ValueError(f"Error fetching Deezer playlist: {e}")

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

    def get_deezer_playlist_image(self, image_url):
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            return image
        except Exception as e:
            logging.error(f"Failed to fetch Deezer playlist image: {str(e)}")
            return None

    def get_local_tracks(self):
        try:
            with open(self.playlist_source, 'r', encoding='utf-8') as file:
                content = file.readlines()
            tracks = [line.strip() for line in content if line.strip() and not line.startswith('#')]
            return tracks
        except Exception as e:
            raise ValueError(f"Error reading local playlist file: {e}")

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
                        encoded_url = quote(playlist_image_url)
                        poster_url = f"{self.plex_server._baseurl}/library/metadata/{plex_playlist.ratingKey}/posters"
                        params = {
                            'url': encoded_url,
                            'X-Plex-Token': self.plex_server._token
                        }
                        response = requests.post(poster_url, params=params)
                        response.raise_for_status()
                        logging.info(f"Successfully set thumbnail for playlist '{playlist_name}'")
                    except Exception as thumb_error:
                        logging.error(f"Failed to set thumbnail: {str(thumb_error)}")
                
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
        self.plex_server = None
        self.spotify_client = None
        self.initUI()
        self.load_config()
        self.setStyleSheet(self.get_stylesheet())
        self.setWindowTitle('Syncra')
        self.setWindowIcon(QIcon('Syncra_Logo.png'))
        self.resize(1200, 800)

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        logo_label = QLabel()
        logo_pixmap = QPixmap(resource_path('Syncra_Logo.png')).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(logo_label)

        self.connection_btn = ModernButton('Connection')
        self.playlists_btn = ModernButton('Playlists')
        self.import_export_btn = ModernButton('Import/Export')
        self.streaming_btn = ModernButton('Streaming Import')

        sidebar_layout.addWidget(self.connection_btn)
        sidebar_layout.addWidget(self.playlists_btn)
        sidebar_layout.addWidget(self.import_export_btn)
        sidebar_layout.addWidget(self.streaming_btn)
        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar)

        # Main content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # Create pages
        self.create_connection_page()
        self.create_playlists_page()
        self.create_import_export_page()
        self.create_streaming_services_page()

        # Connect buttons to switch pages
        self.connection_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(0))
        self.playlists_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(1))
        self.import_export_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(2))
        self.streaming_btn.clicked.connect(lambda: self.content_stack.setCurrentIndex(3))

        # Status bar
        self.statusBar().showMessage('Ready')

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

        buttons_layout = QHBoxLayout()
        self.fetch_playlists_button = ModernButton('Fetch Playlists')
        self.fetch_playlists_button.clicked.connect(self.fetch_playlists)
        buttons_layout.addWidget(self.fetch_playlists_button)

        self.delete_playlist_button = ModernButton('Delete Selected')
        self.delete_playlist_button.clicked.connect(self.delete_selected_playlist)
        buttons_layout.addWidget(self.delete_playlist_button)
        
        layout.addLayout(buttons_layout)
        
        self.playlist_listwidget = QListWidget()
        self.playlist_listwidget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.playlist_listwidget)

        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.select_all_playlists)
        layout.addWidget(self.select_all_checkbox)

        self.content_stack.addWidget(page)

    def create_import_export_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        import_layout = QHBoxLayout()
        self.playlist_input = ModernLineEdit()
        self.playlist_input.setPlaceholderText("Path to .m3u Playlist or Directory")
        import_layout.addWidget(self.playlist_input)

        browse_button = ModernButton('Browse')
        browse_button.clicked.connect(self.browse_files)
        import_layout.addWidget(browse_button)

        layout.addLayout(import_layout)

        import_button = ModernButton('Import Playlist(s)')
        import_button.clicked.connect(self.import_playlist)
        layout.addWidget(import_button)

        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        layout.addWidget(self.import_progress)

        export_button = ModernButton('Export Selected Playlists')
        export_button.clicked.connect(self.export_selected_playlists)
        layout.addWidget(export_button)

        layout.addStretch()
        self.content_stack.addWidget(page)

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

    def authenticate_spotify(self):
        client_id = self.spotify_client_id_input.text()
        client_secret = self.spotify_client_secret_input.text()
        redirect_uri = self.spotify_redirect_uri_input.text()

        if not all([client_id, client_secret, redirect_uri]):
            QMessageBox.warning(self, "Missing Information", "Please fill in all Spotify API settings.")
            return

        scope = "playlist-read-private"
        sp_oauth = SpotifyOAuth(client_id=client_id, client_secret=client_secret,
                                redirect_uri=redirect_uri, scope=scope)
        auth_url = sp_oauth.get_authorize_url()

        auth_dialog = SpotifyAuthDialog(auth_url, redirect_uri, self)
        if auth_dialog.exec_() == QDialog.Accepted and auth_dialog.auth_code:
            token_info = sp_oauth.get_access_token(auth_dialog.auth_code)
            self.spotify_client = spotipy.Spotify(auth=token_info['access_token'])
            QMessageBox.information(self, "Authentication Successful", "Successfully authenticated with Spotify.")
        else:
            QMessageBox.warning(self, "Authentication Failed", "Failed to authenticate with Spotify.")

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

    def create_plex_playlist(self, tracks):
        try:
            playlist_name = f"Imported Playlist {len(self.plex_server.playlists()) + 1}"
            section_id = self.section_combo.currentData()
            if section_id is None:
                raise ValueError("No library section selected")
            
            library_section = self.plex_server.library.sectionByID(section_id)
            if library_section is None:
                raise ValueError(f"Invalid library section: {section_id}")
            
            plex_tracks = []
            total_tracks = len(tracks)
            for i, track in enumerate(tracks):
                search_result = library_section.search(track, limit=1)
                if search_result:
                    plex_tracks.append(search_result[0])
                self.progress_update.emit(50 + int((i + 1) / total_tracks * 50))

            if plex_tracks:
                self.plex_server.createPlaylist(playlist_name, items=plex_tracks)
            else:
                raise ValueError("No matching tracks found in your Plex library")
        except Exception as e:
            logging.error(f"Error creating Plex playlist: {str(e)}", exc_info=True)
            raise ValueError(f"Error creating Plex playlist: {e}")

    def fetch_playlists(self):
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        try:
            self.playlists = self.plex_server.playlists()
            self.update_playlist_listwidget()
            self.statusBar().showMessage(f"Fetched {len(self.playlists)} playlists.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error fetching playlists: {str(e)}")

    def update_playlist_listwidget(self):
        self.playlist_listwidget.clear()
        for playlist in self.playlists:
            item = QListWidgetItem(playlist.title)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.playlist_listwidget.addItem(item)

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
            for item in selected_items:
                playlist = next((p for p in self.playlists if p.title == item.text()), None)
                if playlist:
                    try:
                        playlist.delete()
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Error", f"Error deleting {playlist.title}: {str(e)}")
            
            self.fetch_playlists()
            self.statusBar().showMessage(f"Deleted {len(selected_items)} playlist(s).")

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

    def import_m3u8_playlist(self, playlist_path, section_id):
        try:
            with open(playlist_path, 'r', encoding='utf-8') as file:
                content = file.readlines()
            tracks = [line.strip() for line in content if line.strip() and not line.startswith('#')]
            
            playlist_name = f"Imported Playlist {len(self.plex_server.playlists()) + 1}"
            library_section = self.plex_server.library.sectionByID(section_id)
            
            plex_tracks = []
            total_tracks = len(tracks)
            for i, track in enumerate(tracks):
                search_result = library_section.search(track, limit=1)
                if search_result:
                    plex_tracks.append(search_result[0])
                self.import_progress.setValue(int((i + 1) / total_tracks * 100))
    
            if plex_tracks:
                self.plex_server.createPlaylist(playlist_name, items=plex_tracks)
                self.statusBar().showMessage(f"Successfully imported playlist: {playlist_name}")
            else:
                raise ValueError("No matching tracks found in your Plex library")
            
            self.fetch_playlists()  # Refresh the playlist list after import
        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Error importing playlist: {str(e)}")

    def upload_playlist(self, path):
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
        
        try:
            response = requests.post(url, params=params)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            self.statusBar().showMessage(f"{os.path.basename(path)} imported successfully.")
        except requests.RequestException as e:
            error_message = f"Failed to import {os.path.basename(path)}. Error: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
    
        # Refresh the playlist list after import
        self.fetch_playlists()

    def update_import_progress(self, value):
        self.import_progress.setValue(value)

    def import_finished(self):
        self.import_progress.setVisible(False)
        self.statusBar().showMessage("Import completed.")
        self.fetch_playlists()

    def import_error(self, error_msg):
        self.import_progress.setVisible(False)
        QMessageBox.warning(self, "Import Error", error_msg)

    def export_selected_playlists(self):
        selected_items = [self.playlist_listwidget.item(i) for i in range(self.playlist_listwidget.count()) 
                          if self.playlist_listwidget.item(i).checkState() == Qt.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select playlists to export.")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return

        for item in selected_items:
            playlist = next((p for p in self.playlists if p.title == item.text()), None)
            if playlist:
                try:
                    self.export_playlist(playlist, export_dir)
                except Exception as e:
                    QMessageBox.warning(self, "Export Error", f"Error exporting {playlist.title}: {str(e)}")

        self.statusBar().showMessage(f"Exported {len(selected_items)} playlist(s).")

    def export_playlist(self, playlist, export_dir):
        filename = f"{playlist.title}.m3u"
        filepath = os.path.join(export_dir, filename)
        with open(filepath, "w", encoding="utf-8") as file:
            file.write("#EXTM3U\n")
            for item in playlist.items():
                for part in item.iterParts():
                    file.write(f"{part.file}\n")

    def browse_files(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', "Playlist files (*.m3u *.m3u8)")
        if path:
            self.playlist_input.setText(path)

    def import_streaming_playlist(self):
        playlist_url = self.playlist_url_input.text()
        if not playlist_url:
            QMessageBox.warning(self, "Missing Information", "Please enter a Spotify or Deezer playlist URL.")
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
        QMessageBox.warning(self, "Conversion Error", f"Error during playlist conversion: {error_msg}")

    def save_settings(self):
        self.save_config()
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")

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
    """

    def conversion_error(self, error_msg):
        self.streaming_progress.setVisible(False)
        logging.error(f"Conversion error: {error_msg}")
        QMessageBox.warning(self, "Conversion Error", f"Error during playlist conversion: {error_msg}")

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