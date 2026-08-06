from horcrux.backup import make_backup_zip
import zipfile


def test_make_backup_zip_contains_vault_files(tmp_path):
    v = tmp_path / "vaults" / "lab-1" / "raw" / "experiments"
    v.mkdir(parents=True)
    (v / "r.md").write_text("내용", encoding="utf-8")
    z = make_backup_zip(tmp_path)
    names = zipfile.ZipFile(z).namelist()
    assert "vaults/lab-1/raw/experiments/r.md" in names
