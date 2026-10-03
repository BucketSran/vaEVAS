"""Static queries follow compiled IR identities and actual source positions."""
GUARDS = ["LANG", "COMPOSE"]

import unittest
from evas import compile_sources
from evas.query import static_index, query_static
from test_affine import instance, model


class StaticQueryTests(unittest.TestCase):
    def test_instance_origins_and_connectivity(self):
        source = model('V(y,r)<+idt(V(u,r),0);')
        instances = [instance('a', connections=dict(u='u', y='ya', r='0')),
                     instance('b', connections=dict(u='u', y='yb', r='0'))]
        program = compile_sources({'query.va': source}, instances)
        index = static_index(program, instances, {'query.va':source})
        self.assertEqual([r['name'] for r in index['instances']], ['a', 'b'])
        self.assertEqual(len(index['operators']), 2)
        self.assertEqual(index['modules'][0]['name'], 'm')
        self.assertEqual(index['modules'][0]['ports'], ['u','y','r'])
        for row in index['operators']:
            origin = row['origin']
            self.assertEqual(origin['source'], 'query.va')
            self.assertIn('idt', source.splitlines()[origin['line']-1])
            self.assertIn(origin['instance'], ['a', 'b'])
            self.assertEqual([program.nodes[n] for n in row['input_nodes']], ['0', 'u'])
        page = query_static(index, 'operators', limit=1)
        self.assertEqual(page['total'], 2)
        self.assertEqual(page['next_start'], 1)
        self.assertIsNone(query_static(index, 'operators', start=1)['next_start'])

    def test_equivalent_encodings_keep_dependency_meaning(self):
        indices = []
        for body, declaration in [('V(y,r)<+V(u,r); V(y,r)<+2;', ''),
                                  ('V(y,r)<+2; V(y,r)<+V(u,r);', ''),
                                  ('local=V(u,r); V(y,r)<+local; V(y,r)<+2;', 'real local;')]:
            program = compile_sources({'query.va': model(body, declaration)}, [instance()])
            index = static_index(program)
            meaning = sorted((program.nodes[c['positive']],
                              program.nodes[c['negative']],
                              tuple(program.nodes[n] for n in c['input_nodes']))
                             for c in index['contributions'])
            indices.append(meaning)
        self.assertEqual(indices[0], indices[1])
        self.assertEqual(indices[0], indices[2])

    def test_queries_are_bounded_and_do_not_modify_ir(self):
        program = compile_sources({'query.va': model('V(y,r)<+V(u,r);')}, [instance()])
        before = program.to_dict()
        index = static_index(program)
        for section in ['nodes', 'contributions', 'operators', 'states', 'events', 'instances']:
            query_static(index, section)
        self.assertEqual(before, program.to_dict())
        for bad in [0, 1001, True]:
            with self.assertRaises(ValueError):
                query_static(index, 'nodes', limit=bad)

    def test_split_contributions_preserve_node_dependencies(self):
        for body in ['V(y,r)<+V(u,r)+2;', 'V(y,r)<+V(u,r); V(y,r)<+2;']:
            program = compile_sources({'query.va': model(body)}, [instance()])
            index = static_index(program)
            dependencies = {program.nodes[n] for c in index['contributions'] for n in c['input_nodes']}
            self.assertEqual(dependencies, {'0', 'u'})
            self.assertTrue(all({program.nodes[c['positive']], program.nodes[c['negative']]}=={'0','y'}
                                for c in index['contributions']))
