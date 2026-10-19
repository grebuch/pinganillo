import unittest
from types import SimpleNamespace
from unittest.mock import patch
import app


class Widget:
    def __init__(self, *args, **kwargs):
        self.options = kwargs
        self.index = -1
    def __setitem__(self, key, value):
        self.options[key] = value
    def current(self, index=None):
        if index is None:
            return self.index
        if not 0 <= index < len(self.options.get('values', [])):
            raise ValueError('Combobox index out of range')
        self.index = index
    def __getattr__(self, name):
        return lambda *a, **kw: None


class StartupTests(unittest.TestCase):
    def test_build_window_selects_existing_modes(self):
        fake_ttk = SimpleNamespace(**{name: Widget for name in [
            'Style', 'Frame', 'Label', 'Combobox', 'Button', 'Entry',
            'Progressbar', 'Panedwindow']})
        auth = SimpleNamespace(config={'registrations': []}, tokens=None)
        with patch.object(app, 'ttk', fake_ttk), patch.object(app, 'ScrolledText', Widget), \
             patch.object(app.tk, 'StringVar', Widget), \
             patch.object(app, 'ChatGPTAuth', return_value=auth), \
             patch.object(app.App, 'refresh'):
            instance = app.App(Widget())
            self.assertEqual(instance.mode.current(), 2)
            self.assertEqual(len(instance.mode.options['values']), 3)
