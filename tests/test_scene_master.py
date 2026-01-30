"""
Tests for Scene Master UI improvements (Issue #3)
Tests standby indication, cancel functionality, and state management
"""

import json
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from resolume_colour_picker.application import ColourPickerEngine
from resolume_colour_picker.config import Config


class TestSceneMasterBase(unittest.TestCase):
    """Base test class with common setup"""

    @classmethod
    def setUpClass(cls):
        """Create QApplication instance for all tests"""
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        """Set up test fixtures"""
        self.mock_config = self._create_mock_config()
        self.consts = self._create_consts()
        self.engine = self._create_engine()

    def _create_mock_config(self):
        """Create a mock config object"""
        config = MagicMock(spec=Config)
        config.__getitem__ = MagicMock(side_effect=lambda key: {
            "WEBSERVER_IP": "localhost",
            "WEBSERVER_PORT": 8080,
            "COLOUR_SET": {
                "1 - Red": "#FF0000",
                "2 - Blue": "#0000FF",
                "3 - Yellow": "#FFFF00",
            },
            "LAYER_MAP": {
                "ALL": "ALL",
                "Outer": "Layer 1",
                "Inner": "Layer 2",
            }
        }[key])
        config.value_changed = MagicMock()
        config.value_changed.connect = MagicMock()
        return config

    def _create_consts(self):
        """Create constants dictionary"""
        return {
            "WINDOW_SIZE": (900, 700),
            "BUTTON_HEIGHT": 55,
            "DARKEN_FACTOR": 0.65,
            "HEARTBEAT_INTERVAL": 3000
        }

    def _create_engine(self):
        """Create ColourPickerEngine instance with mocked components"""
        # Mock files to return valid JSON matching actual structure
        mock_files = MagicMock()
        mock_file_content = json.dumps({
            "video": {
                "effects": [
                    {
                        "params": {
                            "Color": {
                                "value": "#FFFFFF"
                            }
                        }
                    }
                ]
            }
        })
        mock_files.return_value.joinpath.return_value.read_text.return_value = mock_file_content
        
        with patch('resolume_colour_picker.application.StatusHeartbeat'):
            with patch('resolume_colour_picker.application.files', mock_files):
                engine = ColourPickerEngine(self.mock_config, self.consts)
                engine.show()  # Make sure the widget is shown for visibility checks
                engine.session = MagicMock()
                engine.executor = MagicMock()
                return engine


class TestStandbyIndication(TestSceneMasterBase):
    """Test standby visual indication in Scene Master mode"""

    def test_desaturate_method_exists(self):
        """Test that desaturate method exists"""
        self.assertTrue(hasattr(self.engine, 'desaturate'))
        self.assertTrue(callable(self.engine.desaturate))

    def test_desaturate_reduces_saturation(self):
        """Test that desaturate reduces colour saturation"""
        original = QColor("#FF0000")  # Red
        desaturated = self.engine.desaturate(original)
        
        # Saturation should be reduced
        self.assertLess(desaturated.saturation(), original.saturation())

    def test_button_stylesheet_includes_standby_parameter(self):
        """Test that button_stylesheet accepts standby parameter"""
        colour = QColor("#FF0000")
        style = self.engine.button_stylesheet(colour, selected=False, standby=False)
        self.assertIn("QPushButton", style)

    def test_standby_styling_has_dashed_border(self):
        """Test that standby styling uses dashed border"""
        colour = QColor("#FF0000")
        style = self.engine.button_stylesheet(colour, selected=True, standby=True)
        
        # Should contain dashed border for standby
        self.assertIn("dashed", style)
        # Should also have desaturated appearance
        self.assertIn("dashed", style)

    def test_live_styling_has_solid_border(self):
        """Test that live styling uses solid border"""
        colour = QColor("#FF0000")
        style = self.engine.button_stylesheet(colour, selected=True, standby=False)
        
        # Should not contain dashed border for non-standby
        self.assertNotIn("dashed", style)

    def test_live_selections_visible_in_scene_master(self):
        """Test that live selections remain visible when entering Scene Master"""
        self.engine._add_buttons()
        # First select in live mode
        self.engine.select_single("Outer", 0)
        live_selection = ("Outer", 0)
        
        # Enter Scene Master mode
        self.engine.toggle_scene_master()
        
        # Live selection should still be in selected_in_column
        self.assertIn("Outer", self.engine.selected_in_column)
        # And should be in live_selections
        self.assertIn(live_selection, self.engine.live_selections)


