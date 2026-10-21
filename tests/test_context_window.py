import copy
import importlib.util
import json
import pathlib
import tempfile
import tomllib
import unittest
import subprocess
import sys
from unittest import mock

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'skills/context-window/scripts/context_window.py'
spec = importlib.util.spec_from_file_location('context_window', SOURCE)
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.cfg = self.root / 'config.toml'
        self.initial = 'model = "example-small"\n# keep this comment\n[desktop]\nlocaleOverride = "zh-CN"\n[plugins.example]\nenabled = true\n'
        self.cfg.write_text(self.initial, encoding='utf-8')
        self.models = [
            {'slug': 'example-main', 'context_window': 500000,
             'max_context_window': 872000, 'effective_context_window_percent': 95,
             'model_messages': {'base_instructions': 'preserve entire model metadata'}},
            {'slug': 'example-secondary', 'context_window': 272000,
             'max_context_window': 872000, 'effective_context_window_percent': 95},
        ]
        (self.root / 'models_cache.json').write_text(
            json.dumps({'fetched_at': 'private-identity-not-for-catalog', 'models': self.models}), encoding='utf-8')
        self.settings = cw.ContextSettings(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_units(self):
        for source, expected in [('60万', 600000), ('600k', 600000), ('1M', 1000000), ('370000', 370000)]:
            self.assertEqual(cw.token_count(source), expected)
        for source in ['0', '-1', '1.5万', 'hello']:
            with self.assertRaises(ValueError):
                cw.token_count(source)

    def test_all_roundtrip(self):
        before = self.cfg.read_bytes()
        result = self.settings.set_global('global-all', '60万')
        parsed = tomllib.loads(self.cfg.read_text(encoding='utf-8'))
        self.assertEqual(parsed['model_context_window'], 600000)
        self.assertTrue(parsed['plugins']['example']['enabled'])
        self.assertIn('# keep this comment', self.cfg.read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'saved_requires_reload')
        self.settings.restore(result['backup_manifest'])
        self.assertEqual(before, self.cfg.read_bytes())

    def test_model_preserves_other_metadata_and_does_not_touch_cache(self):
        cache_before = (self.root / 'models_cache.json').read_bytes()
        result = self.settings.set_global('global-model', '60万', 'example-main')
        data, _ = self.settings.catalog()
        expected = copy.deepcopy(self.models)
        expected[0]['context_window'] = 600000
        self.assertEqual(data, {'models': expected})
        self.assertEqual(cache_before, (self.root / 'models_cache.json').read_bytes())
        self.assertNotIn('model_context_window', tomllib.loads(self.cfg.read_text(encoding='utf-8')))
        self.settings.restore(result['backup_manifest'])
        self.assertEqual(self.initial, self.cfg.read_text(encoding='utf-8'))
        self.assertFalse(self.settings.catalog_path.exists())

    def test_existing_scalar_does_not_mask_model_setting(self):
        self.settings.set_global('global-all', 700000)
        result = self.settings.set_global('global-model', 600000, 'example-main')
        self.assertTrue(result['existing_global_override_materialized'])
        models = {m['model']: m for m in self.settings.status()['models']}
        self.assertEqual(models['example-main']['expected_effective_window'], 570000)
        self.assertEqual(models['example-secondary']['expected_effective_window'], 665000)

    def test_unknown_model_no_config_change(self):
        before = self.cfg.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.set_global('global-model', 500000, 'invented-model')
        self.assertEqual(before, self.cfg.read_bytes())
        self.assertFalse(self.settings.catalog_path.exists())

    def test_restore_detects_later_changes(self):
        result = self.settings.set_global('global-all', 600000)
        self.cfg.write_text(self.cfg.read_text(encoding='utf-8') + '\n# later user edit\n', encoding='utf-8')
        before = self.cfg.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.restore(result['backup_manifest'])
        self.assertEqual(before, self.cfg.read_bytes())

    def test_limits_are_clamped_not_reported_as_live_verified(self):
        self.settings.set_global('global-all', 1000000)
        status = self.settings.status()
        self.assertEqual(status['models'][0]['expected_effective_window'], 828400)
        self.assertFalse(status['runtime_verified'])

    def test_removed_scope_is_rejected(self):
        before = self.cfg.read_bytes()
        for scope in ('session-all', 'session-model'):
            self.assertNotIn(scope, cw.SCOPES)
            with self.assertRaises(ValueError):
                self.settings.set_global(scope, '60万', 'example-main')
        self.assertEqual(before, self.cfg.read_bytes())
        self.assertFalse(hasattr(self.settings, 'prepare_session'))

    def test_root_edit_does_not_change_section_keys(self):
        text = 'model_context_window = 500000\n[example]\nmodel_context_window = 100\n'
        changed = cw.root_key(text, 'model_context_window', '600000')
        data = tomllib.loads(changed)
        self.assertEqual(data['model_context_window'], 600000)
        self.assertEqual(data['example']['model_context_window'], 100)

    def test_absent_config_can_restore_to_absent(self):
        self.cfg.unlink()
        result = self.settings.set_global('global-all', 600000)
        self.assertTrue(self.cfg.exists())
        self.settings.restore(result['backup_manifest'])
        self.assertFalse(self.cfg.exists())

    def test_refresh_keeps_only_explicit_model_choices(self):
        self.settings.set_global('global-model', 600000, 'example-main')
        incoming = copy.deepcopy(self.models)
        incoming[0]['context_window'] = 510000
        incoming[1]['context_window'] = 300000
        incoming.append({'slug': 'example-small', 'context_window': 272000,
                         'max_context_window': 872000, 'effective_context_window_percent': 95})
        (self.root / 'models_cache.json').write_text(json.dumps({'models': incoming}), encoding='utf-8')
        before = self.settings.catalog_path.read_bytes()
        preview = self.settings.refresh_catalog()
        self.assertEqual(preview['status'], 'preview')
        self.assertEqual(preview['new_models'], ['example-small'])
        self.assertEqual(before, self.settings.catalog_path.read_bytes())
        applied = self.settings.refresh_catalog(apply=True)
        entries = {m['slug']: m for m in self.settings.catalog()[0]['models']}
        self.assertEqual(entries['example-main']['context_window'], 600000)
        self.assertEqual(entries['example-secondary']['context_window'], 300000)
        self.assertEqual(entries['example-small']['context_window'], 272000)
        self.settings.restore(applied['backup_manifest'])
        self.assertEqual(before, self.settings.catalog_path.read_bytes())

    def test_refresh_keeps_multiple_explicit_choices(self):
        self.settings.set_global('global-model', 600000, 'example-main')
        self.settings.set_global('global-model', 400000, 'example-secondary')
        incoming = copy.deepcopy(self.models)
        incoming[0]['context_window'] = 520000
        incoming[1]['context_window'] = 310000
        (self.root / 'models_cache.json').write_text(json.dumps({'models': incoming}), encoding='utf-8')
        self.settings.refresh_catalog(apply=True)
        entries = {m['slug']: m for m in self.settings.catalog()[0]['models']}
        self.assertEqual(entries['example-main']['context_window'], 600000)
        self.assertEqual(entries['example-secondary']['context_window'], 400000)

    def test_refresh_refuses_missing_customized_model(self):
        self.settings.set_global('global-model', 600000, 'example-main')
        before = self.settings.catalog_path.read_bytes()
        (self.root / 'models_cache.json').write_text(
            json.dumps({'models': [self.models[1]]}), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.settings.refresh_catalog(apply=True)
        self.assertEqual(before, self.settings.catalog_path.read_bytes())

    def entries(self):
        return {m['slug']: m for m in self.settings.catalog()[0]['models']}

    def cache(self, models):
        (self.root / 'models_cache.json').write_text(json.dumps({'models': models}), encoding='utf-8')

    def test_three_parameters_and_restore(self):
        original = self.cfg.read_bytes()
        result = self.settings.set_global('global-model', '60万', 'example-main', '95%', '50万')
        m = self.entries()['example-main']
        self.assertEqual((m['context_window'], m['effective_context_window_percent'], m['auto_compact_token_limit']),
                         (600000, 95, 500000))
        self.assertEqual(self.entries()['example-secondary'], self.models[1])
        self.settings.restore(result['backup_manifest'])
        self.assertEqual(self.cfg.read_bytes(), original)
        self.assertFalse(self.settings.catalog_path.exists())

    def test_percentage_only_does_not_change_window_or_compaction(self):
        self.settings.set_global('global-model', model='example-main', effective_percent='90%')
        expected = copy.deepcopy(self.models[0])
        expected['effective_context_window_percent'] = 90
        self.assertEqual(self.entries()['example-main'], expected)
        self.assertEqual(self.entries()['example-secondary'], self.models[1])

    def test_compaction_only_and_model_default(self):
        self.models[0]['auto_compact_token_limit'] = 410000
        self.cache(self.models)
        self.settings.set_global('global-model', model='example-main', auto_compact_limit='40万')
        self.assertEqual(self.entries()['example-main']['auto_compact_token_limit'], 400000)
        self.settings.set_global('global-model', model='example-main', auto_compact_limit='default')
        self.assertEqual(self.entries()['example-main']['auto_compact_token_limit'], 410000)
        self.assertNotIn('auto_compact_token_limit',
                         self.settings.status()['custom_parameters']['models'].get('example-main', {}))

    def test_default_compaction_follows_future_catalog(self):
        self.settings.set_global('global-model', model='example-main', auto_compact_limit=400000)
        self.settings.set_global('global-model', model='example-main', auto_compact_limit='default')
        self.models[0]['auto_compact_token_limit'] = 390000
        self.cache(self.models)
        self.settings.refresh_catalog(apply=True)
        self.assertEqual(self.entries()['example-main']['auto_compact_token_limit'], 390000)

    def test_all_parameters_and_scalar_compaction_materialization(self):
        self.settings.set_global('global-all', 600000, effective_percent=95, auto_compact_limit=500000)
        before = {m['model']: m for m in self.settings.status()['models']}
        result = self.settings.set_global('global-model', model='example-main', auto_compact_limit=400000)
        config = tomllib.loads(self.cfg.read_text(encoding='utf-8'))
        self.assertNotIn('model_auto_compact_token_limit', config)
        self.assertEqual(config['model_context_window'], 600000)
        after = {m['model']: m for m in self.settings.status()['models']}
        self.assertEqual(before['example-secondary'], after['example-secondary'])
        self.assertEqual(after['example-main']['expected_compaction_limit'], 400000)
        self.assertTrue(result['existing_global_compaction_materialized'])

    def test_default_removes_global_and_custom_compaction(self):
        self.settings.set_global('global-model', model='example-main', auto_compact_limit=400000)
        self.settings.set_global('global-all', auto_compact_limit=200000)
        self.settings.set_global('global-all', auto_compact_limit='default')
        self.assertNotIn('model_auto_compact_token_limit', tomllib.loads(self.cfg.read_text(encoding='utf-8')))
        for entry in self.entries().values():
            self.assertNotIn('auto_compact_token_limit', entry)

    def test_unchanged_parameters_and_preview(self):
        original = self.cfg.read_bytes()
        result = self.settings.set_global('global-model', '60万', 'example-main', 95, 500000, preview=True)
        self.assertEqual(result['status'], 'preview')
        self.assertEqual(self.cfg.read_bytes(), original)
        self.assertFalse(self.settings.catalog_path.exists())
        self.assertFalse((self.settings.base / 'backups').exists())

    def test_bad_parameters_fail_before_writes(self):
        for kwargs in ({}, {'effective_percent': 0}, {'effective_percent': 101},
                       {'auto_compact_limit': 'garbage'}, {'tokens': 600000, 'auto_compact_limit': 550000},
                       {'tokens': 600000, 'effective_percent': 50, 'auto_compact_limit': 400000}):
            with self.subTest(kwargs=kwargs):
                before = self.cfg.read_bytes()
                with self.assertRaises(ValueError):
                    self.settings.set_global('global-model', model='example-main', **kwargs)
                self.assertEqual(self.cfg.read_bytes(), before)
                self.assertFalse(self.settings.catalog_path.exists())

    def test_window_only_preserves_compaction_and_percentage(self):
        self.models[0]['auto_compact_token_limit'] = 400000
        self.models[0]['effective_context_window_percent'] = 90
        self.cache(self.models)
        self.settings.set_global('global-model', '60万', 'example-main')
        self.assertEqual(self.entries()['example-main']['auto_compact_token_limit'], 400000)
        self.assertEqual(self.entries()['example-main']['effective_context_window_percent'], 90)

    def test_refresh_keeps_three_parameters_and_adopts_other_metadata(self):
        self.settings.set_global('global-model', '60万', 'example-main', 90, 500000)
        incoming = copy.deepcopy(self.models)
        incoming[0].update(context_window=510000, effective_context_window_percent=95,
                           auto_compact_token_limit=450000, new_server_field='adopt')
        incoming[1].update(context_window=310000, effective_context_window_percent=92)
        self.cache(incoming)
        self.settings.refresh_catalog(apply=True)
        sol = self.entries()['example-main']
        self.assertEqual((sol['context_window'], sol['effective_context_window_percent'], sol['auto_compact_token_limit']),
                         (600000, 90, 500000))
        self.assertEqual(sol['new_server_field'], 'adopt')
        self.assertEqual(self.entries()['example-secondary'], incoming[1])

    def test_global_percentage_applies_to_new_models_but_keeps_specific_override(self):
        self.settings.set_global('global-all', effective_percent=90)
        self.settings.set_global('global-model', model='example-main', effective_percent=95)
        incoming = copy.deepcopy(self.models) + [{'slug': 'new-model', 'context_window': 300000}]
        self.cache(incoming)
        self.settings.refresh_catalog(apply=True)
        values = self.entries()
        self.assertEqual(values['new-model']['effective_context_window_percent'], 90)
        self.assertEqual(values['example-secondary']['effective_context_window_percent'], 90)
        self.assertEqual(values['example-main']['effective_context_window_percent'], 95)

    def test_legacy_windows_migrate_without_inventing_parameters(self):
        result = self.settings.set_global('global-model', '60万', 'example-main')
        manifest = pathlib.Path(result['backup_manifest'])
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['operation'].pop('desired_parameters')
        data['operation']['desired_windows'] = {'example-main': 600000}
        data['version'] = '0.3.0'
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.settings.refresh_catalog(apply=True)
        state = self.settings.status()['custom_parameters']
        self.assertEqual(state, {'models': {'example-main': {'context_window': 600000}}, 'all_models': {}})

    def test_unknown_catalog_history_stops_refresh(self):
        self.settings.set_global('global-model', '60万', 'example-main')
        data = json.loads(self.settings.catalog_path.read_text(encoding='utf-8'))
        data['models'][0]['manual_edit'] = True
        self.settings.catalog_path.write_text(json.dumps(data), encoding='utf-8')
        before = self.settings.catalog_path.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.refresh_catalog(apply=True)
        self.assertEqual(before, self.settings.catalog_path.read_bytes())

    def test_bundled_refresh_source_and_preview(self):
        self.settings.set_global('global-model', '60万', 'example-main', 95, 500000)
        incoming = copy.deepcopy(self.models)
        incoming[1]['context_window'] = 300000
        before = self.settings.catalog_path.read_bytes()
        with mock.patch.object(cw, 'bundled_catalog', return_value=({'models': incoming}, 'bundled:installed')) as export:
            preview = self.settings.refresh_catalog(refresh_from_bundled=True, codex='existing.exe')
            export.assert_called_once_with('existing.exe')
            self.assertEqual(preview['source'], 'bundled:installed')
            self.assertEqual(before, self.settings.catalog_path.read_bytes())
            self.settings.refresh_catalog(refresh_from_bundled=True, apply=True)
        self.assertEqual(self.entries()['example-secondary']['context_window'], 300000)
        self.assertEqual(self.entries()['example-main']['auto_compact_token_limit'], 500000)

    def test_bundled_export_failure_never_changes_files(self):
        self.settings.set_global('global-model', '60万', 'example-main')
        before = self.settings.catalog_path.read_bytes()
        with mock.patch.object(cw, 'bundled_catalog', side_effect=ValueError('unsupported')):
            with self.assertRaises(ValueError):
                self.settings.refresh_catalog(refresh_from_bundled=True, apply=True)
        self.assertEqual(before, self.settings.catalog_path.read_bytes())

    def test_bundled_loader_invokes_only_existing_readonly_command(self):
        completed = subprocess.CompletedProcess([], 0, json.dumps({'models': self.models}), '')
        with mock.patch.object(cw.subprocess, 'run', return_value=completed) as run:
            data, source = cw.bundled_catalog('existing.exe')
        self.assertEqual(run.call_args.args[0], ['existing.exe', 'debug', 'models', '--bundled'])
        self.assertNotEqual(run.call_args.kwargs['env']['CODEX_HOME'], str(self.root))
        self.assertEqual(data['models'], self.models)
        self.assertEqual(source, 'bundled:existing.exe')

    def test_compaction_scope_that_cannot_be_preserved_is_rejected(self):
        self.cfg.write_text('model_auto_compact_token_limit = 200000\n'
                            'model_auto_compact_token_limit_scope = "body_after_prefix"\n' + self.initial,
                            encoding='utf-8')
        before = self.cfg.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.set_global('global-model', model='example-main', auto_compact_limit=300000)
        self.assertEqual(self.cfg.read_bytes(), before)

    def test_new_lower_model_cap_blocks_incompatible_custom_compaction(self):
        self.settings.set_global('global-model', '60万', 'example-main', 95, 500000)
        incoming = copy.deepcopy(self.models)
        incoming[0]['max_context_window'] = 400000
        self.cache(incoming)
        before = self.settings.catalog_path.read_bytes()
        with self.assertRaises(ValueError):
            self.settings.refresh_catalog(apply=True)
        self.assertEqual(before, self.settings.catalog_path.read_bytes())

    def test_source_flags_are_exclusive(self):
        with self.assertRaises(ValueError):
            self.settings.refresh_catalog(source='anything.json', refresh_from_bundled=True)

    def test_cli_percentage_only_preview(self):
        result = subprocess.run([sys.executable, '-B', str(SOURCE), '--home', str(self.root), 'set',
                                 '--scope', 'global-model', '--model', 'example-main',
                                 '--effective-percent', '90%', '--preview'], capture_output=True,
                                text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)['status'], 'preview')


if __name__ == '__main__':
    unittest.main(verbosity=2)
