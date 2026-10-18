"""Example plugin: adds a "Say Hello" action under the Plugins menu.

Copy this file as a starting point for real plugins.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from graphmatrix.ui.actions import ActionSpec


def register(context) -> None:
    def say_hello() -> None:
        QMessageBox.information(
            context.window,
            "Hello from a plugin",
            "This action was contributed by graphmatrix/plugins/hello.py\n"
            "Plugins call register(context) and use context.registry / context.commands.",
        )

    action = context.registry.register(
        ActionSpec(id="plugin.hello.say", text="Say Hello"),
        say_hello,
    )
    context.plugins_menu.addAction(action)
