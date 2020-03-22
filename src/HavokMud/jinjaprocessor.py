import stackless

from jinja2 import Environment, PackageLoader


class JinjaProcessor(object):
    def __init__(self):
        self.in_channel = stackless.channel()
        self.environment = Environment(
            loader=PackageLoader("HavokMud", "templates"),
            autoescape=False,
            newline_sequence="\r\n",
            keep_trailing_newline=True,
        )

        stackless.tasklet(self.process_data)()

    def process_data(self):
        while True:
            data = self.in_channel.receive()
            if not isinstance(data, dict):
                continue

            out_channel = data.get("channel", None)
            template_name = data.get("template", None)
            params = data.get("params", {})

            if not out_channel:
                continue

            if template_name:
                template = self.environment.get_template(template_name)
                out_data = template.render(**params)
            else:
                out_data = ""
            out_channel.send(out_data)


jinja_processor = JinjaProcessor()
