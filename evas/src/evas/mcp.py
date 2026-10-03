"""Single-session read-only MCP stdio server. No kernel execution in tool calls."""
import argparse
import json
import sys

from .diagnostics import Session, load_json

VERSION = '2025-11-25'
MAX_MESSAGE = 1024 * 1024
SECTIONS = ['modules', 'instances', 'nodes', 'contributions', 'operators', 'states', 'events']
RANGE = dict(start=dict(type='integer', minimum=0), limit=dict(type='integer', minimum=1, maximum=1000))


def tool(name, description, properties, required=()):
    return dict(name=name, description=description,
                inputSchema=dict(type='object', properties=properties,
                                 required=list(required), additionalProperties=False),
                annotations=dict(readOnlyHint=True, destructiveHint=False, openWorldHint=False))


TOOLS = [tool('evas_status', 'Run status, completeness and source identities.', {}),
         tool('evas_static', 'Compiled instances, connectivity and actual source origins.',
              dict(section=dict(type='string', enum=SECTIONS), **RANGE), ['section']),
         tool('evas_metrics', 'Inclusive stage times and calling-thread counters; times overlap.', {}),
         *[tool(f'evas_{section}', f'Page stored {section}; no evaluation or interpolation.', RANGE)
           for section in ['trace', 'samples', 'firings']],
         tool('evas_why_no_cross', 'Report observed firings or unknown; absence alone does not explain a missing cross.',
              dict(event=dict(type='integer', minimum=0)), ['event'])]


class Server:
    def __init__(self, session):
        self.session = session
        self.phase = 'new'

    def dispatch(self, message):
        if (not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or
                not isinstance(message.get('method'), str) or
                'id' in message and (type(message['id']) not in (int, str))):
            return dict(jsonrpc='2.0', id=None, error=dict(code=-32600, message='Invalid Request'))
        method, params = message['method'], message.get('params', {})
        if 'id' not in message:
            if method == 'notifications/initialized' and self.phase == 'initializing':
                self.phase = 'ready'
            return None
        request_id = message['id']
        if not isinstance(params, dict):
            return self.error(request_id, -32602, 'Invalid params')
        try:
            if method == 'ping':
                result = {}
            elif method == 'initialize':
                if self.phase != 'new':
                    raise ValueError('Already initialized')
                if (not isinstance(params.get('protocolVersion'), str) or
                        not isinstance(params.get('capabilities'), dict) or
                        not isinstance(params.get('clientInfo'), dict) or
                        not isinstance(params['clientInfo'].get('name'), str) or
                        not isinstance(params['clientInfo'].get('version'), str)):
                    raise ValueError('Initialization requires version/capabilities/clientInfo')
                self.phase = 'initializing'
                result = dict(protocolVersion=VERSION, capabilities=dict(tools=dict(listChanged=False)),
                              serverInfo=dict(name='evas-diagnostics', version='0.1.0'))
            elif self.phase != 'ready':
                raise ValueError('Initialize and send notifications/initialized first')
            elif method == 'tools/list':
                if params:
                    raise ValueError('This fixed tool list has no pagination cursor')
                result = dict(tools=TOOLS)
            elif method == 'tools/call':
                name, arguments = params.get('name'), params.get('arguments', {})
                definition = next((t for t in TOOLS if t['name'] == name), None)
                if definition is None or not isinstance(arguments, dict):
                    raise ValueError('Unknown tool or invalid arguments')
                schema = definition['inputSchema']
                if set(arguments) - schema['properties'].keys() or not set(schema['required']) <= arguments.keys():
                    raise ValueError('Tool argument fields do not match its schema')
                try:
                    if name == 'evas_why_no_cross':
                        value = self.session.why_no_cross(arguments['event'])
                    elif name == 'evas_static':
                        value = self.session.query(**arguments)
                    else:
                        value = self.session.query(name.removeprefix('evas_'), **arguments)
                    text = json.dumps(value, allow_nan=False)
                    if len(text.encode()) > MAX_MESSAGE // 2:
                        raise ValueError('Result budget exceeded; request a smaller page')
                    result = dict(content=[dict(type='text', text=text)], structuredContent=value, isError=False)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    result = dict(content=[dict(type='text', text=str(exc))], isError=True)
            else:
                return self.error(request_id, -32601, 'Method not found')
        except (ValueError, KeyError, TypeError) as exc:
            return self.error(request_id, -32602, str(exc))
        return dict(jsonrpc='2.0', id=request_id, result=result)

    @staticmethod
    def error(request_id, code, message):
        return dict(jsonrpc='2.0', id=request_id, error=dict(code=code, message=message))

    def serve(self, input_stream, output_stream):
        while line := input_stream.readline(MAX_MESSAGE+1):
            if len(line.encode()) > MAX_MESSAGE or not line.endswith('\n'):
                # Drain a large message; EOF with an unterminated line is invalid.
                while line and not line.endswith('\n'):
                    line = input_stream.readline(MAX_MESSAGE+1)
                response = self.error(None, -32600, 'Message budget exceeded or missing newline')
            else:
                try:
                    response = self.dispatch(load_json(line))
                except (ValueError, RecursionError):
                    response = self.error(None, -32700, 'Parse error')
            if response is not None:
                output_stream.write(json.dumps(response, allow_nan=False, separators=(',', ':')) + '\n')
                output_stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session', type=str)
    args = parser.parse_args()
    try:
        Server(Session(args.session)).serve(sys.stdin, sys.stdout)
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