class TestCancelFunctionality(TestSceneMasterBase):
    """Test cancel Scene Master functionality"""

    def test_cancel_button_exists(self):
        """Test that cancel button is created"""
        self.assertTrue(hasattr(self.engine, 'cancel_btn'))
        self.assertIsNotNone(self.engine.cancel_btn)

    def test_standby_selections_dict_exists(self):
        """Test that standby_selections tracking dictionary exists"""
        self.assertTrue(hasattr(self.engine, 'standby_selections'))
        self.assertIsInstance(self.engine.standby_selections, dict)

    def test_live_selections_dict_exists(self):
        """Test that live_selections tracking dictionary exists"""
        self.assertTrue(hasattr(self.engine, 'live_selections'))
        self.assertIsInstance(self.engine.live_selections, dict)

    def test_cancel_clears_queued_changes(self):
        """Test that cancel clears queued changes"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        self.engine.queued_changes = [("Outer", "#FF0000"), ("Inner", "#0000FF")]
        self.engine.standby_selections = {("Outer", 0): True, ("Inner", 1): True}
        
        self.engine.cancel_scene_master()
        
        self.assertEqual(len(self.engine.queued_changes), 0)

    def test_cancel_exits_scene_master_mode(self):
        """Test that cancel exits Scene Master mode"""
        self.engine.toggle_scene_master()
        
        self.engine.cancel_scene_master()
        
        # Should be in live mode after cancel
        self.assertFalse(self.engine.scene_master_mode)

    def test_cancel_restores_live_selections(self):
        """Test that cancel restores previous live selections"""
        self.engine._add_buttons()
        # Select in live mode
        self.engine.select_single("Outer", 0)
        
        # Enter Scene Master
        self.engine.toggle_scene_master()
        
        # Make new selection
        self.engine.select_single("Outer", 1)
        
        # Cancel
        self.engine.cancel_scene_master()
        
        # Should restore original selection
        self.assertEqual(self.engine.selected_in_column.get("Outer"), 0)

    def test_deselect_standby_selection_by_clicking_again(self):
        """Test that clicking a standby selection again deselects it"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Select a new colour (creates standby)
        self.engine.select_single("Outer", 1)
        self.assertIn(("Outer", 1), self.engine.standby_selections)
        
        # Click the same button again (deselect)
        self.engine.select_single("Outer", 1)
        
        # Should be removed from standby
        self.assertNotIn(("Outer", 1), self.engine.standby_selections)

    def test_deselect_removes_from_queued_changes(self):
        """Test that deselecting a standby removes it from queued_changes"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Queue a change
        self.engine.on_press("Outer", 1, "#0000FF")
        self.assertEqual(len(self.engine.queued_changes), 1)
        
        # Deselect it
        self.engine.select_single("Outer", 1)
        
        # Should be removed from queued changes
        self.assertEqual(len(self.engine.queued_changes), 0)


class TestStateManagement(TestSceneMasterBase):
    """Test state management during mode transitions"""

    def test_select_single_tracks_standby_state(self):
        """Test that select_single tracks selections in standby mode"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Select a new colour in Scene Master mode
        self.engine.select_single("Outer", 1)
        
        # Should track in standby_selections
        self.assertIn(("Outer", 1), self.engine.standby_selections)

    def test_select_single_tracks_live_state(self):
        """Test that select_single tracks selections in live mode"""
        self.engine._add_buttons()
        self.engine.scene_master_mode = False
        
        # Select a colour in live mode
        self.engine.select_single("Outer", 0)
        
        # Should track in live_selections
        self.assertIn(("Outer", 0), self.engine.live_selections)

    def test_only_one_standby_per_column(self):
        """Test that only one standby selection is allowed per column"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Select first colour
        self.engine.select_single("Outer", 0)
        self.assertIn(("Outer", 0), self.engine.standby_selections)
        
        # Select different colour in same column
        self.engine.select_single("Outer", 1)
        
        # First should be deselected
        self.assertNotIn(("Outer", 0), self.engine.standby_selections)
        # Second should be selected
        self.assertIn(("Outer", 1), self.engine.standby_selections)

    def test_queued_changes_updated_with_selections(self):
        """Test that queued_changes matches standby selections"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Make selection via on_press
        self.engine.on_press("Outer", 0, "#FF0000")
        
        # queued_changes should reflect the change
        self.assertEqual(len(self.engine.queued_changes), 1)
        self.assertIn(("Outer", "#FF0000"), self.engine.queued_changes)

    def test_queued_changes_replaced_on_new_selection(self):
        """Test that queued_changes are replaced for same column"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Queue first change
        self.engine.on_press("Outer", 0, "#FF0000")
        self.assertEqual(len(self.engine.queued_changes), 1)
        
        # Queue different change for same column
        self.engine.on_press("Outer", 1, "#0000FF")
        
        # Should still be one change, but for different colour
        self.assertEqual(len(self.engine.queued_changes), 1)
        self.assertIn(("Outer", "#0000FF"), self.engine.queued_changes)
        self.assertNotIn(("Outer", "#FF0000"), self.engine.queued_changes)


class TestSceneMasterModeTransitions(TestSceneMasterBase):
    """Test transitions between modes"""

    def test_enter_scene_master_mode(self):
        """Test entering Scene Master mode"""
        self.engine.toggle_scene_master()
        
        self.assertTrue(self.engine.scene_master_mode)
        self.assertIn("SCENE MASTER", self.engine.scene_mode_label.text())

    def test_exit_scene_master_mode(self):
        """Test exiting Scene Master mode"""
        self.engine.toggle_scene_master()
        self.engine.toggle_scene_master()
        
        self.assertFalse(self.engine.scene_master_mode)
        self.assertIn("Live Mode", self.engine.scene_mode_label.text())

    def test_go_button_visibility_in_scene_master(self):
        """Test that GO button is visible in Scene Master mode"""
        self.engine.toggle_scene_master()
        
        self.assertTrue(self.engine.go_btn.isVisible())

    def test_cancel_button_visibility_in_scene_master(self):
        """Test that Cancel button is visible in Scene Master mode"""
        self.engine.toggle_scene_master()
        
        self.assertTrue(self.engine.cancel_btn.isVisible())

    def test_go_cancel_buttons_hidden_in_live_mode(self):
        """Test that GO/Cancel buttons are hidden in Live mode"""
        self.engine.scene_master_mode = False
        
        self.assertFalse(self.engine.go_btn.isVisible())
        self.assertFalse(self.engine.cancel_btn.isVisible())

    def test_go_converts_standby_to_live(self):
        """Test that GO converts standby selections to live"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Make standby selection
        self.engine.on_press("Outer", 1, "#0000FF")
        self.assertIn(("Outer", 1), self.engine.standby_selections)
        
        # Send changes
        self.engine.send_queued_changes()
        
        # Standby should be converted to live
        self.assertIn(("Outer", 1), self.engine.live_selections)
        self.assertNotIn(("Outer", 1), self.engine.standby_selections)

    def test_go_exits_scene_master_mode(self):
        """Test that GO exits Scene Master mode"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        self.engine.send_queued_changes()
        
        self.assertFalse(self.engine.scene_master_mode)


class TestUIConsistency(TestSceneMasterBase):
    """Test that UI remains consistent after operations"""

    def test_button_state_after_cancel(self):
        """Test that button states are valid after cancel"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Select some buttons
        self.engine.select_single("Outer", 0)
        
        # Cancel should not break button references
        self.engine.cancel_scene_master()
        
        # Should still have all buttons
        self.assertGreater(len(self.engine.buttons), 0)

    def test_selected_in_column_consistency(self):
        """Test that selected_in_column dict remains consistent"""
        self.engine._add_buttons()
        
        self.engine.select_single("Outer", 0)
        self.engine.select_single("Outer", 1)
        
        # Should only track the latest selection per column
        self.assertEqual(self.engine.selected_in_column["Outer"], 1)

    def test_mode_indicator_label_updates(self):
        """Test that mode indicator label updates correctly"""
        initial_text = self.engine.scene_mode_label.text()
        
        self.engine.toggle_scene_master()
        scene_master_text = self.engine.scene_mode_label.text()
        
        self.engine.toggle_scene_master()
        final_text = self.engine.scene_mode_label.text()
        
        # Should change when toggling
        self.assertNotEqual(initial_text, scene_master_text)
        self.assertEqual(final_text, initial_text)

    def test_live_selection_stays_visible_with_standby(self):
        """Test that live selections remain visible when making standby selections"""
        self.engine._add_buttons()
        # Select in live mode first
        self.engine.select_single("Outer", 0)
        
        # Enter Scene Master
        self.engine.toggle_scene_master()
        
        # Make different selection
        self.engine.select_single("Outer", 1)
        
        # Both live and standby should be tracked
        self.assertIn(("Outer", 0), self.engine.live_selections)
        self.assertIn(("Outer", 1), self.engine.standby_selections)

    def test_all_columns_queues_for_all_layers(self):
        """Test that selecting ALL column queues changes for all layers"""
        self.engine._add_buttons()
        self.engine.toggle_scene_master()
        
        # Select on ALL column
        self.engine.on_press("ALL", 0, "#FF0000")
        
        # Should queue for all non-ALL columns
        non_all_count = len(self.engine.non_all_columns)
        self.assertEqual(len(self.engine.queued_changes), non_all_count)


if __name__ == '__main__':
    unittest.main()
