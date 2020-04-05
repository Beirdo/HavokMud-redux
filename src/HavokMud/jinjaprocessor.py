import stackless

from jinja2 import Environment, PackageLoader


class JinjaRequest(object):
    def __init__(self, data):
        self.data = data
        self.channel = stackless.channel()


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
            request = self.in_channel.receive()
            if not isinstance(request, JinjaRequest):
                continue

            out_channel = request.channel
            if not out_channel:
                continue

            data = request.data
            template_name = data.get("template", None)
            params = data.get("params", {})

            if template_name:
                template = self.environment.get_template(template_name)
                out_data = template.render(**params)
            else:
                out_data = ""
            out_channel.send(out_data)

    def process(self, data):
        request = JinjaRequest(data)
        self.in_channel.send(request)
        return request.channel.receive()


jinja_processor = JinjaProcessor()
