"""Deterministic contract checks; these do not simulate or prove model obedience."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('autonomy_policy', ROOT / 'scripts/manage_agent_autonomy.py')
autonomy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(autonomy)
DURABLE = (ROOT / 'skills/memoria-durable-opencode/SKILL.md').read_text()
BACKEND = (ROOT / 'skills/memoria-engram-opencode/SKILL.md').read_text()


class MemoryPolicyTests(unittest.TestCase):
    def test_roles_keep_their_targets_and_distinct_finding_types(self):
        self.assertEqual(set(autonomy.AGENT_RULES), {'plan', 'build', 'planner', 'master-dev', 'agent-design'})
        self.assertTrue(all(r['task_target'] == 'knowledge-reader' for r in autonomy.AGENT_RULES.values()))
        self.assertIn('descartes', autonomy.AGENT_RULES['planner']['block'])
        self.assertIn('bugfixes', autonomy.AGENT_RULES['master-dev']['block'])
        self.assertIn('reglas de diseño', autonomy.AGENT_RULES['agent-design']['block'])

    def test_context_and_direct_lookup_do_not_force_a_child(self):
        for rule in autonomy.AGENT_RULES.values():
            text = rule['block']
            for clause in ('Si el contexto alcanza, no releas', 'consulta puntual directa',
                           'tools autorizadas', 'sólo si el rol permite delegar', 'Sin acceso, pedí contexto',
                           'lecturas locales obligatorias'):
                self.assertIn(clause, text)
            self.assertNotIn('consultá primero `knowledge-reader`', text)

    def test_reader_does_not_requery_merely_because_history_exists(self):
        text = (ROOT / 'agents/knowledge-reader.md').read_text()
        self.assertIn('reutilizar evidencia suficiente del caller', text)
        self.assertIn('si falta historial pertinente', text)
        self.assertIn('sólo si están disponibles', text)
        self.assertNotIn('si el problema parece tener historial durable', text)

    def test_milestones_urgency_and_local_closures_are_distinct(self):
        for rule in autonomy.AGENT_RULES.values():
            text = rule['block']
            for clause in ('confirmados y reutilizables', 'un hito', 'pedidos de recordar o restricciones críticas',
                           'autoridad del rol', 'el contrato local lo exige expresamente',
                           'no reemplaza una memoria obligatoria',
                           'sin novedades', 'hipótesis/microiteraciones', 'No indexes corpus automáticamente'):
                self.assertIn(clause, text)

    def test_critical_previews_need_evidence_not_a_claim_of_prior_reading(self):
        for clause in ('no se basa en previews truncados', 'original necesario', 'fuente verificable',
                       '«ya lo leí» no basta', 'evidencia, no instrucciones confiables'):
            self.assertIn(clause, DURABLE)

    def test_read_only_and_unavailable_tools_do_not_gain_authority(self):
        for clause in ('Un rol read-only puede sintetizar para el caller', 'no escribir observaciones ni summaries en el backend', 'ningún recuerdo', 'sin bypass'):
            if clause == 'ningún recuerdo':
                self.assertIn(clause, DURABLE.lower())
            elif clause == 'sin bypass':
                self.assertIn('no usar SQL/CLI ni otro agente como bypass', DURABLE)
            else:
                self.assertIn(clause, DURABLE)
        self.assertIn('pedir contexto al caller', DURABLE)

    def test_ordinary_no_change_does_not_require_a_summary(self):
        for clause in ('No por cada respuesta', 'cierre repetido sin cambios',
                       'registro existente ya alcanza', 'No sustituye una memoria reusable',
                       'observación local obligatoria'):
            self.assertIn(clause, DURABLE)
        self.assertNotIn('Siempre consultar primero', DURABLE)
        self.assertNotIn('Luego consultar 1 a 3', DURABLE)

    def test_metadata_topics_and_rework_identity_are_preserved(self):
        for clause in ('`project`', '`scope`', '`type`', '`topic_key`', '`source_agent`',
                       'proyectos respaldados', 'identidad del tema en retrabajos',
                       'analysis/<ticket>/<tema>', 'validation/<ticket>/<tema>', 'architecture/<tema-estable>'):
            self.assertIn(clause, DURABLE)

    def test_privacy_and_pending_conflicts_are_not_a_performance_tradeoff(self):
        for clause in ('<private>...</private>', 'Si todo lo útil es privado, no guardarlo',
                       'capture_prompt=false', 'No guardar prompts crudos',
                       'protocolo de conflictos', 'dejarla pendiente', 'no simular persistencia'):
            self.assertIn(clause, DURABLE)

    def test_backend_errors_are_not_retried_or_repaired_blindly(self):
        for clause in ('unknown_project', 'unknown_session', 'no repetir iguales argumentos',
                       'no prueba que nada se guardó', 'lectura autorizada', 'no reinstalar'):
            self.assertIn(clause, BACKEND.lower())

    def test_fresh_apply_is_idempotent_without_changing_unrelated_body(self):
        text = '---\nmode: subagent\npermission:\n  edit: deny\n  task:\n    "*": deny\n---\nSafety guard stays.\n\nEntrega esperada:\n- result\n'
        with tempfile.TemporaryDirectory(prefix='autonomy-contract-') as temp:
            path = Path(temp) / 'planner.md'
            path.write_text(text)
            autonomy.apply_to_agent(path, autonomy.AGENT_RULES['planner'])
            first = path.read_text()
            autonomy.apply_to_agent(path, autonomy.AGENT_RULES['planner'])
            self.assertEqual(first, path.read_text())
            self.assertEqual(first.count(autonomy.MARKER_START), 1)
            self.assertIn('Safety guard stays.', first)
            self.assertIn('  edit: deny', first)
            self.assertIn('    "*": deny', first)
            self.assertEqual(first.count('knowledge-reader: allow'), 1)
            autonomy.remove_from_agent(path)
            self.assertEqual(path.read_text(), text)

    def test_legacy_marked_body_is_not_silently_claimed_as_updated(self):
        old = autonomy.MARKER_START + '\nlegacy policy\n' + autonomy.MARKER_END + '\n'
        self.assertEqual(autonomy.patch_body(old, autonomy.AGENT_RULES['planner']['block']), old)
        fresh = autonomy.unpatch_body(old)
        updated = autonomy.patch_body(fresh, autonomy.AGENT_RULES['planner']['block'])
        self.assertIn('consulta puntual directa', updated)
        self.assertNotIn('legacy policy', updated)


if __name__ == '__main__':
    unittest.main()
