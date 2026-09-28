import reflex as rx

config = rx.Config(
    app_name="PL_Model",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)