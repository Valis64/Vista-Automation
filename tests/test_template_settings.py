import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from utils.common import (
    load_template_settings,
    save_template_settings,
    update_template_settings,
    validate_template_settings,
    export_template_settings,
    import_template_settings,
)

class TemplateSettingsTest(unittest.TestCase):
    def test_rt3055_rotation(self):
        settings = load_template_settings("RT3055")
        self.assertEqual(settings.get("rotation"), 270)

    def test_tt3055_rotation(self):
        settings = load_template_settings("TT3055")
        self.assertEqual(settings.get("rotation"), 270)

    def test_pb004_rotation(self):
        settings = load_template_settings("PB004")
        self.assertEqual(settings.get("rotation"), 180)

    def test_tt3075_rotation(self):
        settings = load_template_settings("TT3075")
        self.assertEqual(settings.get("rotation"), 270)

    def test_tt3062_rotation(self):
        settings = load_template_settings("TT3062")
        self.assertEqual(settings.get("rotation"), 270)

    def test_lb3218_rotation(self):
        settings = load_template_settings("LB3218")
        self.assertEqual(settings.get("rotation"), 180)

    def test_rt3734_rotation(self):
        settings = load_template_settings("RT3734")
        self.assertEqual(settings.get("rotation"), 90)

    def test_rt3722_rotation(self):
        settings = load_template_settings("RT3722")
        self.assertEqual(settings.get("rotation"), 90)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Template settings",
                "type": "object",
                "properties": {"rotation": {"type": "integer"}},
                "additionalProperties": False,
            }
            Path(tmp, "schema.json").write_text(json.dumps(schema))
            with patch("utils.common.TEMPLATE_SETTINGS_DIR", Path(tmp)):
                save_template_settings("ZZ0001", {"rotation": 45})
                data = load_template_settings("ZZ0001")
                self.assertEqual(data["rotation"], 45)

    def test_update_preserves_other_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Template settings",
                "type": "object",
                "properties": {
                    "rotation": {"type": "integer"},
                    "bleedPaths": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            }
            Path(tmp, "schema.json").write_text(json.dumps(schema))
            existing = {"rotation": 90, "bleedPaths": ["A", "B"]}
            Path(tmp, "ZZ0001.json").write_text(json.dumps(existing))
            with patch("utils.common.TEMPLATE_SETTINGS_DIR", Path(tmp)):
                update_template_settings("ZZ0001", {"rotation": 180})
                data = load_template_settings("ZZ0001")
                self.assertEqual(data["rotation"], 180)
                self.assertEqual(data["bleedPaths"], ["A", "B"])

    def test_validation(self):
        self.assertTrue(validate_template_settings({"rotation": 90}))
        with self.assertRaises(ValueError):
            validate_template_settings({"rotation": "90"})
        with self.assertRaises(ValueError):
            validate_template_settings({"extra": 1})

    def test_validation_schema_change(self):
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Template settings",
            "type": "object",
            "required": ["rotation"],
            "properties": {"rotation": {"type": "integer"}},
            "additionalProperties": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = Path(tmp) / "schema.json"
            schema_path.write_text(json.dumps(schema))
            with patch("utils.common.TEMPLATE_SETTINGS_DIR", Path(tmp)):
                with self.assertRaises(ValueError) as ctx:
                    validate_template_settings({})
                self.assertIn("rotation", str(ctx.exception))

    def test_export_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Template settings",
                "type": "object",
                "properties": {"rotation": {"type": "integer"}},
                "additionalProperties": False,
            }
            Path(tmp, "schema.json").write_text(json.dumps(schema))
            Path(tmp, "AA0001.json").write_text(json.dumps({"rotation": 90}))
            with patch("utils.common.TEMPLATE_SETTINGS_DIR", Path(tmp)):
                archive = Path(tmp, "settings.zip")
                export_template_settings(archive)
                Path(tmp, "AA0001.json").unlink()
                import_template_settings(archive)
                data = load_template_settings("AA0001")
                self.assertEqual(data["rotation"], 90)
                Path(tmp, "AA0001.json").write_text(json.dumps({"rotation": 45}))
                with self.assertRaises(FileExistsError):
                    import_template_settings(archive)
                import_template_settings(archive, overwrite=True)
                data = load_template_settings("AA0001")
                self.assertEqual(data["rotation"], 90)

if __name__ == "__main__":
    unittest.main()
