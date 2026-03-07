# src/screens/menu.py
from kivy.app import App
from kivy.uix.screenmanager import Screen

class MenuScreen(Screen):
    def go_back(self):
        self.manager.current = "login"

    def start_game(self, game_type):
        print(f"Starting game: {game_type}")
        self.manager.current = game_type   # "game1", "game2", "game3"

    def open_settings(self):
        self.manager.current = "settings"
