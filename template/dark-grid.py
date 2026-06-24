from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        self.camera.background_color = "#10131a"
        grid = NumberPlane(
            x_range=(-8, 9, 1),
            y_range=(-5, 6, 1),
            background_line_style={"stroke_color": BLUE_E, "stroke_width": 1, "stroke_opacity": 0.25},
        )
        title = Text(session_title or "Untitled", font_size=28, color=BLUE_A).to_corner(UL)
        self.add(grid, title)
