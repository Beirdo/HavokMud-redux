import re

from colors import color


class AnsiColors(object):
    default = "0007"  # light grey on black
    colorCodeRe = re.compile(r'(?P<preamble>.*?)\$C(?P<code>\d\d\d\S)(?P<text>.*?)(?=(?P<eol>[\r\n]+)|$|\$C\d\d\d\S)',
                             re.I)
    styles = ["none", "bold", "faint", "italic", "underline", "blink", "negative"]
    colors = ['black', 'red', "green", "yellow", "blue", "magenta", "cyan", "white"]
    fg_map = {
        "00": {"style": "none", "fg": "black"},
        "0X": {"style": "none", "fg": "black"},
        "01": {"style": "none", "fg": "red"},
        "0r": {"style": "none", "fg": "red"},
        "02": {"style": "none", "fg": "green"},
        "0g": {"style": "none", "fg": "green"},
        "03": {"style": "none", "fg": "yellow"},
        "0y": {"style": "none", "fg": "yellow"},
        "04": {"style": "none", "fg": "blue"},
        "0b": {"style": "none", "fg": "blue"},
        "05": {"style": "none", "fg": "magenta"},
        "0p": {"style": "none", "fg": "magenta"},
        "06": {"style": "none", "fg": "cyan"},
        "0c": {"style": "none", "fg": "cyan"},
        "07": {"style": "none", "fg": "white"},
        "0w": {"style": "none", "fg": "white"},
        "08": {"style": "bold", "fg": "black"},
        "0x": {"style": "bold", "fg": "black"},
        "09": {"style": "bold", "fg": "red"},
        "0R": {"style": "bold", "fg": "red"},
        "10": {"style": "bold", "fg": "green"},
        "0G": {"style": "bold", "fg": "green"},
        "11": {"style": "bold", "fg": "yellow"},
        "0Y": {"style": "bold", "fg": "yellow"},
        "12": {"style": "bold", "fg": "blue"},
        "0B": {"style": "bold", "fg": "blue"},
        "13": {"style": "bold", "fg": "magenta"},
        "0P": {"style": "bold", "fg": "magenta"},
        "14": {"style": "bold", "fg": "cyan"},
        "0C": {"style": "bold", "fg": "cyan"},
        "15": {"style": "bold", "fg": "white"},
        "0W": {"style": "bold", "fg": "white"},
    }

    def __init__(self):
        pass

    def convert_string(self, input, ansi=True):
        parts = [item.groupdict() for item in self.colorCodeRe.finditer(input)]
        if not parts:
            parts = [{"text": input, "code": self.default}]

        count = 0
        parts_in = list(parts)
        for (index, part) in enumerate(parts_in):
            preamble = parts[index + count].pop("preamble", None)
            if preamble:
                parts.insert(index + count, {"text": preamble, "code": self.default})
                count += 1

        output = ""
        color_params = {}
        old_color_params = {}

        for part in parts:
            if ansi:
                color_params = self.convert_code(part.get("code", self.default))
            text = part.get("text", "")
            eol = part.get("eol", "")
            if not eol:
                eol = ""
            if not ansi or color_params == old_color_params:
                output += text
            else:
                output += color(text, **color_params)
            output += eol

        return output

    def convert_code(self, code):
        params = {}

        bg_index = int(code[1])
        if bg_index >= len(self.colors):
            bg_index = 0
        params["bg"] = self.colors[bg_index]

        style_index = int(code[0])
        if style_index >= len(self.styles):
            style_index = 0
        style = self.styles[style_index]

        fg_code = code[2:]
        fg_params = self.fg_map.get(fg_code, {"style": "none", "fg": "white"})
        new_style = fg_params.get("style", None)
        if new_style == "none" and style == "bold":
            style = "none"
        elif style == "none":
            style = new_style
        else:
            style += "+" + new_style

        if style != "none":
            params["style"] = style
        params['fg'] = fg_params.get("fg", "white")
        return params
