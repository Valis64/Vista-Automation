import unittest
from unittest.mock import MagicMock, patch
from review import (
    BLANK_TEMPLATE_ART_SENTINEL,
    FlaggedItem,
    FlagStatus,
    ReviewManager,
    is_blank_template_art_path,
)

class ReviewManagerTest(unittest.TestCase):
    def test_blank_template_art_path_detection(self):
        self.assertTrue(is_blank_template_art_path(BLANK_TEMPLATE_ART_SENTINEL))
        self.assertFalse(is_blank_template_art_path(""))
        self.assertFalse(is_blank_template_art_path("art.pdf"))

    def test_flat_review_complete(self):
        tree = MagicMock()
        tree.get_children.return_value = ['id1']
        menu = MagicMock()
        with patch('review.load_flags', return_value=[]), patch('utils.history.update_last_run_flagged') as upd:
            mgr = ReviewManager(MagicMock(), tree, menu)
            item = FlaggedItem(id='1', path='a.pdf', reasons=['x'])
            mgr._add_flagged_item = MagicMock()
            mgr.flat_review_complete([item])
            mgr._add_flagged_item.assert_called_once_with(item)
            self.assertIn(item, mgr.flagged_items)
            upd.assert_called_once()

    def test_set_selected_status(self):
        tree = MagicMock()
        tree.selection.return_value = ['i1']
        tree.get_children.return_value = ['i1']
        menu = MagicMock()
        with patch('review.load_flags', return_value=[]), patch('utils.history.update_last_run_flagged'):
            mgr = ReviewManager(MagicMock(), tree, menu)
            itm = FlaggedItem(id='1', path='a', reasons=['x'])
            mgr.tree_items = {'i1': itm}
            mgr._set_selected_status(FlagStatus.IGNORED)
            self.assertEqual(itm.status, FlagStatus.IGNORED)
            tree.set.assert_called_with('i1', 'status', 'ignored')
