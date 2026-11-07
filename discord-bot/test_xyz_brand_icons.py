"""Offline safety regression tests; no Discord or X requests are made."""
import base64
import tempfile
import unittest
from pathlib import Path

from xyz_brand_icons import decode_owner_logo, marker_path, read_markers, save_markers, owner_intent, TARGET_GUILD_ID

class BrandIconTests(unittest.TestCase):
    def test_guild_pinned(self):
        self.assertEqual(TARGET_GUILD_ID, 1566290427366080612)

    def test_off_by_default(self):
        self.assertFalse(owner_intent({}, 'GN_REVEAL_SERVER_ICON_ONCE'))
        self.assertFalse(owner_intent({}, 'GN_REVEAL_BOT_AVATAR_ONCE'))
        self.assertTrue(owner_intent({'GN_REVEAL_SERVER_ICON_ONCE':'true'}, 'GN_REVEAL_SERVER_ICON_ONCE'))

    def test_decodes_embedded_webp_but_not_external_svg_link(self):
        image = b'RIFF'+b'\x00\x00\x00\x00'+b'WEBP'+b'\x11'*2048
        svg = b'<svg><image href="data:image/webp;base64,'+base64.b64encode(image)+b'"/></svg>'
        self.assertEqual(decode_owner_logo(svg), image)
        with self.assertRaises(ValueError):
            decode_owner_logo(b'<svg><image href="https://host/logo.png"/></svg>')
        with self.assertRaises(ValueError):
            decode_owner_logo(b'<svg><image href="data:image/webp;base64,abc="/></svg>')
        with self.assertRaises(ValueError):
            decode_owner_logo(svg + b' ' * 100000)

    def test_markers_are_persisted_per_guild_and_bot(self):
        with tempfile.TemporaryDirectory() as d:
            p=marker_path(Path(d))
            self.assertEqual(read_markers(p),{})
            save_markers(p, {'guild':'testsha'})
            self.assertEqual(read_markers(p),{'guild':'testsha'})
            save_markers(p, {'guild':'testsha','bot':'testsha'})
            self.assertEqual(read_markers(p),{'guild':'testsha','bot':'testsha'})

if __name__=='__main__':
    unittest.main()
