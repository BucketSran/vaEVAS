import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from archive import verify_archive_members


class ArchiveCalibration(unittest.TestCase):
    def test_manifest_mutation_cannot_skip_archived_file_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'FILE_MANIFEST.json').write_bytes(b'{"wave.psf": "frozen"}')
            (root / 'wave.psf').write_bytes(b'VALUE\n"time" 0\n"v" 1\nEND\n')
            with tarfile.open(root / 'raw.tar.gz', 'w:gz') as archive:
                for name in ['FILE_MANIFEST.json', 'wave.psf']:
                    archive.add(root / name, arcname=name)
            identity = hashlib.sha256((root / 'raw.tar.gz').read_bytes()).hexdigest()
            result = verify_archive_members(root, identity, ['wave.psf'])
            self.assertEqual(result['wave.psf']['bytes'], 25)
            (root / 'FILE_MANIFEST.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):
                verify_archive_members(root, identity, ['wave.psf'])

    def collection(self, members=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        (root / 'rows').mkdir()
        (root / 'rows/wave.psf').write_bytes(b'VALUE\n"time" 0\n"v" 1\nEND\n')
        with tarfile.open(root / 'raw.tar.gz', 'w:gz') as archive:
            if members is None:
                archive.add(root / 'rows', arcname='rows')
            else:
                for member, payload in members:
                    archive.addfile(member, io.BytesIO(payload) if payload is not None else None)
        identity = hashlib.sha256((root / 'raw.tar.gz').read_bytes()).hexdigest()
        return root, identity

    def test_valid_archive_returns_all_regular_members_without_extraction(self):
        root, identity = self.collection()
        before = (root / 'rows/wave.psf').read_bytes()
        result = verify_archive_members(root, identity, ['rows/wave.psf'])
        self.assertEqual(set(result), {'rows/wave.psf'})
        self.assertEqual(result['rows/wave.psf']['bytes'], 25)
        self.assertEqual((root / 'rows/wave.psf').read_bytes(), before)

    def test_same_shape_same_size_psf_mutation_rejected(self):
        root, identity = self.collection()
        (root / 'rows/wave.psf').write_bytes(b'VALUE\n"time" 0\n"v" 2\nEND\n')
        with self.assertRaisesRegex(ValueError, 'differs from archive'):
            verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_missing_unpacked_member_rejected(self):
        root, identity = self.collection()
        (root / 'rows/wave.psf').unlink()
        with self.assertRaises(ValueError):
            verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_reviewed_hash_required_before_tar_parsing(self):
        root, _ = self.collection()
        (root / 'raw.tar.gz').write_bytes(b'not a tar archive')
        with self.assertRaisesRegex(ValueError, 'reviewed identity'):
            verify_archive_members(root, '0' * 64, ['rows/wave.psf'])
        for identity in ['', 'not-a-hash']:
            with self.assertRaises(ValueError):
                verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_required_members_nonempty_regular_and_present(self):
        root, identity = self.collection()
        for required in [[], ['missing'], ['rows'], 'rows/wave.psf', None]:
            with self.subTest(required=required), self.assertRaises(ValueError):
                verify_archive_members(root, identity, required)

    def test_empty_archive_and_directory_only_archive_rejected(self):
        directory = tarfile.TarInfo('rows')
        directory.type = tarfile.DIRTYPE
        for members in [[], [(directory, None)]]:
            root, identity = self.collection(members)
            with self.assertRaisesRegex(ValueError, 'no regular payload'):
                verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_duplicate_and_unsafe_member_names_rejected(self):
        for name in ['rows/wave.psf', '../escape', '/absolute', './rows/wave.psf',
                     'rows/../escape', 'rows//wave.psf', 'C:/escape', 'rows\\wave.psf']:
            member = tarfile.TarInfo(name)
            member.size = 25
            members = [(member, b'VALUE\n"time" 0\n"v" 1\nEND\n')]
            if name == 'rows/wave.psf':
                members *= 2
            root, identity = self.collection(members)
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_nonregular_payload_types_rejected(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                     tarfile.CHRTYPE, tarfile.BLKTYPE]:
            member = tarfile.TarInfo('rows/wave.psf')
            member.type, member.linkname = kind, 'other'
            root, identity = self.collection([(member, None)])
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'nonregular'):
                verify_archive_members(root, identity, ['rows/wave.psf'])

    def test_unpacked_file_directory_and_archive_symlinks_rejected(self):
        for name in ['rows/wave.psf', 'rows', 'raw.tar.gz']:
            root, identity = self.collection()
            path = root / name
            moved = root / 'moved'
            path.rename(moved)
            path.symlink_to(moved, target_is_directory=moved.is_dir())
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'symlink'):
                verify_archive_members(root, identity, ['rows/wave.psf'])


if __name__ == '__main__':
    unittest.main()
