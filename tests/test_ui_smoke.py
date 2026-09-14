import flet as ft


def test_desktop_controls_used_by_main_ui_are_available():
    segmented = ft.SegmentedButton(
        selected=["username"],
        segments=[
            ft.Segment(
                value="username",
                label=ft.Text("Usuario"),
                icon=ft.Icon(ft.Icons.ALTERNATE_EMAIL),
            )
        ],
    )
    image = ft.Image(
        src="https://example.com/avatar.png",
        error_content=ft.Icon(ft.Icons.ACCOUNT_CIRCLE),
    )
    button = ft.FilledButton(
        content="Abrir perfil",
        icon=ft.Icons.OPEN_IN_NEW,
        url="https://example.com/profile",
    )

    assert segmented.selected == ["username"]
    assert image.error_content is not None
    assert button.url == "https://example.com/profile"
