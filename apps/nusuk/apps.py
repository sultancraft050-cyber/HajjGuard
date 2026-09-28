from django.apps import AppConfig


class NusukConfig(AppConfig):
    name = 'nusuk'

    def ready(self):
        import nusuk.signals
