from manim import *
from manim.opengl import *


class GeneratedScene(Scene):
    def construct(self):
        # DO NOT EDIT: replaced by manim-server before render.
        session_id = "__SESSION_ID__"
        session_title = "__SESSION_TITLE__"
        template_id = "__TEMPLATE_ID__"

        title = Text(session_title or "Untitled", font_size=52)
        subtitle = Text("Manim Server", font_size=24, color=GRAY_B).next_to(title, DOWN)
        card = VGroup(title, subtitle)
        self.play(FadeIn(card, shift=UP * 0.2), run_time=0.8)
        self.wait(0.3)
        self.play(FadeOut(card, shift=UP * 0.2), run_time=0.5)
