from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled", font_size=36).to_edge(UP)
        underline = Line(LEFT, RIGHT).set_width(config.frame_width - 1).next_to(title, DOWN, buff=0.15)
        self.add(title, underline)
