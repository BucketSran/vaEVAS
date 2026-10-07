"""Public request-envelope documentation for newly frozen native sessions."""
import json

ENVELOPE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['action_id', 'tool', 'arguments'],
    'properties': {
        'action_id': {'type': 'string', 'pattern': '^[A-Za-z0-9_-]{1,80}$',
                      'not': {'pattern': '[^A-Za-z0-9_-]'}},
        'tool': {'type': 'string', 'enum': ['evas_read', 'evas_write', 'evas_simulate', 'evas_submit']},
        'arguments': {'type': 'object'},
    },
    'allOf': [
        {'if': {'properties': {'tool': {'const': tool}}},
         'then': {'properties': {'arguments': {
             'type': 'object', 'additionalProperties': False,
             'required': fields, 'properties': {key: {'type': 'string'} for key in fields},
         }}}}
        for tool, fields in [('evas_read', ['path']), ('evas_write', ['path', 'content']),
                             ('evas_simulate', []), ('evas_submit', [])]
    ],
}
MARKER = '<!-- native public action envelope v1 -->'
NOTE = '''
<!-- native public action envelope v1 -->
公开工具命令是 `harness-public info` 和 `harness-public action`。
`info` 给出函数arguments schema；调用action时还必须包上外层三键：action_id、tool、arguments，不能直接提交函数参数或模型API的tool_call对象。
action_id必须为1至80个字母、数字、下划线或短横线。每个新动作使用新ID；同一动作的重试保留原ID和完全相同请求，不通过换ID重试不确定的请求。

实际读取题面的例子：
```sh
harness-public action <<'JSON'
{"action_id":"read_1","tool":"evas_read","arguments":{"path":"instruction.md"}}
JSON
```
完整外层及各工具参数schema如下。`evas_write`的content是完整文件字符串；`evas_simulate`及`evas_submit`的arguments必须是空对象。
''' + '\n```json\n' + json.dumps(ENVELOPE_SCHEMA, ensure_ascii=False, indent=2) + '\n```\n' + '''
使用evas_write写入全部声明候选文件；完成时使用evas_submit。阶段结束或预算耗尽时，包装器按既定协议冻结最近完整候选；未写齐全部候选文件则不能冻结。普通容器文件不会自动成为正式交付物。公开自测不是终评。
evas_read的path为空字符串时列出文件；其他path须属于声明的公开文件或候选文件。evas_write只能替换声明候选文件的完整内容。该schema描述本次native公开会话的四项工具；可选Docker实验工具不在本次会话启用。
'''


def append_note(text):
    return text if MARKER in text else text + '\n' + NOTE
